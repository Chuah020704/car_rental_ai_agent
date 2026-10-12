"""End-to-end graph wiring tests using a scripted fake chat model — no network,
no API key required for the first two tests. The third test exercises the
real RAG pipeline through the graph and is marked `llm` accordingly.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import build_graph
from tests.fakes import ScriptedChatModel


def test_forced_router_path_skips_llm_tool_selection() -> None:
    """Router forces get_reservation for an R-number directly; the LLM is only
    called once, to compose the final natural-language answer."""
    llm = ScriptedChatModel(responses=[AIMessage(content="Your reservation R001 is confirmed.")])
    graph = build_graph(llm)

    result = graph.invoke(
        {
            "messages": [HumanMessage(content="What is the status of my reservation R001?")],
            "customer_id": "C001",
            "customer_name": "Aisyah Rahman",
            "route_forced": False,
        }
    )

    final_message = result["messages"][-1]
    assert "R001" in final_message.content
    # Exactly one LLM call happened — the forced tool call skipped the first.
    assert llm._call_count == 1


def test_react_path_lets_llm_choose_the_tool() -> None:
    """A vehicle-search question has no forcible rule match, so the LLM itself
    must emit the tool call — this only needs mock JSON data, no Chroma."""
    tool_call_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "search_vehicles",
                "args": {
                    "location": "Penang",
                    "pickup_date": "2026-10-10",
                    "return_date": "2026-10-15",
                    "passengers": 4,
                    "category": "suv",
                },
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )
    final_message = AIMessage(content="I found an SUV in Penang for you.")
    llm = ScriptedChatModel(responses=[tool_call_message, final_message])
    graph = build_graph(llm)

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="I want to rent an SUV in Penang from 10 Oct to 15 Oct for 4 people"
                )
            ],
            "customer_id": "C001",
            "customer_name": "Aisyah Rahman",
            "route_forced": False,
        }
    )

    assert result["messages"][-1].content == final_message.content
    assert llm._call_count == 2


@pytest.mark.llm
def test_policy_question_cites_source_through_the_full_graph() -> None:
    """Exercises the real Chroma + fastembed pipeline through policy_rag,
    proving the citation ("source: cancellation.md") survives end-to-end."""
    tool_call_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "policy_rag",
                "args": {"query": "what happens if I cancel my reservation"},
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )
    final_message = AIMessage(
        content="You can cancel for free up to 48 hours before pickup (source: cancellation.md)."
    )
    llm = ScriptedChatModel(responses=[tool_call_message, final_message])
    graph = build_graph(llm)

    result = graph.invoke(
        {
            "messages": [HumanMessage(content="What happens if I cancel my reservation?")],
            "customer_id": "C001",
            "customer_name": "Aisyah Rahman",
            "route_forced": False,
        }
    )

    tool_message = result["messages"][-2]
    assert "cancellation.md" in tool_message.content
    assert result["messages"][-1].content == final_message.content
