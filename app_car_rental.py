"""FastAPI application entrypoint.

Wires together: settings/config, the LangGraph agent (LLM + checkpointer),
middleware (request context, rate limiting, CORS, trusted host), a single
exception-handling boundary, and the routers. Run with:
    uv run uvicorn app_car_rental:app --reload --port 8081
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import RequestContextMiddleware
from app.api.rate_limit import RateLimitMiddleware
from app.api.routers import auth, chat, health
from app.core.checkpoint import checkpointer_context
from app.service.llm.llm_factory import get_llm
from app.utils.config import get_config_dict, get_settings
from app.utils.exception.exceptions import AppException
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)

FRONTEND_ERROR_MESSAGE = "Oops, something went wrong. Please try again or contact support."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Build the LLM and compile the agent graph once per process, with a
    checkpointer open for the app's entire lifetime — closed automatically on
    shutdown via the `with` block.
    """
    settings = get_settings()
    config = get_config_dict()
    llm = get_llm(settings, config)

    # Import here (not at module scope) so building the graph doesn't require
    # importing app.agent before settings/config are ready.
    from app.agent.graph import build_graph

    with checkpointer_context() as checkpointer:
        app.state.graph = build_graph(llm, checkpointer=checkpointer)
        logger.info("app_startup_complete", llm_provider=settings.llm.llm_provider)
        yield

    logger.info("app_shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    config = get_config_dict()
    openapi_enabled = config["SETTINGS"]["OPENAPI_DOCS"]

    app = FastAPI(
        title="Car Rental AI Agent",
        description="Customer-facing AI agent: vehicle search, reservation management, and policy Q&A.",
        lifespan=lifespan,
        docs_url="/docs" if openapi_enabled else None,
        redoc_url="/redoc" if openapi_enabled else None,
        openapi_url="/openapi.json" if openapi_enabled else None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.middleware.allowed_host.split(";"),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.middleware.cors_origin.split(";"),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        logger.error("app_exception", detail=exc.detail, status_code=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.user_message or FRONTEND_ERROR_MESSAGE},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(status_code=500, content={"message": FRONTEND_ERROR_MESSAGE})

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)

    return app


app = create_app()
