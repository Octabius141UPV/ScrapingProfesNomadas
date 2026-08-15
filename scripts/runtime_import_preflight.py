#!/usr/bin/env python3
"""Check release-critical imports without starting the application.

Run this with the same interpreter that will run the service, after installing
``requirements.txt``::

    $VENV/bin/python scripts/runtime_import_preflight.py

The check deliberately imports only runtime dependencies and the document
reader.  It never imports an entry point, starts Telegram, or runs a scraper.
"""

import importlib
import sys
from pathlib import Path
from typing import Callable, Optional, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_IMPORTS = (
    "aiohttp",
    "fitz",
    "src.utils.document_reader",
)


def add_project_root_to_path() -> None:
    """Place the repository root first so ``src`` resolves from this checkout."""
    project_root = str(PROJECT_ROOT)
    while project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)


def _missing_module_name(error: ModuleNotFoundError, attempted_module: str) -> str:
    """Return the module name reported by Python, with a useful fallback."""
    return error.name or attempted_module


def run_preflight(
    import_module: Optional[Callable[[str], object]] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """Import the bounded runtime surface and return a shell-friendly status."""
    add_project_root_to_path()
    importer = import_module or importlib.import_module
    error_stream = stderr or sys.stderr
    failures = 0

    for module_name in RUNTIME_IMPORTS:
        try:
            importer(module_name)
        except ModuleNotFoundError as error:
            failures += 1
            missing_module = _missing_module_name(error, module_name)
            print(
                "ERROR: runtime import preflight could not import "
                f"'{module_name}': missing module '{missing_module}' ({error}).",
                file=error_stream,
            )
        except Exception as error:
            failures += 1
            print(
                "ERROR: runtime import preflight could not import "
                f"'{module_name}': {type(error).__name__}: {error}",
                file=error_stream,
            )

    if failures:
        print(
            "ERROR: runtime import preflight failed. Install dependencies with "
            "the target interpreter: $VENV/bin/python -m pip install -r requirements.txt",
            file=error_stream,
        )
        return 1

    print("Runtime import preflight passed.", file=error_stream)
    return 0


if __name__ == "__main__":
    sys.exit(run_preflight())
