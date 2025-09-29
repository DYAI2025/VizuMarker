# Repository Guidelines

## Project Structure & Module Organization
Backend API code stays under `ld35_service/`; routes live in `api/v1`, configuration in `core`, schemas in `schemas`, and async helpers in `workers`. Marker engine bundles and CLI tooling reside in `LeanDeep_Engine/` and should only be modified when publishing new engine artifacts. The React viewer sits in `frontend/`, shared docs in `docs/`, storage fixtures and mock data in `storage/`, and all backend tests under `tests/`. Resources consumed by the canonical span matcher are versioned in `resources/` and must be kept in sync with the deployed engine.

## Build, Test, and Development Commands
- `poetry install` — provision Python 3.9 dependencies and pre-commit hooks.
- `poetry run dev` — launch the FastAPI app via `ld35_service.main:main` with hot reload.
- `poetry run uvicorn ld35_service.main:app --reload` — quick local loop for endpoint development.
- `poetry run pytest` — execute the backend test suite.
- `poetry run black ld35_service tests` / `poetry run isort ld35_service tests` — apply formatting.
- `docker-compose up --build` — start API, Redis, and Celery for integrated validation.

## Coding Style & Naming Conventions
Use 4-space indentation, Python type hints, and snake_case for modules, functions, and fixtures. REST handlers should follow action_object naming (`annotate_document`, `render_export`). Frontend components remain PascalCase with colocated styles in `frontend/styles/`. Run `black`, `isort`, `flake8`, and `mypy` locally before opening a pull request.

## Testing Guidelines
Name files `test_*.py` and keep fixtures in `tests/conftest.py`. Prefer `pytest-asyncio` with `httpx.AsyncClient` for route checks, and extend `tests/test_integration.py` when exercising Celery, streaming, or Redis flows. Store or update golden exports under `storage/fixtures/` and document assertions inline for clarity.

## Commit & Pull Request Guidelines
Write commits as `type: summary`, e.g., `feat: add LD35 chunk guard`, and keep each commit scoped to a single concern (API vs. engine vs. frontend). Pull requests should explain the change, list manual checks (`poetry run pytest`, curl snippets, screenshots), and link issues or TODOs driving the work.

## Security & Configuration Tips
Use `.env.example` as the baseline for local secrets; set `LD35_MODEL_PATH`, `STORAGE_PATH`, and Redis variables before launching services. When moving the marker engine, update `MARKER_ENGINE_PATH` so bundles in `ME_ENGINE_CORE_V0.9/` remain discoverable. The local launcher `./start_vizumarker.py` exports `DISABLE_AUTH=1`, waits for `/health`, then opens `/app/`; stop it with `Ctrl+C` when finished.
