"""Offline queue orchestration tests with no Firebase, SMTP, or Telegram access."""

import asyncio
import importlib
import sys
import types
import unittest
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueDecision:
    queued: bool
    reason: str
    account_id: str = "account_a"
    offer_id: str = None
    position_id: str = "position_a"


class FakePolicy:
    def __init__(self, *, batch_limit=2, batch_pause_seconds=3):
        self.batch_limit = batch_limit
        self.batch_pause_seconds = batch_pause_seconds
        self.items = {}
        self.claims = []
        self.transitions = []
        self.pauses = []

    async def enqueue_async(self, *, offer, **kwargs):
        offer_id = offer["id"]
        status = self.items.get(offer_id)
        if status == "sent":
            return QueueDecision(False, "duplicate_already_sent", offer_id=offer_id)
        if status in {"processing", "blocked_ambiguous"}:
            return QueueDecision(False, "duplicate_pending_review", offer_id=offer_id)
        self.items[offer_id] = "queued"
        return QueueDecision(
            True,
            "queue_existing" if status == "queued" else "queued",
            offer_id=offer_id,
        )

    async def claim_queue_item_async(self, decision, run_id, batch_number):
        self.claims.append((decision.offer_id, run_id, batch_number))
        if self.items.get(decision.offer_id) != "queued":
            return QueueDecision(False, "queue_item_not_available", offer_id=decision.offer_id)
        self.items[decision.offer_id] = "processing"
        return QueueDecision(True, "claimed", offer_id=decision.offer_id)

    async def set_queue_item_status_async(self, decision, run_id, **kwargs):
        self.transitions.append((decision.offer_id, kwargs["status"], kwargs["reason"]))
        self.items[decision.offer_id] = kwargs["status"]

    async def record_batch_pause_async(self, run_id, account_email, batch_number):
        self.pauses.append((run_id, account_email, batch_number))


class ApplicationDeliveryQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_policy = sys.modules.get("src.utils.application_send_policy")
        policy_module = types.ModuleType("src.utils.application_send_policy")
        policy_module.QueueDecision = QueueDecision
        sys.modules["src.utils.application_send_policy"] = policy_module
        sys.modules.pop("src.utils.application_delivery_queue", None)
        self.module = importlib.import_module("src.utils.application_delivery_queue")

    def tearDown(self):
        sys.modules.pop("src.utils.application_delivery_queue", None)
        if self._original_policy is None:
            sys.modules.pop("src.utils.application_send_policy", None)
        else:
            sys.modules["src.utils.application_send_policy"] = self._original_policy

    def runner(self, policy, *, test_mode=False, sleep=None):
        return self.module.ApplicationDeliveryQueue(
            policy=policy,
            account_email="candidate@example.com",
            run_id="run-a",
            test_mode=test_mode,
            sleep=sleep or asyncio.sleep,
        )

    async def test_chains_batches_with_pause_and_sequential_attempts(self):
        policy = FakePolicy(batch_limit=2, batch_pause_seconds=3)
        pauses = []
        sent = []

        async def fake_sleep(seconds):
            pauses.append(seconds)

        async def send(offer):
            sent.append(offer["id"])
            return self.module.DeliveryAttempt(True, "sent")

        runner = self.runner(policy, test_mode=True, sleep=fake_sleep)
        items, skipped = await runner.enqueue([{"id": str(index)} for index in range(5)])
        result = await runner.drain(items, send)

        self.assertEqual(0, skipped)
        self.assertEqual(["0", "1", "2", "3", "4"], sent)
        self.assertEqual([3, 3], pauses)
        self.assertEqual(5, result.sent_count)

    async def test_daily_cap_defers_current_and_remaining_items(self):
        policy = FakePolicy(batch_limit=10, batch_pause_seconds=3)
        attempted = []

        async def send(offer):
            attempted.append(offer["id"])
            if offer["id"] == "2":
                return self.module.DeliveryAttempt(False, "daily_limit_reached")
            return self.module.DeliveryAttempt(True, "sent")

        runner = self.runner(policy)
        offers = [{"id": str(index), "email": f"school-{index}@example.ie"} for index in range(4)]
        items, _ = await runner.enqueue(offers)
        result = await runner.drain(items, send)

        self.assertEqual(["0", "1", "2"], attempted)
        self.assertTrue(result.deferred_daily_limit)
        self.assertEqual("queued", policy.items["2"])
        self.assertEqual("queued", policy.items["3"])
        self.assertIn(("2", "queued", "daily_limit_reached"), policy.transitions)

    async def test_dedup_and_smtp_statuses_preserve_safe_lifecycle(self):
        policy = FakePolicy(batch_limit=10)
        policy.items["sent-before"] = "sent"

        async def send(offer):
            if offer["id"] == "known":
                return self.module.DeliveryAttempt(
                    False, "smtp_recipient_rejected", "smtp_recipient_rejected"
                )
            return self.module.DeliveryAttempt(
                False, "smtp_delivery_indeterminate", "smtp_delivery_indeterminate"
            )

        runner = self.runner(policy)
        items, skipped = await runner.enqueue([
            {"id": "sent-before", "email": "a@example.ie"},
            {"id": "known", "email": "b@example.ie"},
            {"id": "ambiguous", "email": "c@example.ie"},
        ])
        result = await runner.drain(items, send)

        self.assertEqual(1, skipped)
        self.assertEqual("failed_definite", policy.items["known"])
        self.assertEqual("blocked_ambiguous", policy.items["ambiguous"])
        self.assertEqual(0, result.sent_count)

    async def test_smtp_authentication_failure_stops_and_leaves_later_items_queued(self):
        policy = FakePolicy(batch_limit=10)
        attempted = []

        async def send(offer):
            attempted.append(offer["id"])
            return self.module.DeliveryAttempt(
                False, "smtp_authentication_failed", "smtp_authentication_failed"
            )

        runner = self.runner(policy)
        items, _ = await runner.enqueue([
            {"id": "first", "email": "first@example.ie"},
            {"id": "later", "email": "later@example.ie"},
        ])
        result = await runner.drain(items, send)

        self.assertEqual(["first"], attempted)
        self.assertEqual("failed_definite", policy.items["first"])
        self.assertEqual("queued", policy.items["later"])
        self.assertEqual("smtp_authentication_failed", result.stopped_reason)

    async def test_restart_rebinds_only_queued_items_in_new_authenticated_session(self):
        policy = FakePolicy()
        first_session = self.runner(policy)
        offers = [{"id": "resume", "email": "school@example.ie"}]
        initial_items, _ = await first_session.enqueue(offers)
        self.assertEqual("queued", policy.items["resume"])

        # The first process exits before sending. The new process supplies the
        # live SMTP material again; it does not get it from persistent storage.
        second_session = self.module.ApplicationDeliveryQueue(
            policy=policy,
            account_email="candidate@example.com",
            run_id="run-b",
            test_mode=False,
            sleep=asyncio.sleep,
        )
        rebound_items, _ = await second_session.enqueue(offers)

        async def send(offer):
            return self.module.DeliveryAttempt(True, "sent")

        result = await second_session.drain(rebound_items, send)
        self.assertEqual(1, len(initial_items))
        self.assertEqual(1, result.sent_count)
        self.assertEqual("sent", policy.items["resume"])


if __name__ == "__main__":
    unittest.main()
