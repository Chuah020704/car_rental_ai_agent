"""Embeddings provider factory.

Mirrors the LLM factory's dispatch-by-name pattern (Phase 4) — same shape,
different return type. "local" needs no API key at all (fastembed runs
on-device), so the RAG pipeline works for a grader with zero cloud credentials.
"""

from typing import Any

from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from app.utils.config import Settings
from app.utils.exception.exceptions import ConfigurationException
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class LocalFastEmbedEmbeddings(Embeddings):
    """Wraps fastembed's on-device model to satisfy LangChain's Embeddings interface.

    BGE-family models are asymmetric: queries and passages are embedded with
    different internal prompts for best retrieval quality, which is why
    fastembed exposes separate `query_embed`/`passage_embed` methods instead of
    one `embed`. Using the wrong one (or a single generic `embed` for both) is
    a common mistake that quietly produces a few lower relevance scores.
    """

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(vector.tolist() for vector in self._model.query_embed([text]))


def get_embeddings(settings: Settings, config: dict[str, Any]) -> Embeddings:
    """Return the configured embeddings provider, dispatching on
    `settings.llm.embedding_provider`."""
    provider = settings.llm.embedding_provider.lower()
    embedding_config = config["SETTINGS"]["MODEL_SERVICE"]["EMBEDDING"]

    if provider == "local":
        logger.debug("embeddings_factory_selected", provider="local")
        return LocalFastEmbedEmbeddings(model_name=embedding_config["LOCAL_MODEL"])

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not settings.llm.google_api_key:
            raise ConfigurationException(
                detail="GOOGLE_API_KEY is required for embedding_provider=google"
            )
        logger.debug("embeddings_factory_selected", provider="google")
        return GoogleGenerativeAIEmbeddings(
            model=embedding_config["GOOGLE_MODEL"],
            api_key=SecretStr(settings.llm.google_api_key),
        )

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        if not settings.llm.openai_api_key:
            raise ConfigurationException(
                detail="OPENAI_API_KEY is required for embedding_provider=openai"
            )
        logger.debug("embeddings_factory_selected", provider="openai")
        return OpenAIEmbeddings(
            model=embedding_config["OPENAI_MODEL"],
            api_key=SecretStr(settings.llm.openai_api_key),
        )

    raise ConfigurationException(
        detail=f"Unknown embedding_provider '{provider}'. Supported: local, google, openai"
    )
