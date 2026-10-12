# Learning Notes — Car Rental AI Agent

A running study log of every file in this repo: what it does, which libraries it
uses and why, and how it connects to everything else. Read top to bottom in the
order things were built, or jump to a phase using the headings below.

---

## Phase 0 — Project scaffolding & tooling

### Lesson 1 — Environment: `uv` and Python version pinning

**Problem solved:** reproducible builds. Two people (or you and a grader) running
this project should get *exactly* the same dependency versions and Python version,
not "whatever pip resolved today."

- **`uv`** (by Astral, makers of `ruff`) replaces `pip` + `venv` + `pip-tools` with a
  single fast Rust binary. `uv sync` reads `pyproject.toml`, resolves every dependency
  (including transitive ones) to an exact version, writes `uv.lock`, and creates a
  `.venv/` — all in one command.
- It wasn't on PATH because `pip install --user uv` drops the executable in
  `%APPDATA%\Python\Python314\Scripts`, which Windows doesn't add to PATH automatically.
  Fixed permanently with `setx PATH "%APPDATA%\Python\Python314\Scripts;%PATH%"`
  (restart the terminal afterwards).
- **Python 3.13, not 3.14:** the machine has both installed. 3.14 is too new — some
  ML-adjacent packages (ChromaDB, certain LangChain extras) don't reliably ship
  pre-built wheels for it yet. `uv` manages its own interpreter download/selection
  independent of what's on PATH, via `requires-python` in `pyproject.toml`.

### Lesson 2 — `pyproject.toml`: the project's single source of truth

**File:** [`pyproject.toml`](../pyproject.toml)

Before this file existed, Python projects scattered config across `setup.py`,
`requirements.txt`, `setup.cfg`, `.flake8`, `pytest.ini`. `pyproject.toml` (TOML —
a stricter, more structured alternative to INI) consolidates all of it:

- `[project]` — PEP 621 metadata (name, version, Python version constraint,
  runtime `dependencies`). `uv`, `pip`, and `build` all read this section the same way.
- `[dependency-groups]` (PEP 735) — `dev` tools (`pytest`, `ruff`, `mypy`) that you
  need locally/in CI but shouldn't ship in a production install.
- `[tool.ruff]` / `[tool.ruff.lint]` — copied **verbatim** from the reference
  `applications.ai.agenticbot.backend` repo: `line-length = 88`, the exact `select`
  rule list (`E, W, F, B, I, UP, ANN, S, N, ARG, RUF`). Practically, this means:
  - `ANN` forces type hints on every function.
  - `S` (flake8-bandit) flags security smells (`eval()`, hardcoded secrets, etc.) —
    this is where "security" from the grading rubric gets enforced automatically.
  - `I` auto-sorts imports (replaces `isort`).
- `[tool.pytest.ini_options]` — defines a custom `llm` marker so CI can run
  `pytest -m "not llm"` and skip tests that need a real API key.
- `[tool.mypy]` — `disallow_untyped_defs = true` backs up the `ANN` ruff rule with
  actual type *checking*, not just presence-of-annotation checking.

**Connects to:** `uv.lock` (generated, derived from this file — never hand-edit it),
later `requirements.txt` (exported from the lock for the Docker build stage),
`.pre-commit-config.yaml` and `.github/workflows/ci.yml` (both invoke the tools
configured here).

### Lesson 3 — `.gitignore` and `.env.example`: the secrets boundary

**Files:** [`.gitignore`](../.gitignore), [`.env.example`](../.env.example)

The reference repo's biggest anti-pattern was committing `secrets.env`,
`secrets_old.env`, and `.pfx` certificate files straight into git history — once a
secret is committed, it's in the repo's history forever (rotating the credential is
the only real fix). This project's rule: **`.env` is gitignored, `.env.example`
documents every variable name with blank/placeholder values and is committed.**

`.env.example` groups variables the same way the two-tier config (Phase 1) will
read them:
- `LLM_PROVIDER` / per-provider API keys — read by the `get_llm()` factory.
- `EMBEDDING_PROVIDER=local` — defaults to `fastembed`, which runs on-device with
  no API key, so the RAG pipeline works for a grader with zero cloud credentials.
- `AUTH_MODE=simulated|entra` — the dual-mode auth switch from the Q11 decision.
- `JWT_*` / `ENTRA_*` — settings for whichever `AUTH_MODE` is active.

### Lesson 4 — `Makefile`: one-word commands for common tasks

**File:** [`Makefile`](../Makefile)

A thin wrapper so `make test`, `make run`, `make lint` work without remembering the
full `uv run ...` invocation each time. Recipe lines **must** be indented with a
literal tab character — Make's oldest, most infamous footgun (spaces silently
produce a "missing separator" error).

### Lesson 5 — Pre-commit hooks and CI

**Files:** [`.pre-commit-config.yaml`](../.pre-commit-config.yaml),
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

- **pre-commit** runs `ruff` (lint + format) and `mypy` automatically on every
  `git commit`, catching style/type issues before they ever reach CI. Install it
  once per clone with `uv run pre-commit install`.
- **CI** (`ci.yml`) runs the same checks on GitHub-hosted runners
  (`ubuntu-latest`) so anyone can fork this repo and get working CI with zero
  Intel-internal infrastructure — the reference repo's CI depended on private
  self-hosted runners (`innersource.prod.amr.dind`) and a private reusable Semgrep
  workflow, neither of which work outside that org. The `semgrep` job here uses the
  public `semgrep/semgrep-action` with free community rulesets
  (`p/python p/security-audit p/owasp-top-ten`) — no token required.
- `.github/dependabot.yml` — automated weekly PRs bumping pinned dependencies and
  GitHub Action versions, a cheap "production thinking" signal.
- `.github/CODEOWNERS` — placeholder; update the username to yours.

### Lesson 6 — `AGENTS.md`: instructions for coding agents

**File:** [`AGENTS.md`](../AGENTS.md)

A convention (not VS Code-specific — also read by Cursor, Aider, Codex, Jules, etc.)
for giving an AI coding agent the context a README doesn't: exact setup/test
commands, architecture rules it must not violate (dependency direction between
layers), the step-by-step checklist for adding a new tool, and security invariants
(e.g. "`customer_id` always comes from the verified token, never from LLM output").
The reference repo had none of this — it's pure added value here.

---

*(Further phases — config/logging, domain/repositories/services, RAG, the
LangGraph agent, HITL, FastAPI, Streamlit, tests — will each get their own section
below as they're built.)*

---

## Phase 1 — Config, logging, exceptions

These three are built first because almost everything else imports them: tools
need the logger, the agent needs settings, the API needs the exception handlers.

### Lesson 7 — `app/core/config/config.yaml` + `app/utils/config.py`: two-tier settings

**Files:** [`app/core/config/config.yaml`](../app/core/config/config.yaml),
[`app/utils/config.py`](../app/utils/config.py)

The split exists because the two kinds of configuration have different lifecycles:

| | Tier 1: `config.yaml` | Tier 2: `.env` |
|---|---|---|
| Contains | model names, temperatures, retrieval thresholds, rate limits | API keys, JWT signing key |
| Committed to git? | Yes | Never (gitignored) |
| Changed by | a reviewable PR | ops/you, per environment |
| Loaded by | `yaml.safe_load` into a plain dict | **pydantic-settings** into validated models |

**`pydantic-settings`** (`BaseSettings`) is the key library here — it's a `pydantic`
subclass that automatically reads matching environment variables (or a `.env` file
via `SettingsConfigDict(env_file=...)`) and validates/coerces them into typed
fields. If you declared a field as `int` and the `.env` had a non-numeric string,
you'd get a clear validation error *at startup*, not a confusing crash three
requests later.

The settings are split into small groups (`LLMProviderSettings`, `AuthSettings`,
`EntraSettings`, `MiddlewarePolicySettings`, `LoggingSettings`) rather than one
giant class, each composed into a top-level `Settings(BaseModel)`. This mirrors
the reference repo's pattern and keeps each group independently testable and
readable — `settings.auth.jwt_secret_key` is self-documenting about where a value
comes from.

Both `get_settings()` and `get_config()` are wrapped in `@lru_cache` — the file is
read and validated exactly once per process, and every subsequent call (from any
module) gets back the identical cached object instantly.

**Connects to:** everything downstream reads config through these two functions —
the LLM factory (Phase 4) reads `config.yaml`'s `MODEL_SERVICE.LLM` block, the
JWT dependency (Phase 6) reads `settings.auth`, the RAG retriever (Phase 3) reads
`config.yaml`'s `RAG` block.

### Lesson 8 — `app/utils/exception/exceptions.py`: one hierarchy, one place to catch errors

**File:** [`app/utils/exception/exceptions.py`](../app/utils/exception/exceptions.py)

Every exception this app raises *on purpose* (not a bug — an expected business
condition like "reservation not found") inherits from `AppException`, which
carries a `status_code`, an internal `detail` (safe to log, may contain IDs/stack
context), and an optional `user_message` (safe to show a customer).

Why bother with a hierarchy instead of just raising `HTTPException` everywhere?
Because `app/service/*` (business logic) shouldn't know anything about HTTP —
it's not a web layer. A service raises `ReservationNotFoundException`, and only
`app_car_rental.py`'s exception handlers (Phase 6) translate that into an HTTP
404 response. This is the same separation of concerns as the layered dependency
rule in `AGENTS.md`: inner layers don't import outer-layer concepts.

Note the ruff config change this required: `N818` (naming rule that wants
`FooError` instead of `FooException`) is ignored project-wide, because we're
intentionally matching FastAPI's own convention (`HTTPException`, not
`HTTPError`) rather than stdlib's.

### Lesson 9 — `app/utils/logging/`: structured logs with automatic secret redaction

**Files:** [`logger.py`](../app/utils/logging/logger.py),
[`config.py`](../app/utils/logging/config.py),
[`formatter.py`](../app/utils/logging/formatter.py),
[`handlers.py`](../app/utils/logging/handlers.py)

**`structlog`** replaces Python's stdlib `logging` string-formatting style
(`logger.info(f"User {uid} did X")` — unstructured, hard to query) with structured
key/value events: `logger.info("reservation_cancelled", reservation_id="R002",
customer_id="C1")`. In production this renders as one JSON object per line,
trivially greppable/queryable by any log aggregator; in your terminal (an
interactive TTY) it renders as colorized, human-readable text instead — that
switch happens automatically in `config.py` based on `sys.stderr.isatty()`.

`structlog.contextvars.merge_contextvars` is what will let Phase 6 bind a
`trace_id` and `customer_id` once per incoming HTTP request and have them
automatically show up on *every* log line emitted while handling that request —
including deep inside a tool call — without threading those values through every
function signature by hand.

`formatter.py`'s `redact_processor` runs on every single log event, before
rendering: any key containing `password`, `token`, `secret`, `api_key`, etc. gets
replaced with `***REDACTED***`, and any string value that looks like an email
gets scrubbed. This is the concrete implementation of the "never log secrets or
PII" rule in `AGENTS.md` — it's enforced in code, not just in a comment telling
developers to be careful.

`handlers.py`'s rotating file handler is defined but not wired in by default —
console/JSON-to-stderr is enough for local dev and container logs (which get
captured by Docker/K8s anyway); it's there to show the pattern exists without
over-engineering a take-home project.

### Lesson 10 — `app/utils/retry.py`: exponential backoff for flaky I/O

**File:** [`app/utils/retry.py`](../app/utils/retry.py)

A generic `retry()` helper (using PEP 695 generic syntax — `async def retry[T](...)`,
new in Python 3.12+, replacing the older `TypeVar("T")` + import dance) that wraps
any async callable, retrying up to `max_attempts` times with the delay doubling
each time (`base_delay * 2^attempt`) — the standard mitigation for transient
failures like LLM API rate limits or network blips. Will wrap the LLM factory's
`.invoke()` calls in Phase 4.

### Lesson 11 — Fixing real lint/type errors (not suppressing them)

Running `ruff check` + `mypy app` immediately surfaced six issues worth noting,
because the fixes are the actual lesson:

- **`S105` hardcoded-password false positive** on `jwt_secret_key`'s dev default —
  suppressed with a `# noqa: S105` *and* a comment explaining it's a documented
  dev-only default (overridden via `.env`), not a real secret.
- **`UP047`**: ruff wanted PEP 695 generic syntax instead of the old `TypeVar`
  pattern — a genuine modernization, not a style nitpick, so it was adopted.
- **`S101` (assert in non-test code)**: `assert` statements are stripped entirely
  when Python runs with the `-O` optimization flag, so using one to guard a
  real invariant in production code is a latent bug. Replaced with an explicit
  `if ... raise RuntimeError(...)`.
- **mypy `list-item` error** in `logging/config.py`: `redact_processor`'s
  parameter was typed too narrowly (`dict[str, Any]`) for structlog's
  `Processor` type alias, which expects the more general `MutableMapping`. Since
  function parameters are contravariant, a narrower type is actually *less*
  compatible, not more — widened it to `MutableMapping[str, Any]` /
  `Mapping[str, Any]` to fix it properly instead of silencing mypy.

---

## Phase 2 — Domain models, mock data, repositories, services

This phase builds the two innermost layers from `AGENTS.md`'s architecture rule:
`domain (enums/models) -> repositories (data access) -> service (business logic)`.
Notice none of these files import anything from `app.agent` or `app.api` —
dependencies only point inward-to-outward.

### Lesson 12 — `app/enums/`: `StrEnum` instead of plain strings

**Files:** [`app/enums/vehicle.py`](../app/enums/vehicle.py),
[`reservation.py`](../app/enums/reservation.py), [`routing.py`](../app/enums/routing.py),
[`auth.py`](../app/enums/auth.py)

Python 3.11+'s `enum.StrEnum` gives you a type that **is-a** `str` (so
`VehicleCategory.SUV == "suv"` is `True`, and it serializes to JSON as a plain
string with zero custom code) while still being a real enum — your editor
autocompletes `VehicleCategory.` and mypy flags `VehicleCategory.SUBARU` as a
typo at commit time instead of a runtime `KeyError` three months later. Compare
that to passing `"suv"` as a bare string everywhere: a typo like `"suuv"` would
silently fail to match anything and nobody would notice until a bug report.

### Lesson 13 — `app/models/schemas.py`: Pydantic v2 models as the only data shape

**File:** [`app/models/schemas.py`](../app/models/schemas.py)

Every piece of data that crosses a function boundary in this app is one of these
models — never a bare `dict`. The payoff shows up immediately: `Vehicle.model_validate(json_dict)`
both *parses* the JSON and *validates* it (wrong types, missing fields, bad enum
values all raise a clear `ValidationError` at load time, not a `KeyError` deep in
business logic later). `date` fields are real Python `datetime.date` objects, not
strings you'd have to parse by hand everywhere you compare pickup/return dates.

`RouteDecision` and `UsageMetadata` are here now even though nothing uses them
yet — they're the data contracts Phase 4 (the router and the agent graph) will
produce, defined alongside the rest of the domain so they're reviewable as part
of the same model file.

### Lesson 14 — `data/`: mock data as the "database"

**Files:** [`data/vehicles.json`](../data/vehicles.json),
[`data/reservations.json`](../data/reservations.json), [`data/policies/*.md`](../data/policies/)

12 vehicles across Economy/Compact/SUV/Premium/Van, Malaysian brands (Perodua,
Proton, Honda, Toyota) and MYR pricing — realistic enough that the demo
conversations in the brief read naturally. `reservations.json` deliberately
includes edge cases, not just happy-path data: **R005 is already `cancelled`**
(tests the idempotency guard — you can't cancel twice), **R004 is `completed`**
(tests that you can't modify/cancel a finished rental), and **R002 is the one
the brief's sample conversation cancels**. Each reservation also carries an
`entra_upn` field (nullable) — the bridge between a real Microsoft Entra ID
login and these mock customer records, per the Q13 decision; customers without
one simply can't log in via `AUTH_MODE=entra` (only `simulated`).

Policies are six **separate** Markdown files, not one `policies.txt` — the
filename itself becomes retrieval metadata in Phase 3 (`source: "cancellation.md"`),
which is what makes citations like "(source: cancellation.md)" possible later
without any extra bookkeeping.

### Lesson 15 — `app/repositories/`: `Protocol` instead of `ABC`

**Files:** [`base.py`](../app/repositories/base.py),
[`vehicle_repo.py`](../app/repositories/vehicle_repo.py),
[`reservation_repo.py`](../app/repositories/reservation_repo.py)

`typing.Protocol` defines an interface by **shape**, not by inheritance —
`JsonVehicleRepository` never writes `class JsonVehicleRepository(VehicleRepository):`;
it just happens to have a `get_all()` and `get_by_id()` method with matching
signatures, and that's enough for `VehicleService` (which type-hints its
constructor parameter as `VehicleRepository`) to accept it. This is "structural
typing" — the Python equivalent of Go interfaces. The practical benefit: if this
were ever swapped for a real REST-backed repository hitting the company's actual
reservation API, that new class doesn't need to inherit from anything in this
codebase, it just needs the same method shapes.

`JsonReservationRepository.save()` writes back to disk using a **write-to-temp-
file-then-`os.replace()`** pattern rather than writing directly to
`reservations.json` — `os.replace()` is atomic on both Windows and POSIX, so a
crash mid-write can never leave a half-written, corrupted JSON file behind. This
also means you can actually open `data/reservations.json` after running a
cancel/modify conversation and see the change reflected on disk — useful for
demoing and debugging, even though it's not how you'd persist state in a real
production service (that would be a real database, see `docs/adr`).

### Lesson 16 — `app/service/`: where the actual business rules live

**Files:** [`vehicle_service.py`](../app/service/vehicle/vehicle_service.py),
[`reservation_service.py`](../app/service/reservation/reservation_service.py)

This is the layer `AGENTS.md` insists stays free of LLM concerns — "no business
logic inside `app/agent/tools/*`" means *all* of it lives here instead, as plain,
synchronous, 100%-unit-testable Python:

- **`VehicleService.search()`** does date-overlap availability checking: a
  vehicle's static `available` flag (e.g. "in maintenance") is combined with a
  dynamic check — does any *other* confirmed reservation's date range overlap
  the requested dates? `_dates_overlap()` is the classic interval-overlap test:
  two ranges overlap unless one ends before the other starts.
- **`ReservationService._assert_owner()`** is the concrete code behind the "IDOR
  guard" decision from planning — it compares the reservation's `customer_id`
  against the id the caller passes in, and raises `NotAuthorizedException` (with
  a *different* message for logs (`detail`) vs. the customer (`user_message`),
  so the log can be specific while the customer just sees "no reservation found"
  rather than "yes R001 exists, it's just not yours," which would leak
  information to an attacker probing reservation IDs).
- **`cancel_reservation()`** checks `status != CONFIRMED` before cancelling — this
  is the idempotency guard that makes cancelling an already-`cancelled`
  reservation a hard error instead of a silent no-op or a double-refund bug.
- **`modify_reservation()`** is deliberately narrow (dates only, per the planning
  grill session) — it re-validates the new dates don't conflict with *other*
  active reservations on the same vehicle (excluding itself!) and recalculates
  `total_price` from the vehicle's `price_per_day`, so the price always reflects
  reality rather than trusting a client-supplied number.

Both services take their repositories as constructor parameters (dependency
injection) rather than importing a concrete repository class directly — this is
what makes `tests/conftest.py`'s fixtures able to swap in a temp-file-backed
repository for mutation tests without touching the committed mock data.

### Lesson 17 — `tests/`: fixtures that protect committed data from mutation

**Files:** [`tests/conftest.py`](../tests/conftest.py),
[`test_vehicle_service.py`](../tests/unit/test_vehicle_service.py),
[`test_reservation_service.py`](../tests/unit/test_reservation_service.py)

The `reservation_repo` fixture copies `data/reservations.json` into pytest's
`tmp_path` (a fresh temp directory per test, auto-cleaned afterwards) *before*
constructing the repository — so `test_cancel_reservation_succeeds_for_owner`
can actually cancel R002 and assert the result, without ever touching the real
`data/reservations.json` that's committed to git. `vehicle_repo` doesn't need
this (nothing ever mutates vehicle data), so it reads the real file directly.

---

## Phase 3 — RAG pipeline (embeddings, ingestion, retrieval)

### Lesson 18 — `app/service/rag/embedding_service.py`: a provider factory, with a free local option

**File:** [`embedding_service.py`](../app/service/rag/embedding_service.py)

Same dispatch-by-name shape the LLM factory (Phase 4) will reuse: `get_embeddings()`
reads `settings.llm.embedding_provider` and returns a LangChain `Embeddings`
instance for Google, OpenAI, or — the default — **`local`**, backed by
**`fastembed`** (a lightweight, dependency-light ONNX runtime for small
embedding models that run entirely on-device, no API key, no network call per
request). This is why the whole RAG pipeline works for a grader who has zero
cloud credentials configured: `EMBEDDING_PROVIDER=local` in `.env.example` means
`uv run python scripts/build_index.py` just works out of the box.

`LocalFastEmbedEmbeddings` wraps `fastembed.TextEmbedding` to satisfy
LangChain's `Embeddings` abstract base class (`embed_documents` / `embed_query`).
A subtlety worth remembering: BGE-family models (we use `BAAI/bge-small-en-v1.5`)
are **asymmetric** — queries and passages are meant to be embedded slightly
differently for best retrieval quality, which is why `fastembed` exposes
separate `query_embed()` / `passage_embed()` methods rather than one generic
`embed()`. Using the wrong one is an easy, silent mistake (the model still
returns *a* vector, just a less accurate one).

### Lesson 19 — `app/service/rag/ingest_service.py`: chunking that preserves citations

**File:** [`ingest_service.py`](../app/service/rag/ingest_service.py)

Two splitters, used in sequence, each solving a different problem:
1. **`MarkdownHeaderTextSplitter`** splits on `#` headers first and stamps each
   resulting chunk's `metadata["title"]` with the heading text above it — this
   keeps a policy's heading attached to its content even after further
   splitting, so a chunk never loses its "what is this about" context.
2. **`RecursiveCharacterTextSplitter`** then enforces a hard size ceiling
   (`CHUNK_SIZE=800`, `CHUNK_OVERLAP=120` from `config.yaml`) for any chunk
   still too long — the overlap means a sentence that happens to fall exactly
   on a chunk boundary still appears intact in at least one of the two chunks.

Critically, **`chunk.metadata["source"] = path.name`** is set *before* any
splitting happens — every chunk, no matter how it gets further subdivided,
carries the filename it came from. This one line is the entire mechanism behind
later being able to say "(source: cancellation.md)" in a chat response — no
separate citation-tracking system required.

`build_index()` is idempotent (skips re-embedding if `.chroma/` already exists,
unless `rebuild=True`) and persists straight to disk via Chroma's
`persist_directory` — a local, file-based vector store needing zero infrastructure,
which is exactly why Chroma was chosen over pgvector/Qdrant for this project
(see `docs/adr`).

### Lesson 20 — `app/service/rag/retrieval_service.py`: a hard relevance cutoff, not a vibe

**File:** [`retrieval_service.py`](../app/service/rag/retrieval_service.py)

`PolicyRetriever.retrieve()` calls Chroma's `similarity_search_with_score()`,
which returns `(Document, distance)` pairs — **smaller distance = more similar**.
Anything above `COSINE_DISTANCE_THRESHOLD` gets thrown away entirely before the
LLM ever sees it. This is the concrete mechanism behind the Q4 planning decision
("RAG groundedness guard") — the `policy_rag` tool (Phase 4) will treat an empty
result list as "nothing on file," never silently falling back to the LLM's own
(unverifiable, possibly wrong) general knowledge about rental policy.

`_deduplicate_by_source()` keeps only the single best-scoring chunk per source
file — with only six short policy documents chunked into 8 pieces total, you
don't want two near-identical chunks from the same `insurance.md` both showing
up and crowding out a different, equally-relevant document.

### Lesson 21 — Calibrating the threshold empirically, not by copying a number

The reference repo hardcodes `COSINE_DISTANCE_THRESHOLD: 0.4` — but that number
was tuned for *their* embedding model (Azure OpenAI `text-embedding-3-large`).
Copying it blindly here broke retrieval entirely: a direct diagnostic query
showed the correct `cancellation.md` chunk scoring **0.41** (just barely
*above* the borrowed 0.4 cutoff) while an irrelevant query ("capital of
France") scored 0.83+ against the same chunk. The actual gap between relevant
and irrelevant is huge (0.41 vs 0.83) — the cutoff just needed to sit somewhere
in between, so it was recalibrated to **0.5** based on these real measured
numbers, not guessed. **Lesson: a relevance threshold is a property of the
embedding model, not a universal constant — always verify it against a real
query/document pair before trusting it.**

### Lesson 22 — `scripts/build_index.py`: the CLI entrypoint

**File:** [`build_index.py`](../scripts/build_index.py)

A thin `argparse` wrapper so the whole ingestion pipeline is one command:
`make index` (defined in the `Makefile`) runs
`uv run python scripts/build_index.py --rebuild`. Separating the CLI (argument
parsing, printing) from `build_index()` (the actual logic, importable and
testable on its own) is the same "thin adapter, logic lives elsewhere" pattern
as agent tools calling into services.

### Lesson 23 — Testing something that needs a network/model download

**File:** [`tests/integration/test_rag_retrieval.py`](../tests/integration/test_rag_retrieval.py)

This test exercises the *real* Chroma + fastembed pipeline end-to-end — no
mocks — which means its first run needs network access to download the
~130MB `bge-small-en-v1.5` ONNX model from Hugging Face (cached afterwards).
It's marked `@pytest.mark.llm` even though no LLM call happens, reusing that
marker as a general "needs network/external resources" signal so `make test`
(the CI-safe, no-credentials-required command) skips it by default, while
`uv run pytest -m llm` runs it explicitly when you do have connectivity.

---

## Phase 4 — LLM factory, prompts, tools, router, and the LangGraph agent

This is the biggest phase: the actual "Agent" in "Car Rental AI Agent." Scope
was deliberately narrowed to **read-only tools only** (`search_vehicles`,
`get_reservation`, `policy_rag`) — `modify_reservation` and
`cancel_reservation` need the `interrupt()` human-confirmation pattern and a
checkpointer to be safe to ship at all, so they're built in Phase 5 alongside
that machinery rather than half-built here.

### Lesson 24 — Verifying library APIs instead of guessing

Several library calls in this phase were verified by inspecting the installed
package directly (`inspect.signature(...)`, `ClassName.model_fields`) *before*
writing code against them, because LangChain's v1.x restructuring moved or
renamed things non-obviously:

- `langchain` no longer bundles text splitters — needed the separate
  `langchain-text-splitters` package (Lesson 19's tooling depends on this).
- `ChatOpenAI`/`ChatAnthropic` accept constructor keywords by their pydantic
  **alias**, not necessarily their field name — e.g. `ChatOpenAI`'s field is
  `model_name` but its constructor alias is `model`; `ChatAnthropic`'s field is
  `model` but its alias is `model_name` (the exact *opposite* mapping!). Typing
  these by memory/convention would have silently produced a working-at-runtime
  but mypy-rejected call; checking `ClassName.model_fields["x"].alias` first
  avoided a second round of guess-and-fix.
- `fastembed.TextEmbedding` exposes `query_embed()`/`passage_embed()`
  separately (not one generic `embed()`) specifically for asymmetric models
  like BGE — confirmed via `inspect.signature` before relying on it.

**Lesson: when a library's behavior isn't obvious from its public docs (or the
docs are for a different major version than what's installed), a 30-second
`inspect.signature()`/`model_fields` check is cheaper than a wrong guess plus a
fix-up round.**

### Lesson 25 — `app/service/llm/llm_factory.py`: the same factory pattern, for chat models

**File:** [`llm_factory.py`](../app/service/llm/llm_factory.py)

Structurally identical to the embeddings factory (Phase 3): `get_llm()`
dispatches on `settings.llm.llm_provider` across `google` / `openai` /
`anthropic` / `fake`. The `fake` provider returns a bare `FakeListChatModel` —
useful for exercising the factory itself, though it can't emit tool calls (see
Lesson 30). Every provider branch validates its own API key is present and
raises `ConfigurationException` early rather than letting the LLM client fail
with an opaque auth error three calls deep into a conversation.

### Lesson 26 — `app/models/prompt_template.py`: the system prompt as a reviewable artifact

**File:** [`prompt_template.py`](../app/models/prompt_template.py)

`PromptTemplates.AGENT_SYSTEM_PROMPT` is where several planning decisions
become concrete instructions the model actually reads: "never invent
availability/prices/policy" (groundedness), "always confirm before
modify/cancel" (the HITL rule), "only discuss this customer's own
reservations" (reinforces the structural IDOR guard — belt *and* suspenders),
and the explicit prompt-injection refusal rule from the planning grill session
("ignore previous instructions" leads to a refusal, continuing under this
prompt). `{today}` is injected fresh on every agent-node call via
`date.today()`, never cached — a stale date baked into the prompt could cause
the model to reason incorrectly about whether a pickup date is in the past.

### Lesson 27 — `app/agent/tools/`: args_schema is the routing signal, and the security boundary

**Files:** [`search_vehicles.py`](../app/agent/tools/search_vehicles.py),
[`get_reservation.py`](../app/agent/tools/get_reservation.py),
[`policy_rag.py`](../app/agent/tools/policy_rag.py),
[`_errors.py`](../app/agent/tools/_errors.py)

Each tool is a thin `@tool`-decorated function with an explicit Pydantic
`args_schema` — the docstring and field `description=`s are **prompt
engineering**, not documentation: they're the only information the LLM has
when deciding whether and how to call a tool. A vague docstring produces
unreliable routing no matter how good the model is.

The security-critical pattern is in `get_reservation`:

```python
def get_reservation(reservation_id: str, state: Annotated[dict, InjectedState]) -> str:
```

`reservation_id` is in `args_schema` (LLM-controllable); `state` is **not** —
LangGraph's `InjectedState` marker makes `ToolNode` supply the current graph
state (which holds the verified `customer_id`) directly from the graph, and
strips that parameter out of the schema the LLM ever sees. This was verified
hands-on before committing to the design: calling the tool directly via
`.invoke()` *fails* (there's no state to inject outside a graph), but invoking
it through a real `ToolNode` inside a compiled `StateGraph` works correctly —
proving the LLM (or a malicious prompt) has no path to forge `customer_id`,
because it's never part of what the LLM can even see, let alone set.

`app/agent/tools/_errors.py`'s `safe_tool_error()` is the other half of the
security boundary: a caught `AppException`'s `user_message` (safe to show) is
returned to the LLM, never `detail` (which might contain internal IDs/context
appropriate for logs but not for an end user) — the same split FastAPI's
exception handlers will enforce at the API layer in Phase 6.

### Lesson 28 — `app/agent/router.py`: forcing a tool call without an LLM round-trip

**File:** [`router.py`](../app/agent/router.py)

This is "Option C" from the original planning grill: a regex fast-path for the
cases where the *arguments* are unambiguous (an `R\d{3}` reservation ID is
either present in the message or it isn't), falling back to the ReAct agent's
own tool-choice for everything else. The interesting design constraint
discovered while building this: **only force a tool call when a regex can
build its arguments completely and safely.** A "cancel R002" message needs
nothing but the ID — forcible. A "modify R006 to next week" message needs real
date parsing ("next week" relative to today, disambiguating which day) that a
regex has no business attempting — so `modify` requests are flagged for
observability (`category=RESERVATION_MUTATION`) but still hand off to the LLM
(`source=REACT`) for the actual tool call.

When a rule *does* force a tool call, `route_node` builds a synthetic
`AIMessage` with a hand-constructed `tool_calls` list and injects it straight
into the message history, then `route_after_router`'s conditional edge sends
execution directly to the `tools` node — **skipping the agent/LLM node
entirely for that turn**. This isn't just logging a routing decision; it's
zero-cost, 100%-deterministic routing for the cases where it's safe, with the
LLM still called exactly once afterward to phrase the final natural-language
answer from the tool's result.

### Lesson 29 — `app/agent/graph.py`: wiring it all together

**File:** [`graph.py`](../app/agent/graph.py)

The graph shape is simple once drawn out:

```
START -> router -> (forced?) -> tools -> agent -> (tool_calls?) -> tools -> agent -> ... -> END
                 -> (not forced) -> agent -----------^
```

`router` and `agent` are both plain functions matching `(AgentState) -> dict`
— LangGraph merges whatever dict a node returns into the state via each
field's reducer (`messages` appends via `add_messages`; plain fields like
`route_forced` just get overwritten). `tools_condition` (prebuilt) inspects the
latest `AIMessage` and routes to `"tools"` if it has `tool_calls`, else
`"__end__"`. `llm.bind_tools(TOOLS)` is called once, inside `build_graph()` —
the function takes the **LLM itself** as a parameter rather than constructing
one internally via `get_llm()`, specifically so tests can inject a scripted
fake chat model instead (see Lesson 30).

A mypy curiosity worth remembering: the agent node is defined as a nested
closure **inside** `build_graph()` rather than returned from a separate
factory function — an earlier attempt at the latter (cleaner-looking, more
"factored" code) made mypy unable to correctly resolve `StateGraph.add_node`'s
heavily-overloaded signature for that one node, even though the runtime
behavior would have been identical. Inlining it fixed the type error. Not every
mypy error means the code is wrong — some are genuine stub/inference
limitations — but it's worth trying an alternative structure first before
reaching for `# type: ignore`.

### Lesson 30 — Testing a tool-calling agent without any API key

**Files:** [`tests/fakes.py`](../tests/fakes.py),
[`tests/unit/test_router.py`](../tests/unit/test_router.py),
[`tests/integration/test_agent_graph.py`](../tests/integration/test_agent_graph.py)

Neither of LangChain's built-in fakes (`FakeListChatModel`,
`GenericFakeChatModel`) implement `bind_tools()` — calling it raises
`NotImplementedError`, since they predate (or simply don't support) tool
calling. `ScriptedChatModel` is a small custom `BaseChatModel` subclass built
specifically for this project's tests: `bind_tools()` is a no-op returning
`self`, and `_generate()` pops the next message off a pre-programmed
`responses` list — which can itself contain `AIMessage`s with `tool_calls`,
letting a test script an entire multi-turn ReAct loop (model decides to call a
tool, the tool runs for real, the model sees the result, the model responds)
completely offline.

This is what makes `test_react_path_lets_llm_choose_the_tool` meaningful: it
proves the *graph wiring* is correct (tool execution, state threading, the
loop back to the agent node) without needing a real model to make a *good*
decision — that's what the Phase 8 eval harness (using a real provider,
marked `llm`) is for instead. Two different kinds of test, two different
purposes: wiring correctness vs. decision quality.

### Lesson 31 — A real Windows bug, and the right way to fix it

Running the full suite surfaced a genuine platform-specific failure:
`test_cancellation_query_retrieves_cancellation_policy`'s
`build_index(rebuild=True)` failed with `PermissionError: [WinError 32] The
process cannot access the file because it is being used by another process`,
specifically on `.chroma/.../data_level0.bin`.

What happened: an earlier test in the same pytest process (Phase 4's
`test_policy_question_cites_source_through_the_full_graph`) called
`get_retriever()` — an `@lru_cache`d singleton — which opened a persistent
Chroma client and never released its SQLite file handle (nothing in that
test's lifecycle calls a "close"). `build_index()`'s original implementation
then tried `shutil.rmtree(persist_dir)` to force a clean rebuild, which Windows
refuses when another handle on a file inside that directory is still open
(POSIX systems are generally more permissive about deleting open files, which
is why this wouldn't have surfaced in CI on Linux).

**The fix wasn't a workaround — it was a better design.** Instead of deleting
files at the OS level, `build_index()` now opens the existing Chroma
collection and calls `store.delete_collection()`, Chroma's own API for
dropping a collection's data through the connection it already manages. This
avoids the file lock entirely (Chroma handles its own internal state), and is
arguably more correct regardless of platform — the ingestion code no longer
needs to know or care about the on-disk file layout of its own vector store.

---

## Phase 5 — Human-in-the-loop confirmation (interrupt)

This phase adds the two mutation tools (`cancel_reservation`,
`modify_reservation`) deferred from Phase 4, built *with* the `interrupt()`
pattern from the start rather than bolted on afterward — a tool that can
mutate a reservation without a confirmation step isn't a smaller version of
this feature, it's a different (and unsafe) feature.

### Lesson 32 — Proving the mechanism before building on it

Before writing the real tools, a throwaway script validated the exact
mechanics of `interrupt()` + `SqliteSaver` + `Command(resume=...)`: a tool
calling `interrupt({...})` inside a graph compiled with a checkpointer causes
`graph.invoke(...)` to return early with an `__interrupt__` key in the result
(`list[Interrupt]`, each carrying whatever dict was passed to `interrupt()`),
and execution resumes exactly where it paused — *inside that same tool call* —
when you call `graph.invoke(Command(resume={"approved": True}), config=config)`
with the same `thread_id`. The value passed to `resume=` becomes `interrupt()`'s
return value at the call site, as if it had been a synchronous input prompt.

This confirmed the design is sound *before* two full tool implementations were
built on top of it — the same "verify the API, then build" discipline from
Lesson 24, applied to a whole mechanism rather than one function signature.

### Lesson 33 — `app/agent/tools/cancel_reservation.py` / `modify_reservation.py`

**Files:** [`cancel_reservation.py`](../app/agent/tools/cancel_reservation.py),
[`modify_reservation.py`](../app/agent/tools/modify_reservation.py)

Both tools follow the same shape:
1. Look up the reservation (ownership re-verified by the service layer, same
   as the read-only `get_reservation` tool).
2. Build a human-readable confirmation summary — `cancel_reservation` even
   computes a real cancellation fee estimate (`estimate_cancellation_fee()`,
   a new `ReservationService` method) so the customer sees the actual
   financial consequence, not just "are you sure?".
3. Call `interrupt({...})` with a structured payload (`type`, `reservation_id`,
   `summary`, plus any amount/dates) — this is the exact dict the API layer
   (Phase 6) will forward to the Streamlit UI as a `confirmation_required` SSE
   event.
4. If `decision["approved"]` is falsy, return immediately — **no service call
   happens on the decline path.** Only on explicit approval does the tool call
   `ReservationService.cancel_reservation()`/`.modify_reservation()`, which
   still re-runs every business rule (ownership, status checks, date
   conflicts) a second time, because the time between "pause" and "resume"
   could be minutes — a reservation could have changed state in between.

`estimate_cancellation_fee()`'s logic (free if 2+ days out, one day's rate
otherwise) is a deliberately simplified version of `cancellation.md`'s real
policy (which has a third tier, "non-refundable within 6 hours") — the mock
domain only tracks `date`, not time-of-day, so sub-day distinctions aren't
representable. Documented as a known simplification rather than silently
papered over.

### Lesson 34 — `app/core/checkpoint.py`: why a context manager, not a singleton

**File:** [`checkpoint.py`](../app/core/checkpoint.py)

`SqliteSaver.from_conn_string(path)` returns a context manager, not a plain
object — it owns a real SQLite connection that needs explicit closing, unlike
the `@lru_cache` singletons used everywhere else in this codebase (config,
repositories, services). `checkpointer_context()` wraps it in a
`@contextlib.contextmanager` generator so FastAPI's `lifespan` (Phase 6) can
open it once at startup and guarantee it closes on shutdown — the same
resource-lifecycle discipline the reference repo's `lifespan` function uses
for its database connections.

### Lesson 35 — `app/agent/graph.py`: `checkpointer` as an optional parameter

**File:** [`graph.py`](../app/agent/graph.py)

`build_graph()` gained a `checkpointer: BaseCheckpointSaver | None = None`
parameter, passed straight to `.compile(checkpointer=checkpointer)`. Making it
optional (rather than required) keeps the Phase 4 tests — which only exercise
read-only tools and never pause — working unchanged; only the HITL tests and
the real API (Phase 6) need to supply a real one.

### Lesson 36 — Testing HITL without ever touching committed data

**File:** [`tests/integration/test_hitl_flow.py`](../tests/integration/test_hitl_flow.py)

The tricky part of testing this wasn't the `interrupt()` mechanics (already
proven in Lesson 32) — it was that `app/agent/tools/*` call
`app.agent.deps.get_reservation_service()`, an `@lru_cache` singleton that
reads the **real, committed** `data/reservations.json` by default. A test that
actually confirms a cancellation would otherwise permanently mutate the
repo's own mock data on every test run.

The `isolated_mock_data` fixture solves this by monkeypatching
`deps._DATA_DIR` to point at a `tmp_path` copy of the data *and* clearing
every affected `lru_cache` (`get_vehicle_repo`, `get_reservation_repo`,
`get_vehicle_service`, `get_reservation_service`) so the singletons rebuild
against the temp copy on next use — then restores both the original path and
cache state in teardown, so later tests in the same pytest session (which
assume the real data) aren't affected. This is the cost of using
module-level `@lru_cache` singletons for simplicity: tests that need a
different instance have to explicitly reset the cache rather than just
constructing a fresh object.

Three tests cover the contract end-to-end: cancel pauses → confirms → the
JSON file on disk actually changes; cancel pauses → declines → the file is
provably untouched; modify pauses → confirms → both the dates *and* the
recalculated price land correctly on disk. Each uses `SqliteSaver.from_conn_string(":memory:")`
— a real checkpointer, just not a persistent one, which is all a single-test
pause/resume cycle needs.

---

## Phase 6 — FastAPI app, auth (simulated + Entra), SSE

This phase wraps the LangGraph agent in an actual web API: authentication,
the chat/confirm endpoints, exception handling, middleware, and a live
Microsoft Entra ID setup wizard for the dual-auth-mode practice goal.

### Lesson 37 — The `wizard` skill: scripting a procedure only a human can do

**File:** [`scripts/setup_entra.sh`](../scripts/setup_entra.sh)

Setting up a real Entra ID App Registration requires clicking through the
Azure Portal — no API I have access to can do that for you. The `wizard` skill
produces a bash script that *walks you through it*: opens the right URL at
each stage, tells you exactly what to click, and captures the values you copy
back (`ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`) straight into `.env`. Two choices
worth calling out:
- The registration is configured as a **public client with device-code flow
  enabled** ("Allow public client flows" = Yes) — no client secret is ever
  generated or stored, matching the Q14 planning decision.
- Before trusting the generated script, it was verified with `bash -n
  scripts/setup_entra.sh` (a syntax-only dry run — confirms the script
  *parses* correctly without executing anything) since the wizard skill
  explicitly warns against actually running a wizard end-to-end yourself (it
  opens browsers and blocks on human input).

### Lesson 38 — `app/service/customer_directory.py`: deriving identity from data you already have

**File:** [`customer_directory.py`](../app/service/customer_directory.py)

Rather than inventing a separate `customers.json`, `CustomerDirectory` derives
the unique set of customers directly from `reservations.json` (distinct
`customer_id`/`customer_name`/`entra_upn` combinations). This single class
serves two different auth-mode needs: `find_by_customer_id()` backs the
simulated-mode token picker; `find_by_upn()` is the Q13 bridge that maps a
real Entra sign-in (which only knows an email-like UPN) back to this
project's `customer_id` space.

### Lesson 39 — `app/dependencies/auth.py`: one dependency, two validators, one security invariant

**File:** [`auth.py`](../app/dependencies/auth.py)

`get_current_customer()` is the single FastAPI dependency every protected
route uses — it dispatches on `settings.auth.auth_mode` to one of two
completely different validation strategies, but both return the exact same
`CurrentCustomer` shape, so route handlers never know or care which mode is
active:

- **`simulated`**: decode a JWT signed with our own `jwt_secret_key` (HS256) —
  `POST /auth/token` is the only place that ever creates one.
- **`entra`**: validate a real Microsoft-issued token's signature against
  Entra's public JWKS (`PyJWKClient`, cached per-tenant), then check its
  `aud`/`iss` claims, then map its `preferred_username` to a `customer_id` via
  `CustomerDirectory.find_by_upn()` — if no match, the customer is rejected
  with "no reservations linked to this account" rather than a raw 500, per
  the Q13 decision.

One architectural subtlety worth remembering for real OAuth work: Entra
issues an **ID token** (audience = this app's own `client_id`) and an
**access token** (audience = whatever API it's meant to call, e.g. Microsoft
Graph) from the same device-code flow. Only the ID token is valid for *this
app* to verify as proof-of-identity — validating a Graph-audienced access
token here would be a token-confusion vulnerability (accepting a credential
meant for a different service). `_decode_entra_token()`'s docstring calls
this out explicitly so it isn't a silent trap for later.

`PyJWT` (with its built-in `PyJWKClient`) replaced the originally-planned
`python-jose` for this — `python-jose` has no equivalent convenience class for
"fetch a tenant's JWKS and find the right signing key for this token," which
would have meant hand-rolling that logic. `pyjwt` was already a transitive
dependency (via `msal`), so switching cost nothing extra.

### Lesson 40 — `app/service/agent_runner.py`: one function, two endpoints

**File:** [`agent_runner.py`](../app/service/agent_runner.py)

`run_turn()`/`run_confirm()` are the *only* code that knows how to call
`graph.invoke()` — both the JSON `/chat` route and the SSE `/chat/stream`
route call these and do nothing else graph-related themselves. This avoids
the classic "the websocket version and the REST version slowly drift apart"
bug class.

The `prior_count` trick (reading `graph.get_state(config)` *before* invoking,
to know how many messages existed already) is what makes it possible to
extract "what happened on just this turn" afterward — `.invoke()` always
returns the *entire* accumulated history, so without this, there'd be no way
to tell a new tool call from one that happened three turns ago. This was
verified hands-on first (Lesson 41) before being relied on.

A deliberate scope cut: `stream_turn_result()` replays an **already-computed**
`TurnResult` as a sequence of SSE events, rather than true token-by-token
streaming via LangGraph's lower-level `astream_events`. True streaming is a
nicer UX (text appears as the model "thinks") but adds real complexity for a
feature that's a demo polish item, not a grading criterion — the trace events
(routing → tool_call → tool_result → confirmation_required/delta → done) are
still fully real and useful for the Streamlit trace panel (Phase 7), just
computed eagerly rather than streamed live.

### Lesson 41 — Verifying multi-turn continuation before building on it

Before writing `run_turn()`, a throwaway script confirmed something not
obvious from LangGraph's docs: calling `graph.invoke({"messages": [...]},
config)` on an **existing** thread with only a *partial* state update (just
the new message, omitting `customer_id`/`customer_name`) still works
correctly — LangGraph merges the partial dict with whatever the checkpointer
already has persisted for that `thread_id`. This is what lets `run_turn()`
avoid re-sending the customer's identity on every single message of a
conversation. Same "prove the mechanism first" discipline as Lessons 24 and 32.

### Lesson 42 — `app_car_rental.py`: one exception handler instead of six

**File:** [`app_car_rental.py`](../app_car_rental.py)

The reference repo registers a separate `@app.exception_handler` for each of
its five custom exception subclasses, each doing nearly identical work (log
the detail, return a generic frontend-safe message). Since every exception in
*this* project's hierarchy already carries its own `status_code` and
`user_message` (Lesson 8), **one** handler for the whole `AppException` base
class covers all of them — adding a new domain exception later needs zero new
wiring here. A second, final `Exception` handler is the safety net for
anything truly unexpected (a library bug, a network failure) — logged with
`exc_info=True` for a full traceback, but the client only ever sees the same
generic `FRONTEND_ERROR_MESSAGE`, regardless of what actually went wrong
internally.

### Lesson 43 — Real bugs only a live server catches

The automated test suite (`TestClient`, which runs the real ASGI app in-
process) caught almost everything — but actually running `uvicorn
app_car_rental:app` surfaced two things `TestClient` never would have:

1. **`TrustedHostMiddleware` rejecting `TestClient`'s own default Host
   header** ("testserver" isn't in `ALLOWED_HOST`). Fixed by pointing the test
   client at `http://localhost` instead of weakening the security config —
   the middleware was *correctly* doing its job.
2. **`LLM_PROVIDER=fake` cannot boot the real app at all** — `build_graph()`
   unconditionally calls `.bind_tools()`, which `FakeListChatModel` doesn't
   implement. This only matters for a live-running server, since every
   offline test builds its graph with `tests/fakes.py::ScriptedChatModel`
   (which *does* support `bind_tools()`) instead of going through the real
   `get_llm()` factory. Documented directly in `llm_factory.py` so nobody
   wastes time on it later.

With a dummy (invalid) `GOOGLE_API_KEY`, the live server was also used to
confirm the full failure path end-to-end: a real `GoogleInvalidRequestError`
(not one of our own `AppException` subclasses) correctly fell through to the
catch-all `Exception` handler, returned a clean `500` with the generic
message, and — critically — **the server kept running** for the next
request. A crash-on-first-bad-request bug would have been much harder to
catch from `TestClient` tests alone, since those don't exercise a real
external network failure.

Also caught: `PyJWT` warning that the dev-default JWT secret
(`"dev-only-change-me"`, 18 bytes) was below HS256's recommended 32-byte
minimum key length — a real, if minor, security hygiene finding, fixed by
lengthening the default rather than just silencing the warning.

---

## Phase 7 — Streamlit UI

The last piece: a thin chat client exercising the public HTTP API. Deliberately
holds **no** business logic, no LLM client, no graph — it's the same contract
a curl command or the eval harness (Phase 8) uses, just rendered nicely.

### Lesson 44 — One backend call per turn, not two

**File:** [`app/ui/streamlit_app.py`](../app/ui/streamlit_app.py)

The UI needs two things per turn: the conversational reply, and a live trace
of what the agent did (routing decision, tool calls, tool results) for the
sidebar panel. The tempting-but-wrong design is to call the plain JSON
`/chat` endpoint for the reply and *separately* call `/chat/stream` for the
trace — but both endpoints ultimately call `run_turn()`, which invokes the
graph. Calling both would run the agent **twice** for one user message: wasted
LLM calls at best, a double-executed mutation (e.g. cancelling a reservation
twice) at worst. `send_chat_message()` instead calls `/chat/stream` exclusively
and derives *both* the trace and the final reply from the one SSE stream.

### Lesson 45 — Parsing Server-Sent Events by hand

`_parse_sse_stream()` is a ~15-line parser for the `event: X\ndata: Y\n\n`
format `sse_starlette` emits. No library dependency needed: SSE is a
deliberately simple text protocol (one event = one `event:` line, one or more
`data:` lines, terminated by a blank line), and `httpx`'s `iter_lines()`
already handles the chunked-transfer decoding — all that's left is grouping
lines into frames and JSON-decoding the accumulated `data:` payload.

### Lesson 46 — A real bug only a browser could catch

Automated tests (`TestClient`, `pytest`) never execute Streamlit's actual
script-rerun model — they can't catch bugs in how the UI *reacts* to a
backend failure. Driving the real running app through an actual browser
(via `open_browser_page`/`click_element`/`type_in_page`) surfaced a genuine
bug no unit test would have: `send_chat_message()` calls
`response.raise_for_status()`, which raises `httpx.HTTPStatusError` on any
backend 500 — and that exception was **uncaught**, bubbling all the way up
through `main()` to crash the entire Streamlit script. Streamlit's own
fallback error display (a raw traceback alert) isn't a terrible failure mode,
but it's a jarring one for an end user mid-conversation.

The fix wraps every backend call site (`send_chat_message`, `send_confirmation`,
`login`) in `try/except httpx.HTTPError`, rendering a friendly chat-bubble
error (`st.error(...)`) instead of letting the exception escape. This was
verified by literally reproducing the failure (a deliberately invalid
`GOOGLE_API_KEY`, the same real backend code path from Lesson 43) through the
browser, confirming the raw traceback *before* the fix and the friendly error
message *after* it, on the same live stack.

**Lesson: for UI code specifically, no amount of `TestClient`/pytest coverage
substitutes for actually clicking through the running app once.** The
backend's automated tests were already thorough and passing the whole time —
the bug was entirely in how the frontend reacted to a backend error, which is
a category of bug that only shows up when something actually renders.

---

## Phase 8 — Tests + eval harness

The final piece the brief explicitly grades: "Agent correctly routes to right
tool." This phase builds `tests/evals/dataset.yaml` (the 5 brief sample
conversations + 5 adversarial probes) and a harness graded by exact
`expected_tool` match — per the Q6 planning decision, no LLM-as-judge.

### Lesson 45 — Not every eval case needs an LLM to grade

The key insight that shaped this harness: the hybrid router (Lesson 28)
already makes **half the dataset's routing fully deterministic** — any case
with an `R\d{3}` reservation ID is force-routed with zero LLM involvement.
That means grading splits cleanly into three tiers of increasing cost:

1. **Router-decision check** (`test_router_matches_expected_routing`) — calls
   `resolve_route()` directly, a pure function. Confirms the router neither
   force-routes something it shouldn't, nor fails to force-route something it
   should. Runs in milliseconds, zero LLM cost, covers all 10 cases.
2. **Deterministic tool execution** (`test_deterministic_tool_execution`) —
   for the 4 rule-routed cases, runs the *real* graph with a scripted fake
   model (which only phrases the final answer, never chooses the tool) and
   the `isolated_mock_data` fixture, checking what actually happened:
   paused for confirmation, denied with the right message, or executed
   cleanly. Still zero LLM cost.
3. **Real tool-choice** (`test_react_tool_choice_matches_expected`) — for the
   6 cases that genuinely need a model to decide (vehicle search, policy
   questions, refusals), builds the graph with the *real* configured
   provider via `get_llm()`. Marked `@pytest.mark.llm`.

The dataset.yaml itself records which tier each case belongs to via a
`routing: rule|react` field — making the dataset self-documenting about its
own cost, not just its expected outcomes.

### Lesson 46 — Skip, don't fail, when a precondition is missing

Tier 3's tests originally **failed** outright with `ConfigurationException:
GOOGLE_API_KEY is required` when no provider key was configured — technically
correct, but semantically wrong: "I can't run this check here" is a different
condition from "this check ran and found a bug." Added an explicit
`pytest.skip(...)` guard before calling `get_llm()`, checking whether the
configured provider's key is actually present. Now `uv run pytest -m llm
tests/evals` cleanly reports `6 skipped` rather than `6 failed` in a
credential-less environment — a grader with a real key configured would see
these actually run and grade the model's tool choice.

### Lesson 47 — Building the eval dataset found a real product bug

Writing the `double_cancel_already_cancelled` adversarial case (cancel an
already-cancelled reservation) surfaced something the HITL tests hadn't
caught: `cancel_reservation`'s original implementation checked ownership,
then unconditionally called `interrupt()` to ask for confirmation, and only
checked whether the reservation was actually cancellable *after* the customer
confirmed. That means a customer trying to cancel an already-cancelled
booking would be asked "are you sure?" for an action already guaranteed to
fail — confusing, wasted round-trip, and a pause recorded in the checkpointer
for nothing.

**Fix:** both `cancel_reservation` and `modify_reservation` now check
`reservation.status != ReservationStatus.CONFIRMED` and return a plain,
immediate message *before* ever calling `interrupt()`. This is the second
time in this project that building the *test* (not just running it)
surfaced a real design gap — Lesson 31's Windows file-lock bug was found by
running tests under stress; this one was found by the discipline of writing
down, in advance, exactly what "correct" looks like for an edge case. **An
eval dataset isn't just a grading rubric — writing it is itself a design
review.**

### Lesson 48 — Consolidating a duplicated fixture

By Phase 8, three different test files (`test_hitl_flow.py`, `test_api.py`,
and now the eval harness) all needed the same "point the agent's singleton
repos at a disposable copy of the mock data" fixture. Rather than copy it a
third time, it moved into `tests/conftest.py` as `isolated_mock_data`,
available to every test file automatically (pytest fixtures defined in
`conftest.py` need no import). Classic rule of three: duplicate once for
speed, copy-paste a second time if it's genuinely simpler, but the third
repetition is the signal to extract a shared fixture — any earlier and you
risk guessing the wrong shared abstraction before you've seen enough call
sites to know what it should look like.

---

## Phase 9 — README, architecture docs, ADRs, Docker

The final packaging phase: turning eight phases of working code into
something a reviewer can actually navigate.

### Lesson 49 — ADRs are for decisions that survive the code that made them

**Files:** [`docs/adr/`](../docs/adr/)

Six short ADRs (Architecture Decision Records), each following the same
shape: Context, Decision, Consequences. The test for whether something
deserves an ADR versus just a code comment: *would a future contributor
reasonably ask "why isn't this just X instead?"* — "why `interrupt()` instead
of a bare tool loop," "why Chroma instead of pgvector," "why is
`modify_reservation` dates-only," "why two config tiers," "why a hybrid
router instead of pure ReAct or a pure classifier," "why such strict secrets
hygiene." Each ADR cross-references the specific Learning Notes lesson where
the decision was actually *made* (often mid-debugging, not upfront) — the
ADR is the durable summary; the lesson is the full story of how it was
discovered.

### Lesson 50 — Writing a Dockerfile you can't build-test

**Files:** [`Dockerfile`](../Dockerfile), [`Dockerfile.ui`](../Dockerfile.ui),
[`docker-compose.yml`](../docker-compose.yml)

Docker wasn't installed in this environment, so `docker build` could never
actually be run to catch mistakes the way the live `uvicorn`/Streamlit smoke
tests did in Phases 6–7. The mitigation: **trace every path the Dockerfile
depends on against the real code**, the same way an API's constructor kwargs
were verified with `inspect.signature()` rather than guessed. Concretely,
every relative-path assumption in `app/utils/config.py`,
`app/service/rag/ingest_service.py`, and `app/agent/deps.py` (`Path(__file__)
.resolve().parents[N]`) was walked by hand against the Docker image's actual
`WORKDIR /app` + `COPY app/ /app/app/` layout to confirm `N` still resolves
correctly inside the container. This is real verification, just static
instead of dynamic — and it's explicitly disclosed as untested in the README
rather than silently presented as working. **Never claim something works
when the only evidence is "I wrote it carefully."**

A concrete design choice this tracing produced: the policy index is built
**at image build time** (`RUN python scripts/build_index.py` in the
Dockerfile, after the non-root user is created and owns `.chroma/`), not at
container startup — so the container is immediately ready to serve requests
the moment it starts, rather than needing a first-request-triggers-indexing
race condition or a separate init container.

### Lesson 51 — README as a map, not a duplicate

**File:** [`README.md`](../README.md)

The README deliberately doesn't re-explain what `docs/LEARNING_NOTES.md`
already covers in depth — it's a map pointing to the detailed material
(architecture diagrams, ADRs, the learning log) rather than a second copy of
it. The "Sample conversations" section is honest about a real constraint:
no API key was available in the build environment to generate genuine
screenshots, so the README documents exactly how to reproduce and capture
them rather than fabricating placeholder images — consistent with the
project's running theme of disclosing limitations precisely rather than
papering over them.
