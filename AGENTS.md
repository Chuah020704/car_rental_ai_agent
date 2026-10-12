# AGENTS.md

Guidance for coding agents (and future-you) working in this repository.

## Project overview

A LangGraph-based customer service agent for a car rental company. Layers, inner to outer:

```
domain (enums/models) -> repositories (data access) -> service (business logic)
    -> agent (tools, router, graph) -> api (FastAPI routers) -> ui (Streamlit)
```

Dependencies only point inward-to-outward in that list; never import `api` or `ui`
from `agent`, and never import `agent` from `service`.

## Setup commands

```
uv sync --all-extras
cp .env.example .env            # then fill in at least one LLM provider key
uv run python scripts/build_index.py --rebuild
```

## Run commands

```
make run    # FastAPI on :8081
make ui     # Streamlit on :8501
make index  # rebuild the Chroma policy index
```

## Testing

```
make test              # uv run pytest -m "not llm" — no API key required, CI-safe
uv run pytest -m llm    # also exercises real LLM calls, needs provider keys
```

When adding a new agent behaviour, add a case to `tests/evals/dataset.yaml` asserting
the `expected_tool`, not just a unit test — routing regressions are the easiest thing
to miss.

## Code style

- Ruff is the only linter/formatter (config in `pyproject.toml`); run `make lint format`.
- Full type hints required everywhere (`ANN` ruff rule + `mypy --disallow-untyped-defs`).
- Pydantic v2 only for data models; no bare dicts crossing a function boundary.
- No business logic inside `app/agent/tools/*` — tools are thin adapters that call
  `app/service/*`; this keeps the logic testable without an LLM in the loop.

## Adding a new tool

1. Create `app/agent/tools/<name>.py` with a `@tool`-decorated function, a Pydantic
   `args_schema`, and a docstring written for the LLM (it IS the routing signal).
2. Register it in `app/agent/tools/__init__.py`'s `TOOLS` list.
3. Add a unit test for the underlying service call.
4. Add at least one case to `tests/evals/dataset.yaml`.

## Security considerations

- Never log secrets or full PII; the logging formatter has a redaction filter — use it.
- `customer_id` is always derived from the verified JWT/Entra token inside
  `app/dependencies/auth.py`, never taken from LLM tool-call arguments.
- Mutations (`modify_reservation`, `cancel_reservation`) must go through
  `interrupt()` confirmation — no exceptions.
- Secrets live only in `.env` (gitignored). `.env.example` documents every key with
  no real values.

## PR / commit conventions

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Run `make check` (lint + typecheck + test) before committing.
