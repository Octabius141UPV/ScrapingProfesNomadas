"""Offline integration coverage for delivery safety entry points.

Every network-capable dependency is replaced with an in-process fake. These tests
must never contact Google, Gmail, Telegram, Firebase, or EducationPosts.
"""

import asyncio
import contextlib
import importlib
import io
import os
import sys
import tempfile
import threading
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


class ModuleSandbox:
    def __init__(self):
        self._original = {}

    def install(self, name, module):
        if name not in self._original:
            self._original[name] = sys.modules.get(name)
        sys.modules[name] = module

    def remove(self, name):
        if name not in self._original:
            self._original[name] = sys.modules.get(name)
        sys.modules.pop(name, None)

    def restore(self):
        for name, original in reversed(list(self._original.items())):
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def install_dotenv_and_firebase_stubs(sandbox):
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: False
    sandbox.install("dotenv", dotenv)

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
    sandbox.install("firebase_admin", firebase_admin)
    sandbox.install("firebase_admin.credentials", credentials)
    sandbox.install("firebase_admin.firestore", firestore)
    sandbox.install("firebase_admin.storage", storage)


def import_email_sender(sandbox):
    install_dotenv_and_firebase_stubs(sandbox)
    pdf = types.ModuleType("PyPDF2")
    pdf.PdfReader = object
    sandbox.install("PyPDF2", pdf)
    sandbox.remove("src.utils.firebase_manager")
    sandbox.remove("src.utils.application_send_policy")
    sandbox.remove("src.generators.email_sender")
    with patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": ""}, clear=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return importlib.import_module("src.generators.email_sender")


class FakeAsyncPolicy:
    def __init__(self, batch_limit=2, delay_seconds=0):
        self.batch_limit = batch_limit
        self.delay_seconds = delay_seconds
        self.reserve_calls = []
        self.batch_skips = []
        self.smtp_results = []

    async def reserve_async(self, **kwargs):
        self.reserve_calls.append(kwargs)
        return SimpleNamespace(
            allowed=True,
            reason="test_mode_exempt",
            account_id="account_test",
            recipient_id="recipient_test",
            offer_id="offer_test",
            delay_seconds=self.delay_seconds,
        )

    async def record_batch_skip_async(self, **kwargs):
        self.batch_skips.append(kwargs)

    async def record_smtp_result_async(self, *args, **kwargs):
        self.smtp_results.append((args, kwargs))

    async def mark_sent_async(self, *args, **kwargs):
        return None

    async def release_after_definite_failure_async(self, *args, **kwargs):
        return None


class EmailSenderSafetyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sandbox = ModuleSandbox()
        self.addCleanup(self.sandbox.restore)
        self.email_module = import_email_sender(self.sandbox)

    async def test_test_email_uses_policy_spacing_and_never_reserves_production(self):
        sender = self.email_module.EmailSender.__new__(self.email_module.EmailSender)
        sender.email_address = None
        sender.email_password = None
        sender.send_policy = FakeAsyncPolicy(batch_limit=2, delay_seconds=1)
        sender._batch_id = "test-run"
        sender._batch_attempt_count = 0
        sender._last_smtp_error_category = None
        sender._last_smtp_failure_is_definite = False
        sender._send_email = AsyncMock(return_value=True)

        with patch.object(self.email_module.asyncio, "sleep", new=AsyncMock()) as sleep:
            result = await sender.send_test_email(
                "test-recipient@example.com",
                email_address="candidate@example.com",
                email_password="app-password",
                offer={"id": "offer-1"},
            )

        self.assertTrue(result)
        self.assertEqual(1, sender._batch_attempt_count)
        self.assertEqual(True, sender.send_policy.reserve_calls[0]["test_mode"])
        self.assertEqual("candidate@example.com", sender.send_policy.reserve_calls[0]["account_email"])
        sleep.assert_awaited_once_with(1)
        self.assertEqual(1, len(sender.send_policy.smtp_results))


class ScraperTestBranchIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sandbox = ModuleSandbox()
        self.addCleanup(self.sandbox.restore)
        install_dotenv_and_firebase_stubs(self.sandbox)

        scraper_module = types.ModuleType("src.scrapers.scraper_educationposts")

        class EducationPosts:
            def __init__(self, *args, **kwargs):
                pass

            async def fetch_all(self):
                return [
                    {"id": "offer-1", "email": "school-1@example.ie"},
                    {"id": "offer-2", "email": "school-2@example.ie"},
                    {"id": "offer-3", "email": "school-3@example.ie"},
                ]

        scraper_module.EducationPosts = EducationPosts
        self.sandbox.install("src.scrapers.scraper_educationposts", scraper_module)

        bot_module = types.ModuleType("src.bots.telegram_bot")
        bot_module.TelegramBot = object
        self.sandbox.install("src.bots.telegram_bot", bot_module)
        logger_module = types.ModuleType("src.utils.logger")
        logger_module.setup_logger = lambda *args, **kwargs: None
        self.sandbox.install("src.utils.logger", logger_module)
        reader_module = types.ModuleType("src.utils.document_reader")
        reader_module.DocumentReader = object
        self.sandbox.install("src.utils.document_reader", reader_module)

        self.sender_instances = []
        email_module = types.ModuleType("src.generators.email_sender")

        class EmailSender:
            def __init__(instance):
                instance.send_policy = SimpleNamespace(
                    batch_limit=2,
                    batch_pause_seconds=0,
                )
                instance.send_test_email = AsyncMock(return_value=True)
                instance._last_application_send_reason = "sent"
                instance._last_smtp_error_category = None
                self.sender_instances.append(instance)

        email_module.EmailSender = EmailSender
        self.sandbox.install("src.generators.email_sender", email_module)
        ai_module = types.ModuleType("src.generators.ai_email_generator_v2")
        ai_module.AIEmailGeneratorV2 = object
        self.sandbox.install("src.generators.ai_email_generator_v2", ai_module)
        self.sandbox.remove("scripts.scrape_all_safe")
        self.script = importlib.import_module("scripts.scrape_all_safe")

    async def test_test_branch_chains_batches_and_passes_test_credentials(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as form:
            form_path = form.name
        self.addCleanup(lambda: os.path.exists(form_path) and os.unlink(form_path))
        self.script.generate_application_forms_from_offers = AsyncMock(
            return_value=[{"file_path": form_path}] * 3
        )
        user_data = {
            "name": "Candidate",
            "email": "candidate@example.com",
            "email_password": "app-password",
            "application_form": form_path,
            "county_selection": "all",
            "test_mode": True,
        }
        with patch.dict("os.environ", {"EMAIL_ADDRESS": "test-recipient@example.com"}, clear=False):
            result = await self.script.process_user_request_with_county(user_data)

        sender = self.sender_instances[0]
        self.assertEqual(3, sender.send_test_email.await_count)
        self.assertEqual(3, result["total_offers"])
        self.assertEqual(0, result["skipped_by_queue"])
        first_call = sender.send_test_email.await_args_list[0].kwargs
        self.assertEqual("candidate@example.com", first_call["email_address"])
        self.assertEqual("app-password", first_call["email_password"])
        self.assertEqual("offer-1", first_call["offer"]["id"])
        self.assertTrue(first_call["queue_managed"])


def install_telegram_bot_stubs(sandbox):
    install_dotenv_and_firebase_stubs(sandbox)
    sandbox.install("aiofiles", types.ModuleType("aiofiles"))

    telegram = types.ModuleType("telegram")
    telegram.Update = type("Update", (), {})
    telegram.InlineKeyboardButton = type("InlineKeyboardButton", (), {})
    telegram.InlineKeyboardMarkup = type("InlineKeyboardMarkup", (), {})
    sandbox.install("telegram", telegram)
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.Application = type("Application", (), {})
    telegram_ext.CommandHandler = type("CommandHandler", (), {})
    telegram_ext.MessageHandler = type("MessageHandler", (), {})
    telegram_ext.CallbackQueryHandler = type("CallbackQueryHandler", (), {})
    telegram_ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    telegram_ext.filters = SimpleNamespace()
    sandbox.install("telegram.ext", telegram_ext)

    for name, attribute in (
        ("src.utils.document_reader", "DocumentReader"),
        ("src.utils.pdf_generator", "PDFGenerator"),
        ("src.utils.document_validator", "DocumentValidator"),
        ("src.scrapers.scraper_educationposts", "EducationPosts"),
        ("src.generators.email_sender", "EmailSender"),
    ):
        module = types.ModuleType(name)
        setattr(module, attribute, type(attribute, (), {}))
        sandbox.install(name, module)

    firebase_module = types.ModuleType("src.utils.firebase_manager")
    for name in (
        "get_applied_vacancies",
        "mark_vacancy_as_applied",
        "upload_file_to_storage",
        "get_presentation_recipients",
        "mark_presentation_sent",
    ):
        setattr(firebase_module, name, lambda *args, **kwargs: None)
    sandbox.install("src.utils.firebase_manager", firebase_module)
    policy_module = types.ModuleType("src.utils.application_send_policy")
    policy_module.ApplicationSendPolicy = type("ApplicationSendPolicy", (), {})
    policy_module.QueueDecision = type("QueueDecision", (), {})
    sandbox.install("src.utils.application_send_policy", policy_module)
    sandbox.remove("src.utils.application_delivery_queue")
    sandbox.remove("src.bots.telegram_bot")
    return importlib.import_module("src.bots.telegram_bot")


class TelegramExecutorIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sandbox = ModuleSandbox()
        self.addCleanup(self.sandbox.restore)
        self.bot_module = install_telegram_bot_stubs(self.sandbox)

    async def test_smtp_and_application_recording_are_offloaded_from_event_loop(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as form:
            form_path = form.name
        self.addCleanup(lambda: os.path.exists(form_path) and os.unlink(form_path))
        event_loop_thread = threading.get_ident()
        smtp_threads = []
        firestore_threads = []

        def smtp_sender(*args):
            smtp_threads.append(threading.get_ident())
            return True, None, False

        def mark_application(*args, **kwargs):
            firestore_threads.append(threading.get_ident())

        self.bot_module.mark_vacancy_as_applied = mark_application
        user = SimpleNamespace(
            email="candidate@example.com",
            test_mode=False,
            education_level="primary",
            teaching_council_registration=None,
            tc_route=None,
            name="Candidate",
            documents={},
        )
        policy = FakeAsyncPolicy()
        fake_bot = SimpleNamespace(
            user_data={1: user},
            send_policy=policy,
            logger=MagicMock(),
            generate_application_form=AsyncMock(return_value=form_path),
            get_required_attachments=lambda *args: [],
            _get_tc_info=lambda *args: "",
            _send_application_smtp_message=smtp_sender,
            _last_application_send_reason=None,
        )
        offer = {"id": "offer-1", "email": "school@example.ie", "position": "Teacher"}

        result = await self.bot_module.TelegramBot.send_application_email_for_offer(
            fake_bot,
            offer,
            "candidate@example.com",
            "app-password",
            run_id="test-run",
        )

        self.assertTrue(result)
        self.assertEqual([True], [entry[1]["success"] for entry in policy.smtp_results])
        self.assertNotEqual(event_loop_thread, smtp_threads[0])
        self.assertNotEqual(event_loop_thread, firestore_threads[0])


if __name__ == "__main__":
    unittest.main()
