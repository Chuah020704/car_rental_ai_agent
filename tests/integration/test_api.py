"""Full HTTP-layer tests: /auth/token -> /chat -> /chat/confirm, against the
real FastAPI app via TestClient. The graph's LLM is swapped for a scripted
fake (same technique as tests/integration/test_agent_graph.py) so no API key
or network call is needed; lifespan is never triggered (app.state.graph is
set manually), which is also why these tests need the same isolated mock
data fixture (see tests/conftest.py) as the HITL graph tests.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app_car_rental import create_app
from tests.fakes import ScriptedChatModel


def _make_client(llm: ScriptedChatModel) -> TestClient:
    app = create_app()
    app.state.graph = build_graph(llm, checkpointer=InMemorySaver())
    # TrustedHostMiddleware only allows "localhost;127.0.0.1" (see .env.example);
    # httpx's TestClient defaults to Host: testserver, which that middleware
    # correctly rejects with 400 — point it at an allowed host instead.
    return TestClient(app, base_url="http://localhost")


def _login(client: TestClient, customer_id: str) -> str:
    response = client.post("/auth/token", json={"customer_id": customer_id})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def test_list_customers_returns_mock_customers(isolated_mock_data: Path) -> None:
    client = _make_client(ScriptedChatModel(responses=[]))
    response = client.get("/auth/customers")
    assert response.status_code == 200
    ids = {c["customer_id"] for c in response.json()}
    assert "C001" in ids


def test_token_issuance_rejects_unknown_customer(isolated_mock_data: Path) -> None:
    client = _make_client(ScriptedChatModel(responses=[]))
    response = client.post("/auth/token", json={"customer_id": "C999"})
    assert response.status_code == 404


def test_chat_requires_auth(isolated_mock_data: Path) -> None:
    client = _make_client(ScriptedChatModel(responses=[]))
    response = client.post("/api/agent/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_forced_router_path_returns_answer(isolated_mock_data: Path) -> None:
    llm = ScriptedChatModel(responses=[AIMessage(content="Your reservation R001 is confirmed.")])
    client = _make_client(llm)
    token = _login(client, "C001")

    response = client.post(
        "/api/agent/chat",
        json={"message": "What is the status of my reservation R001?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "R001" in body["message"]
    assert body["thread_id"]


def test_chat_continues_same_thread(isolated_mock_data: Path) -> None:
    llm = ScriptedChatModel(
        responses=[
            AIMessage(content="Your reservation R001 is confirmed."),
            AIMessage(content="It's a Perodua Myvi."),
        ]
    )
    client = _make_client(llm)
    token = _login(client, "C001")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/agent/chat",
        json={"message": "What is the status of my reservation R001?"},
        headers=headers,
    )
    thread_id = first.json()["thread_id"]

    second = client.post(
        "/api/agent/chat",
        json={"message": "What vehicle is it?", "thread_id": thread_id},
        headers=headers,
    )

    assert second.status_code == 200
    assert second.json()["thread_id"] == thread_id
    assert "Myvi" in second.json()["message"]


def test_cancel_hitl_flow_over_http(isolated_mock_data: Path) -> None:
    llm = ScriptedChatModel(responses=[AIMessage(content="Your reservation has been cancelled.")])
    client = _make_client(llm)
    token = _login(client, "C002")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/agent/chat",
        json={"message": "I want to cancel my booking R002"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["confirmation"]["reservation_id"] == "R002"
    thread_id = body["thread_id"]

    confirm_response = client.post(
        "/api/agent/confirm",
        json={"thread_id": thread_id, "approved": True},
        headers=headers,
    )
    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    assert confirm_body["status"] == "ok"
    assert "cancelled" in confirm_body["message"].lower()


def test_health_and_root_need_no_auth() -> None:
    client = _make_client(ScriptedChatModel(responses=[]))
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
