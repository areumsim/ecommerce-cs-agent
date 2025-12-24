# Repository Guidelines

This guide helps contributors work effectively in this repo. It covers structure, local dev commands, style, testing, and PR expectations tailored to this Python agent PoC.

## Project Structure & Module Organization
- `src/` — main code
  - `agents/` (orchestrators, tools)
  - `data_prep/` (load/clean/normalize)
  - `guardrails/` (policy checks/validators)
  - `mock_system/` (CSV-backed repos, mock APIs)
  - `rag/` (retriever, indexing helpers)
- `scripts/` — data crawl, preprocess, index, E2E flows
- `configs/` — YAML configs (e.g., `mock.yaml`, `crawl.yaml`)
- `data/` — input/processed/mock artifacts (CSV/JSONL)
- `api.py` — FastAPI app; `ui.py` — Gradio demo
- `docs/` — runbooks and pipeline docs

When adding modules, prefer small, focused files under an existing subpackage. Example: new retrieval logic → `src/rag/<name>_retriever.py`.

## Build, Test, and Development Commands
- Create env and install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Prepare policy data: `python scripts/01a_crawl_policies.py && python scripts/04_build_index.py`
- Generate mock data: `python scripts/03_generate_mock_csv.py`
- Run API locally: `uvicorn api:app --reload`
- Run demo UI: `python ui.py`

## Data Pipeline Artifacts
After running `python scripts/02_full_preprocess_stream.py`, expect:
- `data/processed/products.parquet` (~203MB)
- `data/processed/reviews.parquet` (~7.5GB)
- `data/processed/reviews_agg.parquet` (~19MB)
These are large and must not be committed; keep them under `data/` and ensure configs point to the local paths.

## Next Steps: Crawl → Index → Smoke
- Crawl + index policies: `python scripts/01a_crawl_policies.py && python scripts/04_build_index.py`
- Start API: `uvicorn api:app --reload` then smoke-check:
  - Health: `curl localhost:8000/healthz`
  - Search: `curl "localhost:8000/policies/search?q=환불&top_k=3"`
- Start UI (optional): `python ui.py` and open `http://localhost:7860`.

Tip: 자동 스모크 체크는 `bash scripts/smoke_api.sh [BASE_URL] [QUERY]`로 실행합니다.
기본값은 `http://localhost:8000`, `환불`이며, `/healthz` 대기 후 정책 검색 응답(HTTP 200)을 확인합니다.

## Coding Style & Naming Conventions
- Python 3.10+; 4-space indent; PEP 8 style; add type hints.
- Modules/functions: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE`.
- Keep functions <100 lines; prefer pure functions in `data_prep/` and thin adapters in `mock_system/`.
- Validate external inputs with `pydantic` models at the API boundary.

## Testing Guidelines
- Framework: `pytest` (add to dev env if missing). Place tests under `tests/`, named `test_*.py`.
- Focus on deterministic units: CSV repositories, RAG retrieval scoring, guardrails.
- Example: `pytest -q` (optionally `pytest tests/rag/test_retriever.py -q`). Aim for 70%+ coverage on touched code.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`. Scope examples: `rag`, `mock_system`, `api`.
- PRs must include: purpose, key changes, how to run/test, and any config/data assumptions. Link related issues and add screenshots/logs for UI/API changes.
- Keep PRs small and cohesive; add/update docs under `docs/` when behavior changes.

## Security & Configuration Tips
- Do not commit secrets. Use env vars or a local `.env` (ignored) and reference via `configs/*.yaml` when feasible.
- Large artifacts stay in `data/`; avoid committing generated files outside that tree.
