"""The LangGraph ReAct agent: router -> agent (LLM+tools) -> tools -> agent -> ...

Router forces a tool call deterministically for the common, unambiguous cases
(see app/agent/router.py); everything else goes through the agent node, which
binds TOOLS to the LLM and lets the model choose — including chaining multiple
tools for compound questions (e.g. "is my R001 refundable?" needs both
get_reservation AND policy_rag).
"""

from datetime import date
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.router import route_after_router, route_node
from app.agent.state import AgentState
from app.agent.tools import TOOLS
from app.models.prompt_template import PromptTemplates


def build_graph(
    llm: BaseChatModel, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    """Compile the agent graph.

    `llm` is injected (not constructed internally) so tests can pass a
    scripted fake chat model instead of a real provider — see
    tests/integration/test_agent_graph.py. `checkpointer` is required for the
    interrupt()-based confirmation flow in cancel_reservation/modify_reservation
    to work at all (see app/core/checkpoint.py); omit it only for graphs that
    never pause (e.g. a quick smoke test of read-only tools).
    """
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict[str, Any]:
        system_prompt = PromptTemplates.AGENT_SYSTEM_PROMPT.format(
            today=date.today().isoformat(),
            customer_name=state["customer_name"],
            customer_id=state["customer_id"],
        )
        messages = [SystemMessage(content=system_prompt), *state["messages"]]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("router", route_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router", route_after_router, {"tools": "tools", "agent": "agent"}
    )
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
