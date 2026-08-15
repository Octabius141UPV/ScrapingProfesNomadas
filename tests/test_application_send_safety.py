"""Offline tests for automatic application send controls.

The Firebase SDK is mocked: no Google, Gmail, Telegram, or Firestore call is
made by this test module.
"""

import contextlib
import importlib
import io
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODULES_TO_RESTORE = (
    "dotenv",
    "firebase_admin",
    "firebase_admin.credentials",
    "firebase_admin.firestore",
    "firebase_admin.storage",
    "src.utils.firebase_manager",
    "src.utils.application_send_policy",
)


def save_test_modules():
    return {name: sys.modules.get(name) for name in MODULES_TO_RESTORE}


def restore_test_modules(saved_modules):
    for name, original in saved_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def load_firebase_manager():
    """Import the module with a minimal in-process Firebase SDK replacement."""
    for module_name in list(sys.modules):
        if module_name == "firebase_admin" or module_name.startswith("firebase_admin."):
            del sys.modules[module_name]
    sys.modules.pop("src.utils.firebase_manager", None)

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: False
    sys.modules["dotenv"] = dotenv

    firebase_admin = types.ModuleType("firebase_admin")
    firebase_admin._apps = []
    firebase_admin.initialize_app = lambda *args, **kwargs: None
    credentials = types.ModuleType("firebase_admin.credentials")
    credentials.Certificate = lambda path: object()
    firestore = types.ModuleType("firebase_admin.firestore")
    firestore.transactional = lambda function: function
    firestore.client = lambda: None
    storage = types.ModuleType("firebase_admin.storage")
    storage.bucket = lambda: None
    firebase_admin.credentials = credentials
    firebase_admin.firestore = firestore
    firebase_admin.storage = storage
    sys.modules["firebase_admin"] = firebase_admin
    sys.modules["firebase_admin.credentials"] = credentials
    sys.modules["firebase_admin.firestore"] = firestore
    sys.modules["firebase_admin.storage"] = storage

    with patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": ""}, clear=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return importlib.import_module("src.utils.firebase_manager")


class Snapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class Reference:
    def __init__(self, state, path):
        self.state = state
        self.path = path

    def get(self, transaction=None):
        return Snapshot(self.state.get(self.path))

    def collection(self, name):
        return Collection(self.state, f"{self.path}/{name}")


class Collection:
    def __init__(self, state, path):
        self.state = state
        self.path = path

    def document(self, document_id):
        return Reference(self.state, f"{self.path}/{document_id}")


class Transaction:
    def set(self, reference, payload, merge=False):
        existing = dict(reference.state.get(reference.path, {})) if merge else {}
        existing.update(payload)
        reference.state[reference.path] = existing


class FakeDatabase:
    def __init__(self, state):
        self.state = state

    def collection(self, name):
        return Collection(self.state, name)

    def transaction(self):
        return Transaction()


class CloudAuditIdentifierTests(unittest.TestCase):
    def test_keyed_ids_are_stable_and_domain_separated(self):
        from src.utils.cloud_audit import hash_identifier

        secret = "0123456789abcdef0123456789abcdef"
        self.assertEqual(
            hash_identifier("Teacher@example.com", secret, "account"),
            hash_identifier("teacher@example.com", secret, "account"),
        )
        self.assertNotEqual(
            hash_identifier("teacher@example.com", secret, "account"),
            hash_identifier("teacher@example.com", secret, "recipient"),
        )
        self.assertNotEqual(
            hash_identifier("Teacher", secret, "position"),
            hash_identifier("Teacher", secret, "offer"),
        )
        self.assertIsNone(hash_identifier("teacher@example.com", None, "account"))

    def test_cloud_audit_is_disabled_without_hash_key(self):
        from src.utils.cloud_audit import CloudAuditLogger

        audit = CloudAuditLogger(
            {
                "GOOGLE_CLOUD_AUDIT_LOGGING_ENABLED": "true",
                "APPLICATION_AUDIT_ENVIRONMENT": "test",
            }
        )
        self.assertFalse(audit.cloud_enabled)

    def test_short_and_placeholder_hash_keys_are_rejected(self):
        from src.utils.cloud_audit import CloudAuditLogger

        for secret in ("too-short", "replace_with_a_long_random_secret"):
            audit = CloudAuditLogger(
                {
                    "GOOGLE_CLOUD_AUDIT_LOGGING_ENABLED": "true",
                    "APPLICATION_AUDIT_HASH_KEY": secret,
                }
            )
            self.assertFalse(audit.cloud_enabled)
            self.assertIsNone(audit.account_id("candidate@example.com"))

    def test_audit_omits_host_without_an_explicit_deployment_label(self):
        from src.utils import cloud_audit

        audit = cloud_audit.CloudAuditLogger(
            {
                "APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef",
                "APPLICATION_AUDIT_ENVIRONMENT": "test",
            }
        )
        with patch.object(cloud_audit.logger, "log") as write_log:
            audit.emit("application_send_run_started", run_id="test-run")

        payload = json.loads(write_log.call_args.args[2])
        self.assertNotIn("host", payload)

    def test_queue_audit_accepts_hmac_position_and_rejects_unknown_fields(self):
        from src.utils import cloud_audit

        audit = cloud_audit.CloudAuditLogger(
            {"APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef"}
        )
        with patch.object(cloud_audit.logger, "log") as write_log:
            audit.emit(
                "application_send_queue_transition",
                position_id="position_abc",
                batch_number=2,
                password="must-not-be-logged",
            )

        payload = json.loads(write_log.call_args.args[2])
        self.assertEqual("position_abc", payload["position_id"])
        self.assertEqual(2, payload["batch_number"])
        self.assertNotIn("password", payload)




class ApplicationSendPolicyTests(unittest.TestCase):
    def test_queue_defaults_match_operational_delivery_policy(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {"APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef"}
            )

            self.assertEqual(100, policy.daily_limit)
            self.assertEqual(10, policy.batch_limit)
            self.assertEqual(10, policy.min_interval_seconds)
            self.assertEqual(300, policy.batch_pause_seconds)
        finally:
            restore_test_modules(saved_modules)

    def test_production_configuration_clamps_unsafe_delivery_values(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {
                    "APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef",
                    "APPLICATION_AUDIT_ENVIRONMENT": "production",
                    "APPLICATION_DELIVERY_TEST_MODE": "true",
                    "APPLICATION_SEND_DAILY_LIMIT": "1000",
                    "APPLICATION_SEND_BATCH_LIMIT": "99",
                    "APPLICATION_SEND_MIN_INTERVAL_SECONDS": "0",
                    "APPLICATION_SEND_BATCH_PAUSE_SECONDS": "1",
                }
            )

            self.assertEqual(100, policy.daily_limit)
            self.assertEqual(10, policy.batch_limit)
            self.assertEqual(10, policy.min_interval_seconds)
            self.assertEqual(300, policy.batch_pause_seconds)
        finally:
            restore_test_modules(saved_modules)

    def test_test_only_configuration_can_use_fast_offline_values(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {
                    "APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef",
                    "APPLICATION_AUDIT_ENVIRONMENT": "test",
                    "APPLICATION_SEND_DAILY_LIMIT": "2",
                    "APPLICATION_SEND_BATCH_LIMIT": "2",
                    "APPLICATION_SEND_MIN_INTERVAL_SECONDS": "1",
                    "APPLICATION_SEND_BATCH_PAUSE_SECONDS": "0",
                }
            )

            self.assertEqual(2, policy.daily_limit)
            self.assertEqual(2, policy.batch_limit)
            self.assertEqual(1, policy.min_interval_seconds)
            self.assertEqual(0, policy.batch_pause_seconds)
        finally:
            restore_test_modules(saved_modules)

    def test_production_safety_flag_cannot_bypass_reservation_or_queue(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {
                    "APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef",
                    "APPLICATION_AUDIT_ENVIRONMENT": "production",
                    "APPLICATION_SAFETY_ENABLED": "false",
                }
            )
            with patch.object(
                policy_module,
                "reserve_application_send",
                return_value={
                    "allowed": False,
                    "reason": "policy_store_unavailable",
                    "delay_seconds": 0,
                },
            ) as reserve, patch.object(
                policy_module,
                "enqueue_application_send_queue_item",
                return_value={"queued": False, "reason": "policy_store_unavailable"},
            ) as enqueue:
                reservation = policy.reserve(
                    account_email="candidate@example.com",
                    recipient_email="school@example.ie",
                    offer={"id": "offer-1"},
                    run_id="test-run",
                    test_mode=False,
                )
                queued = policy.enqueue(
                    account_email="candidate@example.com",
                    recipient_email="school@example.ie",
                    offer={"id": "offer-1"},
                    run_id="test-run",
                )

            reserve.assert_called_once()
            enqueue.assert_called_once()
            self.assertFalse(reservation.allowed)
            self.assertEqual("policy_store_unavailable", reservation.reason)
            self.assertFalse(queued.queued)
            self.assertEqual("policy_store_unavailable", queued.reason)
        finally:
            restore_test_modules(saved_modules)

    def test_missing_hash_secret_fails_closed_before_any_firestore_call(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {
                    "APPLICATION_AUDIT_ENVIRONMENT": "test",
                }
            )

            decision = policy.reserve(
                account_email="candidate@example.com",
                recipient_email="school@example.ie",
                offer={"id": "offer-1"},
                run_id="test-run",
                test_mode=False,
            )

            self.assertFalse(decision.allowed)
            self.assertEqual("safety_hash_key_missing", decision.reason)
        finally:
            restore_test_modules(saved_modules)

    def test_test_mode_keeps_local_spacing_without_firestore_reservation(self):
        saved_modules = save_test_modules()
        try:
            load_firebase_manager()
            sys.modules.pop("src.utils.application_send_policy", None)
            policy_module = importlib.import_module("src.utils.application_send_policy")
            policy = policy_module.ApplicationSendPolicy(
                {
                    "APPLICATION_AUDIT_HASH_KEY": "0123456789abcdef0123456789abcdef",
                    "APPLICATION_SEND_MIN_INTERVAL_SECONDS": "1",
                    "APPLICATION_AUDIT_ENVIRONMENT": "test",
                }
            )
            first = policy.reserve(
                account_email="candidate@example.com",
                recipient_email="test@example.com",
                offer={"id": "offer-1"},
                run_id="test-run",
                test_mode=True,
            )
            second = policy.reserve(
                account_email="candidate@example.com",
                recipient_email="test@example.com",
                offer={"id": "offer-2"},
                run_id="test-run",
                test_mode=True,
            )
            self.assertEqual("test_mode_exempt", first.reason)
            self.assertEqual(0, first.delay_seconds)
            self.assertGreaterEqual(second.delay_seconds, 1)
        finally:
            restore_test_modules(saved_modules)

class FirestoreReservationTransactionTests(unittest.TestCase):
    def setUp(self):
        self._saved_modules = save_test_modules()
        self.addCleanup(restore_test_modules, self._saved_modules)
        self.manager = load_firebase_manager()
        self.state = {}
        self.transaction = Transaction()
        self.account = Reference(self.state, "account")
        self.daily = Reference(self.state, "account/days/2026-08-15")
        self.reservation = Reference(self.state, "reservation/offer-a")
        self.now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

    def reserve(self, reservation=None, daily_limit=2, now=None, batch_limit=10):
        return self.manager._reserve_application_send_transaction(
            self.transaction,
            self.account,
            reservation or self.reservation,
            daily_limit=daily_limit,
            min_interval_seconds=30,
            batch_limit=batch_limit,
            batch_pause_seconds=300,
            now=now or self.now,
        )

    def test_reservation_is_atomic_and_blocks_duplicate_then_daily_limit(self):
        first = self.reserve()
        self.assertEqual({"allowed": True, "reason": "reserved", "delay_seconds": 0}, first)
        self.assertEqual(1, self.state["account/days/2026-08-15"]["pending_count"])

        duplicate = self.reserve()
        self.assertEqual("duplicate_pending_review", duplicate["reason"])
        self.assertEqual(1, self.state["account/days/2026-08-15"]["pending_count"])

        finalized = self.manager._finalize_application_send_transaction(
            self.transaction, self.daily, self.reservation, now=self.now
        )
        self.assertEqual("finalized", finalized["reason"])
        self.assertEqual("sent", self.state["reservation/offer-a"]["status"])
        self.assertEqual(1, self.state["account/days/2026-08-15"]["sent_count"])

        different_offer = Reference(self.state, "reservation/offer-b")
        blocked = self.reserve(reservation=different_offer, daily_limit=1)
        self.assertEqual("daily_limit_reached", blocked["reason"])

    def test_definite_failure_release_makes_the_offer_retriable(self):
        self.reserve()
        released = self.manager._release_application_send_transaction(
            self.transaction,
            self.daily,
            self.reservation,
            now=self.now,
            error_category="smtp_authentication_failed",
        )
        self.assertEqual("released", released["reason"])
        self.assertEqual(0, self.state["account/days/2026-08-15"]["pending_count"])

        retried = self.reserve()
        self.assertTrue(retried["allowed"])
        self.assertEqual("reserved", self.state["reservation/offer-a"]["status"])

    def test_fractional_wait_rounds_up_to_avoid_under_waiting(self):
        self.state["account"] = {
            "next_available_at": self.now + timedelta(milliseconds=100)
        }
        result = self.reserve(reservation=Reference(self.state, "reservation/offer-b"))
        self.assertEqual(1, result["delay_seconds"])

    def test_settlement_uses_scheduled_delivery_day_across_midnight(self):
        state = {}
        self.manager.db = FakeDatabase(state)
        before_midnight = datetime(2026, 8, 15, 23, 59, 59, tzinfo=timezone.utc)
        after_midnight = datetime(2026, 8, 16, 0, 1, tzinfo=timezone.utc)

        first = self.manager.reserve_application_send(
            account_id="account_a",
            offer_id="offer_a",
            daily_limit=2,
            min_interval_seconds=30,
            batch_limit=10,
            batch_pause_seconds=300,
            now=before_midnight,
        )
        second = self.manager.reserve_application_send(
            account_id="account_a",
            offer_id="offer_b",
            daily_limit=2,
            min_interval_seconds=30,
            batch_limit=10,
            batch_pause_seconds=300,
            now=before_midnight,
        )
        self.assertTrue(first["allowed"])
        self.assertTrue(second["allowed"])

        finalized = self.manager.finalize_application_send_reservation(
            "account_a", "offer_a", now=after_midnight
        )
        released = self.manager.release_application_send_reservation(
            "account_a",
            "offer_b",
            now=after_midnight,
            error_category="smtp_authentication_failed",
        )

        day_15 = "application_send_safety/account_a/days/2026-08-15"
        day_16 = "application_send_safety/account_a/days/2026-08-16"
        self.assertEqual("finalized", finalized["reason"])
        self.assertEqual("released", released["reason"])
        self.assertEqual(1, state[day_15]["sent_count"])
        self.assertEqual(0, state[day_15]["pending_count"])
        self.assertEqual(0, state[day_16]["pending_count"])

    def test_scheduled_delivery_day_caps_each_utc_day_across_midnight(self):
        state = {}
        self.manager.db = FakeDatabase(state)
        just_before_midnight = datetime(2026, 8, 15, 23, 59, 50, tzinfo=timezone.utc)
        kwargs = {
            "account_id": "account_a",
            "daily_limit": 2,
            "min_interval_seconds": 10,
            "batch_limit": 10,
            "batch_pause_seconds": 300,
            "now": just_before_midnight,
        }

        first = self.manager.reserve_application_send(offer_id="offer_a", **kwargs)
        second = self.manager.reserve_application_send(offer_id="offer_b", **kwargs)
        third = self.manager.reserve_application_send(offer_id="offer_c", **kwargs)
        blocked = self.manager.reserve_application_send(offer_id="offer_d", **kwargs)

        day_15 = "application_send_safety/account_a/days/2026-08-15"
        day_16 = "application_send_safety/account_a/days/2026-08-16"
        reservation_a = "application_send_safety/account_a/reservations/offer_a"
        reservation_b = "application_send_safety/account_a/reservations/offer_b"
        self.assertTrue(first["allowed"])
        self.assertTrue(second["allowed"])
        self.assertTrue(third["allowed"])
        self.assertEqual("daily_limit_reached", blocked["reason"])
        self.assertEqual("2026-08-15", state[reservation_a]["delivery_day"])
        self.assertEqual("2026-08-16", state[reservation_b]["delivery_day"])
        self.assertEqual(1, state[day_15]["pending_count"])
        self.assertEqual(2, state[day_16]["pending_count"])

    def test_batch_cooldown_is_persisted_and_shared_by_workers(self):
        state = {}
        account = Reference(state, "account")
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        for index in range(10):
            result = self.manager._reserve_application_send_transaction(
                Transaction(),
                account,
                Reference(state, f"reservation/{index}"),
                daily_limit=100,
                min_interval_seconds=10,
                batch_limit=10,
                batch_pause_seconds=300,
                now=now,
            )
            self.assertTrue(result["allowed"])

        # A separate worker transaction sees the account-level state and must
        # schedule only after the completed batch's durable cooldown.
        next_worker = self.manager._reserve_application_send_transaction(
            Transaction(),
            account,
            Reference(state, "reservation/next"),
            daily_limit=100,
            min_interval_seconds=10,
            batch_limit=10,
            batch_pause_seconds=300,
            now=now,
        )
        self.assertEqual(390, next_worker["delay_seconds"])
        self.assertEqual(1, state["account"]["batch_count"])

    def test_queue_metadata_persists_without_smtp_material_and_rebinds_safely(self):
        queue = Reference(self.state, "queue/offer-a")
        first = self.manager._enqueue_application_send_queue_item_transaction(
            self.transaction,
            queue,
            run_id="run-a",
            position_id="position_a",
            now=self.now,
        )
        self.assertEqual({"queued": True, "reason": "queued"}, first)
        self.assertEqual("queued", self.state["queue/offer-a"]["status"])
        self.assertNotIn("password", self.state["queue/offer-a"])
        self.assertNotIn("recipient", self.state["queue/offer-a"])
        self.assertNotIn("body", self.state["queue/offer-a"])

        # A fresh process reading the same durable state may re-bind only a
        # still-queued item to a newly authenticated in-memory session.
        resumed = self.manager._enqueue_application_send_queue_item_transaction(
            self.transaction,
            queue,
            run_id="run-b",
            position_id="position_a",
            now=self.now + timedelta(minutes=5),
        )
        self.assertEqual({"queued": True, "reason": "queue_existing"}, resumed)

        claimed = self.manager._claim_application_send_queue_item_transaction(
            self.transaction,
            queue,
            run_id="run-b",
            batch_number=1,
            now=self.now + timedelta(minutes=5),
        )
        self.assertEqual({"claimed": True, "reason": "claimed"}, claimed)
        blocked_restart = self.manager._enqueue_application_send_queue_item_transaction(
            self.transaction,
            queue,
            run_id="run-c",
            position_id="position_a",
            now=self.now + timedelta(minutes=6),
        )
        self.assertEqual(
            {"queued": False, "reason": "duplicate_pending_review"}, blocked_restart
        )


if __name__ == "__main__":
    unittest.main()
