"""Streamlit chat UI for the Car Rental AI Agent.

Talks to the FastAPI backend over HTTP only — this script holds no business
logic, no LLM client, no graph; it's purely a thin client exercising the same
public API a curl command or the eval harness would use. Run with:
    uv run streamlit run app/ui/streamlit_app.py
"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8081")


@dataclass
class ChatTurnResult:
    text: str | None
    confirmation: dict[str, Any] | None
    thread_id: str | None
    trace: list[dict[str, Any]] = field(default_factory=list)


def _parse_sse_stream(response: httpx.Response) -> Iterator[tuple[str, dict[str, Any]]]:
    """Minimal SSE frame parser for sse_starlette's `event: X\\ndata: Y\\n\\n` format."""
    event_type: str | None = None
    data_lines: list[str] = []
    for line in response.iter_lines():
        if line == "":
            if event_type is not None and data_lines:
                yield event_type, json.loads("".join(data_lines))
            event_type, data_lines = None, []
            continue
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())


def send_chat_message(message: str, thread_id: str | None, token: str) -> ChatTurnResult:
    """One user turn: streams routing/tool_call/tool_result/confirmation
    events, returning the accumulated trace plus the final answer (or a
    pending confirmation) — exactly one backend call per turn, matching
    app.service.agent_runner's "one invoke per turn" contract. Never also
    call /chat for the same message — that would run the agent (and any
    mutating tools) twice.
    """
    trace: list[dict[str, Any]] = []
    text: str | None = None
    confirmation: dict[str, Any] | None = None
    resolved_thread_id = thread_id

    with httpx.stream(
        "POST",
        f"{API_BASE_URL}/api/agent/chat/stream",
        json={"message": message, "thread_id": thread_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as response:
        response.raise_for_status()
        for event_type, payload in _parse_sse_stream(response):
            if event_type in {"routing", "tool_call", "tool_result"}:
                trace.append({"type": event_type, **payload})
            elif event_type == "confirmation_required":
                confirmation = payload
            elif event_type == "delta":
                text = payload.get("text")
            elif event_type == "done":
                resolved_thread_id = payload.get("thread_id", resolved_thread_id)
                break

    return ChatTurnResult(
        text=text, confirmation=confirmation, thread_id=resolved_thread_id, trace=trace
    )


def send_confirmation(thread_id: str, approved: bool, token: str) -> str:
    response = httpx.post(
        f"{API_BASE_URL}/api/agent/confirm",
        json={"thread_id": thread_id, "approved": approved},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return str(body.get("message") or "")


def fetch_customers() -> list[dict[str, Any]]:
    response = httpx.get(f"{API_BASE_URL}/auth/customers", timeout=10.0)
    response.raise_for_status()
    customers: list[dict[str, Any]] = response.json()
    return customers


def login(customer_id: str) -> dict[str, Any]:
    response = httpx.post(
        f"{API_BASE_URL}/auth/token", json={"customer_id": customer_id}, timeout=10.0
    )
    response.raise_for_status()
    token_data: dict[str, Any] = response.json()
    return token_data


def _init_session_state() -> None:
    defaults: dict[str, Any] = {
        "token": None,
        "customer_id": None,
        "customer_name": None,
        "thread_id": None,
        "messages": [],
        "trace": [],
        "pending_confirmation": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_conversation() -> None:
    st.session_state.thread_id = None
    st.session_state.messages = []
    st.session_state.trace = []
    st.session_state.pending_confirmation = None


def _render_trace_event(event: dict[str, Any]) -> None:
    event_type = event.get("type")
    if event_type == "routing":
        st.caption(f"🧭 routed via **{event.get('source')}** → {event.get('category')}")
    elif event_type == "tool_call":
        st.caption(f"🔧 calling `{event.get('tool')}`")
        st.json(event.get("args", {}), expanded=False)
    elif event_type == "tool_result":
        st.caption(f"✅ `{event.get('tool')}` returned")
        st.code(str(event.get("content", ""))[:500])


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🚗 Car Rental AI Agent")

        if st.session_state.token is None:
            st.subheader("Sign in")
            try:
                customers = fetch_customers()
            except httpx.HTTPError as exc:
                st.error(f"Can't reach the API at {API_BASE_URL}: {exc}")
                return
            options = {c["customer_name"]: c["customer_id"] for c in customers}
            selected_name = st.selectbox("Customer", list(options.keys()))
            if st.button("Log in", type="primary"):
                try:
                    token_data = login(options[selected_name])
                except httpx.HTTPError as exc:
                    st.error(f"Login failed: {exc}")
                    return
                st.session_state.token = token_data["access_token"]
                st.session_state.customer_id = token_data["customer_id"]
                st.session_state.customer_name = token_data["customer_name"]
                st.rerun()
            return

        st.success(f"Signed in as **{st.session_state.customer_name}**")
        st.caption(f"Customer ID: {st.session_state.customer_id}")
        if st.button("Reset conversation"):
            _reset_conversation()
            st.rerun()
        if st.button("Log out"):
            st.session_state.token = None
            st.session_state.customer_id = None
            st.session_state.customer_name = None
            _reset_conversation()
            st.rerun()

        st.divider()
        st.subheader("🔍 Tool call trace")
        if not st.session_state.trace:
            st.caption("Trace from the most recent turn will appear here.")
        for event in st.session_state.trace:
            _render_trace_event(event)


def _render_chat_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _render_pending_confirmation() -> None:
    confirmation = st.session_state.pending_confirmation
    if confirmation is None:
        return

    with st.chat_message("assistant"):
        st.warning(confirmation.get("summary", "This action needs your confirmation."))
        col_confirm, col_decline = st.columns(2)
        if col_confirm.button("✅ Confirm", type="primary", key="confirm_yes"):
            try:
                reply = send_confirmation(st.session_state.thread_id, True, st.session_state.token)
            except httpx.HTTPError as exc:
                st.error(f"Couldn't confirm: {exc}")
                return
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.pending_confirmation = None
            st.rerun()
        if col_decline.button("❌ Cancel", key="confirm_no"):
            try:
                reply = send_confirmation(st.session_state.thread_id, False, st.session_state.token)
            except httpx.HTTPError as exc:
                st.error(f"Couldn't decline: {exc}")
                return
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.pending_confirmation = None
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Car Rental AI Agent", page_icon="🚗")
    _init_session_state()
    _render_sidebar()

    if st.session_state.token is None:
        st.info("Sign in from the sidebar to start chatting.")
        return

    st.title("Car Rental AI Agent")
    _render_chat_history()
    _render_pending_confirmation()

    if st.session_state.pending_confirmation is not None:
        return  # don't accept new messages mid-confirmation

    user_input = st.chat_input("Ask about vehicles, reservations, or policies…")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = send_chat_message(
                    user_input, st.session_state.thread_id, st.session_state.token
                )
            except httpx.HTTPError as exc:
                # A backend/LLM failure must never crash the whole UI script —
                # render it as a normal chat bubble instead of a raw traceback.
                error_text = (
                    "Sorry, something went wrong reaching the assistant. Please try again."
                )
                st.error(error_text)
                st.caption(f"({exc})")
                st.session_state.messages.append({"role": "assistant", "content": error_text})
                return

        st.session_state.thread_id = result.thread_id
        st.session_state.trace = result.trace

        if result.confirmation is not None:
            st.session_state.pending_confirmation = result.confirmation
        else:
            st.markdown(result.text or "")
            st.session_state.messages.append(
                {"role": "assistant", "content": result.text or ""}
            )


if __name__ == "__main__":
    main()
