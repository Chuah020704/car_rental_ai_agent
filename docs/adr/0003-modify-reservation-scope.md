# ADR 0003: `modify_reservation` is dates-only

## Context

The brief's sample conversations only exercise cancellation in detail.
"Modify" is mentioned only in the LangGraph agent flow diagram, without
specifying what's modifiable.

## Decision

`modify_reservation` only accepts new `pickup_date`/`return_date`. Vehicle
swaps and passenger-count changes are explicitly out of scope — the agent's
system prompt and the tool's own docstring instruct the model to tell the
customer to cancel and make a new booking instead.

## Consequences

- `ReservationService.modify_reservation()` only needs to re-validate date
  conflicts against other active reservations on the *same* vehicle — it
  never needs to re-run vehicle search/availability logic for a *different*
  vehicle, keeping the business rule small and fully unit-testable.
- A customer asking "can I switch to a bigger car?" gets redirected to
  cancel-and-rebook rather than silently failing or (worse) a tool accepting
  a `vehicle_id` argument that bypasses `search_vehicles`' own availability
  checks.
- If broader modification support is ever needed, it is additive: a new
  tool (or an extended schema) rather than a breaking change to this one.
