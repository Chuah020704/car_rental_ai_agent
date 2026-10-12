"""Shared helper: turn a caught AppException into safe text for the LLM/user.

Never let a domain exception's internal `detail` leak into a tool result — the
service layer already logs the real detail; the tool only ever surfaces the
customer-safe `user_message` (or a generic fallback), same boundary FastAPI's
exception handlers enforce at the API layer (Phase 6).
"""

from app.utils.exception.exceptions import AppException


def safe_tool_error(exc: AppException) -> str:
    return exc.user_message or "Sorry, I couldn't complete that request."
