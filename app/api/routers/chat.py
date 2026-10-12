"""POST /api/agent/chat (JSON), POST /api/agent/chat/stream (SSE), and
POST /api/agent/confirm — all delegate to app.service.agent_runner, so there
is exactly one place that knows how to invoke the graph.
"""

from fastapi import APIRouter, Depends, Request
from langgraph.graph.state import CompiledStateGraph
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import ChatRequest, ChatResponse, ConfirmRequest
from app.dependencies.auth import CurrentCustomer, get_current_customer
from app.service.agent_runner import run_confirm, run_turn
from app.service.llm.streaming import stream_turn_result

router = APIRouter(prefix="/api/agent", tags=["chat"])


def get_graph(request: Request) -> CompiledStateGraph:
    graph: CompiledStateGraph = request.app.state.graph
    return graph


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    customer: CurrentCustomer = Depends(get_current_customer),
    graph: CompiledStateGraph = Depends(get_graph),
) -> ChatResponse:
    turn = run_turn(
        graph,
        message=payload.message,
        thread_id=payload.thread_id,
        customer_id=customer.customer_id,
        customer_name=customer.customer_name,
    )
    return turn.response


@router.post("/confirm", response_model=ChatResponse)
def confirm(
    payload: ConfirmRequest,
    _customer: CurrentCustomer = Depends(get_current_customer),
    graph: CompiledStateGraph = Depends(get_graph),
) -> ChatResponse:
    turn = run_confirm(graph, thread_id=payload.thread_id, approved=payload.approved)
    return turn.response


@router.post("/chat/stream")
def chat_stream(
    payload: ChatRequest,
    customer: CurrentCustomer = Depends(get_current_customer),
    graph: CompiledStateGraph = Depends(get_graph),
) -> EventSourceResponse:
    turn = run_turn(
        graph,
        message=payload.message,
        thread_id=payload.thread_id,
        customer_id=customer.customer_id,
        customer_name=customer.customer_name,
    )
    return EventSourceResponse(stream_turn_result(turn))
