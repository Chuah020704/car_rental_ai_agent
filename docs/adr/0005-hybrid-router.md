# ADR 0005: Hybrid router (deterministic rules + ReAct fallback)

## Context

The brief's architecture diagram shows an explicit "Router Node." Two pure
options were considered: (A) a dedicated LLM call just for intent
classification (the reference repo's `IntentClassifier` pattern), or (B) pure
ReAct, letting the model's own tool-choice be the only routing signal.

## Decision

Neither pure option: a regex fast-path forces a tool call directly (skipping
an LLM round-trip entirely) only when a reservation ID is present *and* the
tool's full arguments are safely derivable from the message alone
(`get_reservation`, `cancel_reservation`). Everything else — including
"modify" requests, which need real date parsing a regex shouldn't attempt —
defers to the ReAct agent's own tool-choice.

## Consequences

- Zero-cost, 100%-deterministic routing for the common cases, independent of
  model quality or cost.
- Still handles compound questions naturally (e.g. "is my R001 refundable?"
  needs both `get_reservation` and `policy_rag`) since ReAct remains fully
  available for anything the rules don't cover.
- The eval harness (`tests/evals/`) can grade half its dataset with zero LLM
  calls, because the router's decision is a pure function independent of any
  model (see Lesson 45).
- A rule that's too eager would silently short-circuit a case the model
  should have reasoned about — mitigated by requiring argument
  derivability, not just category match, before forcing a tool call.
