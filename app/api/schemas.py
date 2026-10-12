"""Request/response models for the FastAPI routers."""

from typing import Any

from pydantic import BaseModel


class TokenRequest(BaseModel):
    customer_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 scheme name, not a secret
    customer_id: str
    customer_name: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    status: str  # "ok" or "awaiting_confirmation"
    message: str | None = None
    confirmation: dict[str, Any] | None = None


class ConfirmRequest(BaseModel):
    thread_id: str
    approved: bool
