"""Tool registry — register every new tool here; this list is what gets bound
to the LLM in app/agent/graph.py.
"""

from app.agent.tools.cancel_reservation import cancel_reservation
from app.agent.tools.get_reservation import get_reservation
from app.agent.tools.modify_reservation import modify_reservation
from app.agent.tools.policy_rag import policy_rag
from app.agent.tools.search_vehicles import search_vehicles

TOOLS = [search_vehicles, get_reservation, policy_rag, cancel_reservation, modify_reservation]

__all__ = ["TOOLS"]
