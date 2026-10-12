"""Health/liveness endpoints — no auth required, used by container orchestrators."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, str]:
    return {"api": "Car Rental AI Agent is running"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
