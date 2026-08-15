"""In-memory worker for a persistent, privacy-safe application delivery queue.

Firestore retains only queue lifecycle metadata. The candidate credentials,
email body, and attachment paths remain exclusively in the authenticated
in-memory process that owns the SMTP session.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Iterable, Optional

from src.utils.application_send_policy import QueueDecision


@dataclass(frozen=True)
class DeliveryAttempt:
    """Result returned by a local SMTP delivery callback."""

    success: bool
    reason: str
    error_category: Optional[str] = None


@dataclass(frozen=True)
class QueueRunResult:
    """Aggregate result of the current authenticated delivery session."""

    queued_count: int
    sent_count: int
    skipped_count: int
    deferred_daily_limit: bool
    stopped_reason: Optional[str]


class ApplicationDeliveryQueue:
    """Drain persisted production metadata in batches from a live local session."""

    _AMBIGUOUS_REASONS = {
        "smtp_delivery_indeterminate",
        "smtp_unexpected_error",
    }

    def __init__(
        self,
        *,
        policy,
        account_email: str,
        run_id: str,
        test_mode: bool,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.policy = policy
        self.account_email = account_email
        self.run_id = run_id
        self.test_mode = test_mode
        self._sleep = sleep

    async def enqueue(self, offers: Iterable[Dict]):
        """Persist production queue metadata or retain test items locally only."""
        items = []
        skipped_count = 0
        for offer in offers:
            if self.test_mode:
                items.append((offer, None))
                continue
            decision = await self.policy.enqueue_async(
                account_email=self.account_email,
                recipient_email=offer.get("email", ""),
                offer=offer,
                run_id=self.run_id,
            )
            if decision.queued:
                items.append((offer, decision))
            else:
                skipped_count += 1
        return items, skipped_count

    async def drain(
        self,
        items,
        send_attempt: Callable[[Dict], Awaitable[DeliveryAttempt]],
        *,
        on_batch_pause: Optional[Callable[[int], Awaitable[None]]] = None,
    ) -> QueueRunResult:
        """Send queued items sequentially while applying batch pauses safely."""
        sent_count = 0
        skipped_count = 0
        deferred_daily_limit = False
        stopped_reason = None
        index = 0
        batch_number = 1

        while index < len(items):
            attempts_in_batch = 0
            while index < len(items) and attempts_in_batch < self.policy.batch_limit:
                offer, queue_decision = items[index]
                index += 1

                if not self.test_mode:
                    claim = await self.policy.claim_queue_item_async(
                        queue_decision, self.run_id, batch_number
                    )
                    if not claim.queued:
                        skipped_count += 1
                        continue
                    queue_decision = claim

                outcome = await send_attempt(offer)
                if outcome.reason == "daily_limit_reached":
                    deferred_daily_limit = True
                    stopped_reason = outcome.reason
                    if not self.test_mode:
                        await self.policy.set_queue_item_status_async(
                            queue_decision,
                            self.run_id,
                            status="queued",
                            reason="daily_limit_reached",
                            batch_number=batch_number,
                        )
                    break

                # A local delivery callback is reached only after the item has a
                # turn in the current queue. Count known failures too: SMTP was
                # attempted or safely rejected during preflight.
                attempts_in_batch += 1
                if outcome.success:
                    sent_count += 1
                    status = "sent"
                else:
                    skipped_count += 1
                    if outcome.reason.startswith("duplicate_"):
                        status = "deduplicated"
                    elif outcome.reason in self._AMBIGUOUS_REASONS:
                        status = "blocked_ambiguous"
                    else:
                        status = "failed_definite"

                if not self.test_mode:
                    await self.policy.set_queue_item_status_async(
                        queue_decision,
                        self.run_id,
                        status=status,
                        reason=outcome.reason,
                        error_category=outcome.error_category,
                        batch_number=batch_number,
                    )

                # Retrying bad credentials across every queued vacancy is unsafe
                # operationally. The released item is persisted as a known failure
                # and the remaining items stay queued for a fresh authenticated run.
                if outcome.reason == "smtp_authentication_failed":
                    stopped_reason = outcome.reason
                    break

            if deferred_daily_limit or stopped_reason:
                break
            if index < len(items) and attempts_in_batch:
                if not self.test_mode:
                    await self.policy.record_batch_pause_async(
                        self.run_id, self.account_email, batch_number
                    )
                if on_batch_pause:
                    await on_batch_pause(batch_number)
                if self.policy.batch_pause_seconds:
                    await self._sleep(self.policy.batch_pause_seconds)
                batch_number += 1
            elif index < len(items):
                # Avoid an accidental hot loop when every remaining item was
                # concurrently claimed by another process.
                break

        return QueueRunResult(
            queued_count=len(items),
            sent_count=sent_count,
            skipped_count=skipped_count,
            deferred_daily_limit=deferred_daily_limit,
            stopped_reason=stopped_reason,
        )
