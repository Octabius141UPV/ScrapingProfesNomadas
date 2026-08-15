"""Offline regression coverage for the scraper command entry point."""

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_PATH = PROJECT_ROOT / "run.py"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"


def load_run_module():
    spec = importlib.util.spec_from_file_location("run_entrypoint_test", RUN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunEntrypointTests(unittest.TestCase):
    def test_requirements_declares_aiohttp_as_direct_dependency(self):
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()

        self.assertIn("aiohttp>=3.8.0,<4.0.0", requirements)

    def test_requirements_declares_pymupdf_for_each_supported_python_line(self):
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()

        self.assertIn(
            'PyMuPDF>=1.24.11,<1.24.12; python_version >= "3.8" and python_version < "3.9"',
            requirements,
        )
        self.assertIn(
            'PyMuPDF>=1.26.1,<1.27.0; python_version >= "3.9"',
            requirements,
        )

    def test_document_reader_uses_declared_fitz_dependency_not_pdf2image(self):
        source = (PROJECT_ROOT / "src/utils/document_reader.py").read_text(encoding="utf-8")

        self.assertIn("import fitz", source)
        self.assertNotIn("from pdf2image import convert_from_path", source)

    def test_missing_aiohttp_keeps_the_real_dependency_diagnostic(self):
        run_module = load_run_module()
        missing_aiohttp = ModuleNotFoundError("No module named 'aiohttp'")
        missing_aiohttp.name = "aiohttp"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(run_module, "_load_scrape_main", side_effect=missing_aiohttp):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = run_module.run()

        self.assertEqual(1, exit_code)
        self.assertIn("No module named 'aiohttp'", stdout.getvalue())
        self.assertIn("ModuleNotFoundError", stderr.getvalue())
        self.assertIn("No module named 'aiohttp'", stderr.getvalue())
        self.assertNotIn("No se pudo encontrar 'scrape_all_safe.py'", stdout.getvalue())

    def test_missing_fitz_keeps_the_real_dependency_diagnostic(self):
        run_module = load_run_module()
        missing_fitz = ModuleNotFoundError("No module named 'fitz'")
        missing_fitz.name = "fitz"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(run_module, "_load_scrape_main", side_effect=missing_fitz):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = run_module.run()

        self.assertEqual(1, exit_code)
        self.assertIn("No module named 'fitz'", stdout.getvalue())
        self.assertIn("ModuleNotFoundError", stderr.getvalue())
        self.assertIn("No module named 'fitz'", stderr.getvalue())
        self.assertNotIn("No se pudo encontrar 'scrape_all_safe.py'", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
