"""Evaluation harness: grades the agent's tool-routing behavior against
tests/evals/dataset.yaml — the 5 brief sample conversations plus 5
adversarial probes (IDOR, idempotency, prompt injection, out-of-scope,
budget-constrained search).

Three tiers, cheapest first:
1. Router-decision check — zero LLM cost, pure function.
2. Deterministic tool execution — real graph + scripted fake model, still
   zero LLM cost, for cases the router force-routes.
3. Real tool-choice — a real provider must decide which tool to call; marked
   `llm` so `make test` skips it without API keys configured.

Grading is exact expected_tool match only (no LLM-as-judge) — see the
planning Q6 decision.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.agent.router import resolve_route
from app.service.llm.llm_factory import get_llm
from app.utils.config import get_config_dict, get_settings
from tests.fakes import ScriptedChatModel

_DATASET_PATH = Path(__file__).parent / "dataset.yaml"


def _load_dataset() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = yaml.safe_load(_DATASET_PATH.read_text(encoding="utf-8"))
    return data


DATASET = _load_dataset()
RULE_CASES = [c for c in DATASET if c["routing"] == "rule"]
REACT_CASES = [c for c in DATASET if c["routing"] == "react"]


@pytest.mark.parametrize("case", DATASET, ids=[c["id"] for c in DATASET])
def test_router_matches_expected_routing(case: dict[str, Any]) -> None:
    """The router must force-route exactly the cases it's supposed to, and
    defer to ReAct for everything else — a regression test for the router
    rules themselves, independent of LLM behavior."""
    decision, _reservation_id = resolve_route(case["message"])
    assert decision.source.value == case["routing"], (
        f"expected routing={case['routing']!r} but router chose {decision.source.value!r}"
    )
    if case["routing"] == "rule":
        assert decision.tool == case["expected_tool"]


@pytest.mark.parametrize("case", RULE_CASES, ids=[c["id"] for c in RULE_CASES])
def test_deterministic_tool_execution(case: dict[str, Any], isolated_mock_data: Path) -> None:
    """For router-forced cases, run the real graph (a scripted fake model
    only phrases the final answer — it never chooses the tool) and check
    what actually happened: paused for confirmation, denied, or executed,
    matching the case's expectations.
    """
    llm = ScriptedChatModel(responses=[AIMessage(content="(final answer placeholder)")])
    graph = build_graph(llm, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": f"eval-{case['id']}"}}

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=case["message"])],
            "customer_id": case["customer_id"],
            "customer_name": case["customer_name"],
            "route_forced": False,
        },
        config=config,
    )

    if case.get("requires_confirmation"):
        assert "__interrupt__" in result, "expected the tool to pause for confirmation"
        return

    tool_message = result["messages"][-2]
    assert tool_message.name == case["expected_tool"]

    if case.get("expect_denied"):
        denial_markers = ("no reservation found", "already", "cannot")
        assert any(marker in tool_message.content.lower() for marker in denial_markers), (
            f"expected a denial/guard message, got: {tool_message.content!r}"
        )


@pytest.mark.llm
@pytest.mark.parametrize("case", REACT_CASES, ids=[c["id"] for c in REACT_CASES])
def test_react_tool_choice_matches_expected(case: dict[str, Any]) -> None:
    """Grades the real model's own tool-choice — needs a configured provider
    (GOOGLE_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY per .env). Run with
    `uv run pytest -m llm tests/evals`. Skipped (not failed) when no key is
    configured — "can't run this here" is a different condition from "this
    is broken."
    """
    settings = get_settings()
    config = get_config_dict()
    provider = settings.llm.llm_provider
    has_key = {
        "google": settings.llm.google_api_key,
        "openai": settings.llm.openai_api_key,
        "anthropic": settings.llm.anthropic_api_key,
    }.get(provider)
    if not has_key:
        pytest.skip(f"no API key configured for llm_provider={provider!r}")

    llm = get_llm(settings, config)
    graph = build_graph(llm, checkpointer=InMemorySaver())
    thread_config = {"configurable": {"thread_id": f"eval-{case['id']}"}}

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=case["message"])],
            "customer_id": case["customer_id"],
            "customer_name": case["customer_name"],
            "route_forced": False,
        },
        config=thread_config,
    )

    tool_calls_made = [
        call["name"]
        for msg in result["messages"]
        if isinstance(msg, AIMessage)
        for call in msg.tool_calls
    ]

    if case["expected_tool"] is None:
        assert not tool_calls_made, f"expected no tool call, but got: {tool_calls_made}"
    else:
        assert case["expected_tool"] in tool_calls_made, (
            f"expected {case['expected_tool']!r} to be called, got: {tool_calls_made}"
        )
