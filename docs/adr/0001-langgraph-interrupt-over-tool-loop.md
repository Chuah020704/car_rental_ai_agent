# ADR 0001: LangGraph `interrupt()` over a bare tool-calling loop

## Context

High-impact actions (cancelling or modifying a reservation) must pause for
explicit customer confirmation before taking effect. A simpler alternative —
a bare tool-calling loop with a hard iteration cap and no checkpointer (the
pattern the `applications.ai.agenticbot.backend` reference repo uses for its
BSOD analysis tool) — never truly "pauses": it either completes a tool call
immediately or doesn't call it at all within that process's lifetime.

## Decision

Use LangGraph's `interrupt()` primitive together with a `BaseCheckpointSaver`
(`SqliteSaver` in production, `InMemorySaver` in tests). A tool calls
`interrupt({...})`, which suspends graph execution *inside that exact tool
call* and persists the full state to the checkpointer. A separate request
later resumes with `Command(resume={"approved": bool})`, continuing exactly
where it left off.

## Consequences

- The pause survives across separate HTTP requests and even a server
  restart — proven in Lesson 36 by restarting the API mid-pause during
  manual testing.
- Required adding `app/core/checkpoint.py` and threading a checkpointer
  through `build_graph()`, `app_car_rental.py`'s lifespan, and every test
  that exercises a mutating tool.
- Mutation tools must re-validate business rules *after* resume, not just
  before `interrupt()` — state can change in the gap between pause and
  resume (see `cancel_reservation`/`modify_reservation`'s post-confirmation
  checks).
