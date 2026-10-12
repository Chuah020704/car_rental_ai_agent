# Architecture

## Layered dependency direction

```mermaid
graph LR
    domain["domain<br/>(enums / models)"] --> repos["repositories<br/>(data access)"]
    repos --> service["service<br/>(business logic)"]
    service --> agent["agent<br/>(tools, router, graph)"]
    agent --> api["api<br/>(FastAPI routers)"]
    api --> ui["ui<br/>(Streamlit)"]
```

Dependencies only point inward-to-outward: `agent` never imports from `api`
or `ui`; `service` never imports from `agent`. See `AGENTS.md`.

## The LangGraph agent

```mermaid
graph TD
    START((start)) --> router[Router Node]
    router -->|"R-number + forcible tool<br/>(get_reservation, cancel_reservation)"| tools[Tools Node]
    router -->|"everything else"| agentNode[Agent Node<br/>LLM + bound tools]
    agentNode -->|tool_calls present| tools
    agentNode -->|no tool_calls| END((end))
    tools --> agentNode
    tools -.->|interrupt pauses here| PAUSE{{"⏸ awaiting confirmation"}}
```

- **Router Node** (`app/agent/router.py`): regex fast-path forces a tool call
  directly for unambiguous ID-based cases, skipping an LLM round-trip
  entirely; everything else defers to the agent node's own tool-choice.
- **Agent Node**: binds all five tools to the configured LLM
  (`app/service/llm/llm_factory.py`) and lets it decide, chaining multiple
  tools for compound questions.
- **Tools Node**: a prebuilt `ToolNode` executing whichever tool the model
  (or the router) selected. `cancel_reservation`/`modify_reservation` call
  `interrupt()` here, pausing graph execution until a separate
  `Command(resume=...)` call continues it.

## Human-in-the-loop confirmation sequence

```mermaid
sequenceDiagram
    participant U as Customer
    participant UI as Streamlit
    participant API as FastAPI
    participant G as LangGraph
    participant CP as SqliteSaver

    U->>UI: "cancel my booking R002"
    UI->>API: POST /api/agent/chat/stream
    API->>G: graph.invoke(..., thread_id)
    G->>G: router forces cancel_reservation
    G->>G: interrupt() pauses mid-tool
    G->>CP: persist full state
    G-->>API: result["__interrupt__"]
    API-->>UI: SSE confirmation_required + done
    UI-->>U: render summary + Confirm/Decline

    U->>UI: clicks Confirm
    UI->>API: POST /api/agent/confirm
    API->>G: graph.invoke(Command(resume={"approved": true}), thread_id)
    G->>CP: load persisted state
    G->>G: resume inside cancel_reservation, mutate, continue to agent node
    G-->>API: final answer
    API-->>UI: JSON response
    UI-->>U: "Reservation R002 has been cancelled."
```

## Auth dual-mode

```mermaid
graph LR
    req["Incoming request<br/>Authorization: Bearer &lt;token&gt;"] --> dep[get_current_customer]
    dep -->|AUTH_MODE=simulated| jwt["Decode locally-signed JWT<br/>(HS256, our own secret)"]
    dep -->|AUTH_MODE=entra| entra["Validate against Entra's JWKS<br/>(RS256, PyJWKClient)"]
    jwt --> customer[CurrentCustomer]
    entra --> upn["map preferred_username<br/>via CustomerDirectory"] --> customer
    customer --> state["graph state<br/>(InjectedState, never LLM-controlled)"]
```

See `docs/adr/` for the reasoning behind each of these decisions.
