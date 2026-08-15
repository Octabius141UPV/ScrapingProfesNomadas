"""Privacy-safe audit events for automated application delivery.

Cloud Logging is deliberately opt-in. Local structured logs are always emitted, but
never contain raw email addresses, email content, credentials, or filenames.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

MIN_AUDIT_HASH_KEY_LENGTH = 32
KNOWN_INSECURE_HASH_KEYS = {
    "replace_with_a_long_random_secret",
    "change-me",
    "changeme",
    "your-secret",
    "your_secret",
    "secret",
    "password",
}


def env_flag(value: Optional[str], default: bool = False) -> bool:
    """Return a predictable boolean value for an environment variable."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_secure_hash_key(secret: Optional[str]) -> bool:
    """Require a real, sufficiently strong secret for pseudonymous IDs."""
    if not secret:
        return False
    normalized = secret.strip()
    if len(normalized) < MIN_AUDIT_HASH_KEY_LENGTH:
        return False
    lower = normalized.lower()
    return not (
        lower in KNOWN_INSECURE_HASH_KEYS
        or lower.startswith("replace_with_")
        or lower.startswith("your_")
        or lower.startswith("example_")
    )


def hash_identifier(value: str, secret: Optional[str], label: str) -> Optional[str]:
    """Return a non-reversible, domain-separated identifier, or ``None``.

    A plain hash is intentionally not used: email addresses are guessable and a
    plain hash would make audit data unnecessarily reversible by enumeration.
    """
    if not value or not is_secure_hash_key(secret):
        return None
    normalized = value.strip().lower().encode("utf-8")
    normalized_secret = secret.strip()
    digest = hmac.new(
        normalized_secret.encode("utf-8"),
        label.encode("utf-8") + b":" + normalized,
        hashlib.sha256,
    ).hexdigest()
    return f"{label}_{digest[:24]}"


class CloudAuditLogger:
    """Emit allow-listed, privacy-safe send events to local and Cloud Logging."""

    def __init__(self, environ: Optional[Mapping[str, str]] = None):
        self._environ = environ if environ is not None else os.environ
        configured_hash_secret = self._environ.get("APPLICATION_AUDIT_HASH_KEY")
        self.hash_secret = (
            configured_hash_secret.strip()
            if is_secure_hash_key(configured_hash_secret)
            else None
        )
        self.environment = self._environ.get("APPLICATION_AUDIT_ENVIRONMENT", "production")
        configured_host = self._environ.get("APPLICATION_AUDIT_HOST", "").strip()
        # A workstation hostname may contain a person's name, so include a host
        # field only when deployment config explicitly provides a safe label.
        self.host = configured_host or None
        self.cloud_enabled = env_flag(
            self._environ.get("GOOGLE_CLOUD_AUDIT_LOGGING_ENABLED"),
            default=False,
        )
        self._cloud_logger = None
        self._cloud_ready = False

        # Cloud events without a keyed identity would be unsafe and unhelpful.
        if configured_hash_secret and not self.hash_secret:
            logger.warning(
                "APPLICATION_AUDIT_HASH_KEY is rejected; use at least %s random characters.",
                MIN_AUDIT_HASH_KEY_LENGTH,
            )
        if self.cloud_enabled and not self.hash_secret:
            self.cloud_enabled = False
            logger.warning(
                "Cloud audit logging is disabled because APPLICATION_AUDIT_HASH_KEY is missing."
            )

    def account_id(self, email: str) -> Optional[str]:
        return hash_identifier(email, self.hash_secret, "account")

    def recipient_id(self, email: str) -> Optional[str]:
        return hash_identifier(email, self.hash_secret, "recipient")

    def offer_id(self, offer_identity: str) -> Optional[str]:
        return hash_identifier(offer_identity, self.hash_secret, "offer")

    def position_id(self, position_identity: str) -> Optional[str]:
        return hash_identifier(position_identity, self.hash_secret, "position")

    def emit(self, event_type: str, *, severity: str = "INFO", **fields: Any) -> None:
        """Write an allow-listed event locally and, when configured, to Cloud Logging.

        Callers must pass pseudonymous IDs only. Values are normalized to JSON so
        accidental complex objects (which could carry personal data) are not
        serialized by a cloud client.
        """
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": self.environment,
        }
        if self.host:
            event["host"] = self.host
        # Only this schema is accepted. It prevents future callers from
        # accidentally shipping an email, a subject, a body, a password, or an
        # attachment to a log sink.
        allowed_fields = {
            "run_id", "account_id", "recipient_id", "offer_id", "position_id", "outcome",
            "decision", "daily_limit", "batch_limit", "test_mode",
            "delay_seconds", "error_category", "requested_offer_count",
            "eligible_offer_count", "batch_offer_count", "sent_count",
            "skipped_count", "batch_number", "batch_pause_seconds",
            "queue_status", "queue_reason", "queued_count",
        }
        event.update(
            {
                key: value
                for key, value in fields.items()
                if key in allowed_fields and value is not None
            }
        )
        safe_event = self._json_safe(event)
        logger.log(
            getattr(logging, severity.upper(), logging.INFO),
            "application_audit=%s",
            json.dumps(safe_event, sort_keys=True, separators=(",", ":")),
        )

        if not self.cloud_enabled:
            return
        try:
            cloud_logger = self._get_cloud_logger()
            if cloud_logger is not None:
                cloud_logger.log_struct(safe_event, severity=severity.upper())
        except Exception as exc:  # Cloud audit must never interrupt email delivery.
            logger.warning("Cloud audit event was not written (%s).", type(exc).__name__)

    async def emit_async(
        self, event_type: str, *, severity: str = "INFO", **fields: Any
    ) -> None:
        """Run potentially blocking Cloud Logging writes outside an event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(self.emit, event_type, severity=severity, **fields),
        )

    def _get_cloud_logger(self):
        if self._cloud_ready:
            return self._cloud_logger
        self._cloud_ready = True
        try:
            import google.cloud.logging  # Imported lazily: optional at runtime.

            project_id = self._environ.get("GOOGLE_CLOUD_PROJECT")
            client = google.cloud.logging.Client(project=project_id or None)
            log_name = self._environ.get(
                "GOOGLE_CLOUD_AUDIT_LOG_NAME", "profes_nomadas_application_audit"
            )
            self._cloud_logger = client.logger(log_name)
        except Exception as exc:  # Missing package/credentials/API are non-fatal.
            logger.warning("Cloud audit logger was not initialized (%s).", type(exc).__name__)
            self._cloud_logger = None
        return self._cloud_logger

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [CloudAuditLogger._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): CloudAuditLogger._json_safe(item)
                for key, item in value.items()
            }
        return str(value)
