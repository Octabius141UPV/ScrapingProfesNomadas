"""Safety policy for automatic SMTP application delivery."""

from __future__ import annotations

import logging
import os
import asyncio
import functools
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Mapping, Optional

from src.utils.cloud_audit import CloudAuditLogger
from src.utils.firebase_manager import (
    claim_application_send_queue_item,
    enqueue_application_send_queue_item,
    finalize_application_send_reservation,
    release_application_send_reservation,
    reserve_application_send,
    set_application_send_queue_item_status,
)

logger = logging.getLogger(__name__)


def _positive_int(value: Optional[str], default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _production_ceiling(value: Optional[str], default: int, ceiling: int, name: str) -> int:
    configured = _positive_int(value, default)
    if configured > ceiling:
        logger.warning("%s exceeds the production safety ceiling; clamping to %s.", name, ceiling)
        return ceiling
    return configured


def _production_floor(value: Optional[str], default: int, floor: int, name: str) -> int:
    configured = _non_negative_int(value, default)
    if configured < floor:
        logger.warning("%s is below the production safety floor; clamping to %s.", name, floor)
        return floor
    return configured


def _non_negative_int(value: Optional[str], default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def offer_identity(offer: Dict, recipient: str) -> str:
    """Choose a stable offer identity without putting it in logs or document IDs."""
    for key in ("id", "vacancy_id", "offer_id", "url"):
        value = offer.get(key)
        if value:
            return f"{key}:{value}"
    # The recipient is the reliable fallback when the scraper has no offer ID.
    return f"recipient:{recipient.strip().lower()}"


def position_identity(offer: Dict) -> str:
    """Return a stable non-sensitive position input for a HMAC identifier."""
    return str(
        offer.get("position")
        or offer.get("vacancy")
        or offer.get("title")
        or "unspecified-position"
    )


@dataclass(frozen=True)
class SendDecision:
    allowed: bool
    reason: str
    account_id: Optional[str] = None
    recipient_id: Optional[str] = None
    offer_id: Optional[str] = None
    delay_seconds: int = 0


@dataclass(frozen=True)
class QueueDecision:
    queued: bool
    reason: str
    account_id: Optional[str] = None
    offer_id: Optional[str] = None
    position_id: Optional[str] = None


class ApplicationSendPolicy:
    """Reserve a safe delivery slot before SMTP and settle it afterwards."""

    def __init__(
        self,
        environ: Optional[Mapping[str, str]] = None,
        audit_logger: Optional[CloudAuditLogger] = None,
    ):
        self._environ = environ if environ is not None else os.environ
        self.audit = audit_logger or CloudAuditLogger(self._environ)
        # A runtime toggle must never relax a deployed production worker. Only
        # an explicit non-production audit environment enables fast test values.
        self.test_only_configuration = (
            self._environ.get("APPLICATION_AUDIT_ENVIRONMENT", "").strip().lower()
            == "test"
        )
        if self.test_only_configuration:
            self.daily_limit = _positive_int(
                self._environ.get("APPLICATION_SEND_DAILY_LIMIT"), 100
            )
            self.batch_limit = _positive_int(
                self._environ.get("APPLICATION_SEND_BATCH_LIMIT"), 10
            )
            self.min_interval_seconds = _non_negative_int(
                self._environ.get("APPLICATION_SEND_MIN_INTERVAL_SECONDS"), 10
            )
            self.batch_pause_seconds = _non_negative_int(
                self._environ.get("APPLICATION_SEND_BATCH_PAUSE_SECONDS"), 300
            )
        else:
            self.daily_limit = _production_ceiling(
                self._environ.get("APPLICATION_SEND_DAILY_LIMIT"),
                100,
                100,
                "APPLICATION_SEND_DAILY_LIMIT",
            )
            self.batch_limit = _production_ceiling(
                self._environ.get("APPLICATION_SEND_BATCH_LIMIT"),
                10,
                10,
                "APPLICATION_SEND_BATCH_LIMIT",
            )
            self.min_interval_seconds = _production_floor(
                self._environ.get("APPLICATION_SEND_MIN_INTERVAL_SECONDS"),
                10,
                10,
                "APPLICATION_SEND_MIN_INTERVAL_SECONDS",
            )
            self.batch_pause_seconds = _production_floor(
                self._environ.get("APPLICATION_SEND_BATCH_PAUSE_SECONDS"),
                300,
                300,
                "APPLICATION_SEND_BATCH_PAUSE_SECONDS",
            )
        self._test_next_available_at = None

    def reserve(
        self,
        *,
        account_email: str,
        recipient_email: str,
        offer: Dict,
        run_id: str,
        test_mode: bool,
    ) -> SendDecision:
        """Atomically reserve a slot, unless this is a test-mode message."""
        account_id = self.audit.account_id(account_email)
        recipient_id = self.audit.recipient_id(recipient_email)
        offer_id = self.audit.offer_id(offer_identity(offer, recipient_email))

        if test_mode:
            now = datetime.now(timezone.utc)
            scheduled_at = max(now, self._test_next_available_at or now)
            self._test_next_available_at = scheduled_at + timedelta(
                seconds=self.min_interval_seconds
            )
            decision = SendDecision(
                allowed=True,
                reason="test_mode_exempt",
                account_id=account_id,
                recipient_id=recipient_id,
                offer_id=offer_id,
                delay_seconds=max(
                    0, math.ceil((scheduled_at - now).total_seconds())
                ),
            )
            self._emit_decision(run_id, decision, test_mode=True)
            return decision

        if not account_id or not recipient_id or not offer_id:
            decision = SendDecision(False, "safety_hash_key_missing")
            self._emit_decision(run_id, decision, test_mode=False)
            return decision

        result = reserve_application_send(
            account_id=account_id,
            offer_id=offer_id,
            daily_limit=self.daily_limit,
            min_interval_seconds=self.min_interval_seconds,
            batch_limit=self.batch_limit,
            batch_pause_seconds=self.batch_pause_seconds,
            now=datetime.now(timezone.utc),
        )
        decision = SendDecision(
            allowed=result["allowed"],
            reason=result["reason"],
            account_id=account_id,
            recipient_id=recipient_id,
            offer_id=offer_id,
            delay_seconds=result.get("delay_seconds", 0),
        )
        self._emit_decision(run_id, decision, test_mode=False)
        return decision

    async def reserve_async(self, **kwargs) -> SendDecision:
        """Reserve in a worker so Firestore and Cloud Logging do not block Telegram."""
        return await self._run_blocking(self.reserve, **kwargs)

    def enqueue(
        self,
        *,
        account_email: str,
        recipient_email: str,
        offer: Dict,
        run_id: str,
    ) -> QueueDecision:
        """Persist only HMAC queue metadata before a local session sends."""
        account_id = self.audit.account_id(account_email)
        offer_id = self.audit.offer_id(offer_identity(offer, recipient_email))
        position_id = self.audit.position_id(position_identity(offer))
        if not account_id or not offer_id or not position_id:
            decision = QueueDecision(False, "safety_hash_key_missing")
        else:
            result = enqueue_application_send_queue_item(
                account_id=account_id,
                offer_id=offer_id,
                run_id=run_id,
                position_id=position_id,
                now=datetime.now(timezone.utc),
            )
            decision = QueueDecision(
                result["queued"],
                result["reason"],
                account_id=account_id,
                offer_id=offer_id,
                position_id=position_id,
            )
        self._emit_queue_event("application_send_queue_enqueued", run_id, decision)
        return decision

    async def enqueue_async(self, **kwargs) -> QueueDecision:
        return await self._run_blocking(self.enqueue, **kwargs)

    def claim_queue_item(
        self, decision: QueueDecision, run_id: str, batch_number: int
    ) -> QueueDecision:
        """Claim a queued production item before preparing SMTP material."""
        if not decision.queued:
            return decision
        result = claim_application_send_queue_item(
            account_id=decision.account_id,
            offer_id=decision.offer_id,
            run_id=run_id,
            batch_number=batch_number,
            now=datetime.now(timezone.utc),
        )
        claimed = QueueDecision(
            result["claimed"],
            result["reason"],
            decision.account_id,
            decision.offer_id,
            decision.position_id,
        )
        self._emit_queue_event(
            "application_send_queue_claimed",
            run_id,
            claimed,
            batch_number=batch_number,
        )
        return claimed

    async def claim_queue_item_async(
        self, decision: QueueDecision, run_id: str, batch_number: int
    ) -> QueueDecision:
        return await self._run_blocking(
            self.claim_queue_item, decision, run_id, batch_number
        )

    def set_queue_item_status(
        self,
        decision: QueueDecision,
        run_id: str,
        *,
        status: str,
        reason: str,
        error_category: Optional[str] = None,
        batch_number: Optional[int] = None,
    ) -> None:
        """Persist a privacy-safe lifecycle transition after local delivery."""
        if decision.account_id and decision.offer_id:
            result = set_application_send_queue_item_status(
                account_id=decision.account_id,
                offer_id=decision.offer_id,
                status=status,
                now=datetime.now(timezone.utc),
                reason=reason,
                error_category=error_category,
            )
            outcome = result.get("reason", "queue_item_updated")
        else:
            outcome = "queue_state_not_persisted"
        self._emit_queue_event(
            "application_send_queue_transition",
            run_id,
            decision,
            outcome=outcome,
            queue_status=status,
            queue_reason=reason,
            error_category=error_category,
            batch_number=batch_number,
        )

    async def set_queue_item_status_async(self, decision: QueueDecision, run_id: str, **kwargs) -> None:
        await self._run_blocking(self.set_queue_item_status, decision, run_id, **kwargs)

    def record_batch_pause(self, run_id: str, account_email: str, batch_number: int) -> None:
        self.audit.emit(
            "application_send_batch_paused",
            run_id=run_id,
            account_id=self.audit.account_id(account_email),
            outcome="paused",
            batch_number=batch_number,
            batch_limit=self.batch_limit,
            batch_pause_seconds=self.batch_pause_seconds,
            daily_limit=self.daily_limit,
        )

    async def record_batch_pause_async(
        self, run_id: str, account_email: str, batch_number: int
    ) -> None:
        await self._run_blocking(
            self.record_batch_pause, run_id, account_email, batch_number
        )

    def mark_sent(self, decision: SendDecision, run_id: str) -> None:
        """Commit a reserved slot after SMTP accepted the message."""
        if self._requires_settlement(decision):
            result = finalize_application_send_reservation(
                account_id=decision.account_id,
                offer_id=decision.offer_id,
                now=datetime.now(timezone.utc),
            )
            outcome = result.get("reason", "finalized")
        else:
            outcome = "not_reserved"
        self.audit.emit(
            "application_send_settled",
            run_id=run_id,
            account_id=decision.account_id,
            recipient_id=decision.recipient_id,
            offer_id=decision.offer_id,
            outcome=outcome,
        )

    async def mark_sent_async(self, decision: SendDecision, run_id: str) -> None:
        await self._run_blocking(self.mark_sent, decision, run_id)

    def release_after_definite_failure(
        self, decision: SendDecision, run_id: str, error_category: str
    ) -> None:
        """Release only failures known to have happened before delivery."""
        if self._requires_settlement(decision):
            result = release_application_send_reservation(
                account_id=decision.account_id,
                offer_id=decision.offer_id,
                now=datetime.now(timezone.utc),
                error_category=error_category,
            )
            outcome = result.get("reason", "released")
        else:
            outcome = "not_reserved"
        self.audit.emit(
            "application_send_reservation_released",
            run_id=run_id,
            account_id=decision.account_id,
            recipient_id=decision.recipient_id,
            offer_id=decision.offer_id,
            outcome=outcome,
            error_category=error_category,
        )

    async def release_after_definite_failure_async(
        self, decision: SendDecision, run_id: str, error_category: str
    ) -> None:
        await self._run_blocking(
            self.release_after_definite_failure, decision, run_id, error_category
        )

    def record_smtp_result(
        self,
        decision: SendDecision,
        run_id: str,
        *,
        success: bool,
        error_category: Optional[str] = None,
    ) -> None:
        self.audit.emit(
            "application_smtp_result",
            severity="INFO" if success else "WARNING",
            run_id=run_id,
            account_id=decision.account_id,
            recipient_id=decision.recipient_id,
            offer_id=decision.offer_id,
            outcome="sent" if success else "failed",
            error_category=error_category,
        )

    async def record_smtp_result_async(
        self,
        decision: SendDecision,
        run_id: str,
        *,
        success: bool,
        error_category: Optional[str] = None,
    ) -> None:
        await self._run_blocking(
            self.record_smtp_result,
            decision,
            run_id,
            success=success,
            error_category=error_category,
        )

    def record_batch_skip(
        self,
        *,
        account_email: str,
        recipient_email: str,
        offer: Dict,
        run_id: str,
    ) -> None:
        self.audit.emit(
            "application_send_reservation",
            severity="WARNING",
            run_id=run_id,
            account_id=self.audit.account_id(account_email),
            recipient_id=self.audit.recipient_id(recipient_email),
            offer_id=self.audit.offer_id(offer_identity(offer, recipient_email)),
            outcome="skipped",
            decision="batch_limit_reached",
            daily_limit=self.daily_limit,
            batch_limit=self.batch_limit,
        )

    async def record_batch_skip_async(self, **kwargs) -> None:
        await self._run_blocking(self.record_batch_skip, **kwargs)

    def _emit_decision(self, run_id: str, decision: SendDecision, test_mode: bool) -> None:
        self.audit.emit(
            "application_send_reservation",
            severity="INFO" if decision.allowed else "WARNING",
            run_id=run_id,
            account_id=decision.account_id,
            recipient_id=decision.recipient_id,
            offer_id=decision.offer_id,
            outcome="reserved" if decision.allowed else "skipped",
            decision=decision.reason,
            delay_seconds=decision.delay_seconds,
            daily_limit=self.daily_limit,
            batch_limit=self.batch_limit,
            test_mode=test_mode,
        )

    def _emit_queue_event(
        self,
        event_type: str,
        run_id: str,
        decision: QueueDecision,
        **fields,
    ) -> None:
        self.audit.emit(
            event_type,
            severity="INFO" if decision.queued else "WARNING",
            run_id=run_id,
            account_id=decision.account_id,
            offer_id=decision.offer_id,
            position_id=decision.position_id,
            outcome=fields.pop("outcome", "queued" if decision.queued else "skipped"),
            decision=decision.reason,
            daily_limit=self.daily_limit,
            batch_limit=self.batch_limit,
            batch_pause_seconds=self.batch_pause_seconds,
            **fields,
        )

    @staticmethod
    def _requires_settlement(decision: SendDecision) -> bool:
        return decision.allowed and decision.reason == "reserved"

    @staticmethod
    async def _run_blocking(function, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(function, *args, **kwargs)
        )
