"""Offline tests for the bounded runtime import preflight script."""

import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = PROJECT_ROOT / "scripts/runtime_import_preflight.py"


def load_preflight_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_import_preflight_test", PREFLIGHT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RuntimeImportPreflightTests(unittest.TestCase):
    def test_preflight_checks_only_the_bounded_runtime_import_surface(self):
        preflight = load_preflight_module()
        imported_modules = []
        stderr = io.StringIO()

        def successful_import(module_name):
            imported_modules.append(module_name)
            return object()

        exit_code = preflight.run_preflight(successful_import, stderr)

        self.assertEqual(0, exit_code)
        self.assertEqual(list(preflight.RUNTIME_IMPORTS), imported_modules)
        self.assertEqual(
            ["aiohttp", "fitz", "src.utils.document_reader"], imported_modules
        )
        self.assertIn("Runtime import preflight passed.", stderr.getvalue())

    def test_preflight_reports_each_missing_module_and_returns_nonzero(self):
        preflight = load_preflight_module()
        stderr = io.StringIO()

        def import_with_missing_dependencies(module_name):
            if module_name == "aiohttp":
                error = ModuleNotFoundError("No module named 'aiohttp'")
                error.name = "aiohttp"
                raise error
            if module_name == "fitz":
                error = ModuleNotFoundError("No module named 'fitz'")
                error.name = "fitz"
                raise error
            if module_name == "src.utils.document_reader":
                error = ModuleNotFoundError("No module named 'PIL'")
                error.name = "PIL"
                raise error
            return object()

        exit_code = preflight.run_preflight(import_with_missing_dependencies, stderr)

        self.assertEqual(1, exit_code)
        output = stderr.getvalue()
        self.assertIn("'aiohttp': missing module 'aiohttp'", output)
        self.assertIn("'fitz': missing module 'fitz'", output)
        self.assertIn("'src.utils.document_reader': missing module 'PIL'", output)
        self.assertIn("$VENV/bin/python -m pip install -r requirements.txt", output)

    def test_preflight_adds_project_root_before_importing(self):
        preflight = load_preflight_module()
        stderr = io.StringIO()
        project_root = str(PROJECT_ROOT)
        original_path = list(sys.path)

        try:
            sys.path[:] = [entry for entry in sys.path if entry != project_root]
            exit_code = preflight.run_preflight(lambda _module_name: object(), stderr)

            self.assertEqual(0, exit_code)
            self.assertEqual(project_root, sys.path[0])
        finally:
            sys.path[:] = original_path

    def test_script_entrypoint_runs_the_real_importlib_preflight(self):
        result = subprocess.run(
            [sys.executable, str(PREFLIGHT_PATH)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            self.assertIn("Runtime import preflight passed.", result.stderr)
            return

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("ERROR: runtime import preflight could not import", result.stderr)
        self.assertRegex(result.stderr, r"missing module '[^']+'")
        self.assertIn("runtime import preflight failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
