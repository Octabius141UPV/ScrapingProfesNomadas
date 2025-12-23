# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Main package code
  - `scrapers/`: EducationPosts scraper(s)
  - `bots/`: Telegram bot and state handling
  - `utils/`: PDF, logging, Firebase, doc helpers, Notion CRM manager
  - `generators/`: Email generation and sending
- `scripts/`: Orchestration scripts (e.g., `scrape_all_safe.py`, `setup_notion_crm.py`, `manage_notion_crm.py`)
- `tests/`: Pytest tests (e.g., `test_pdf_generation.py`)
- `templates/`: Email templates; `temp/`: working files (PDFs)
- `data/`, `logs/`: Outputs and logs
- `docs/`: Documentation including Notion CRM guides
- Entry points: `run.py` (bot), `scripts/scrape_all_safe.py` (scraper)

## Build, Test, and Development Commands
- Setup env: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt` (then `python -m playwright install` for browsers)
- Run bot: `python run.py`
- Run scraper only: `python scripts/scrape_all_safe.py`
- Run tests: `pytest -q` (single file: `pytest tests/test_pdf_generation.py -q`)

## Coding Style & Naming Conventions
- Python 3.8+, PEP 8, 4-space indentation, descriptive names.
- Files/modules: `snake_case.py`; classes: `CamelCase`; functions/vars: `snake_case`; constants: `UPPER_CASE`.
- Logging: use `logging.getLogger(__name__)` or `src.utils.logger.setup_logger`; avoid `print` in library code.
- Keep scripts idempotent; avoid side effects outside `data/`, `logs/`, `temp/`.

## Testing Guidelines
- Framework: pytest. Tests live in `tests/` and use `test_*.py` naming.
- Prefer fast, offline tests; mock network/Telegram where possible.
- PDF tests expect an Application Form template in `temp/` (e.g., `temp/Application_Form.pdf`).
- No formal coverage target; add tests for new or changed behavior.

## Commit & Pull Request Guidelines
- Commits: imperative mood; short summary + details. Common prefixes seen: `Refactor:`, `Actualización:`.
- Reference issues (e.g., `#123`) and scope affected (e.g., `bots`, `scrapers`).
- PRs: include purpose, notable changes, run instructions, logs/screenshots if relevant, and linked issues. Update docs/templates as needed.

## Security & Configuration
- Secrets via `.env` (never commit):
  - `TELEGRAM_BOT_TOKEN`, `AUTHORIZED_USER_IDS`
  - `EDUCATIONPOSTS_USERNAME`, `EDUCATIONPOSTS_PASSWORD`
  - `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON), `FIREBASE_STORAGE_BUCKET`
  - `NOTION_API_KEY`, `NOTION_DATABASE_ID` (for CRM integration)
  - Optional test email: `EMAIL_ADDRESS`
- Create `.env` from `.env.example`; configure before running. Keep credentials out of code and commits.
- Notion CRM is optional; system works without it (graceful fallback)

