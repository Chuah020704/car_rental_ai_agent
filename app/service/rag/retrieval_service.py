"""Policy retrieval over the Chroma vector store built by ingest_service.

Keyword-only filters and a hard distance cutoff mirror the reference repo's
retrieval_service pattern — but this returns citations (via Document.metadata),
since the Q5 planning decision was to surface sources back to the end user.
"""

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.service.rag.embedding_service import get_embeddings
from app.utils.config import get_config_dict, get_settings
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class PolicyRetriever:
    """Thin wrapper around a Chroma collection, with a hard relevance cutoff."""

    def __init__(self) -> None:
        settings = get_settings()
        config = get_config_dict()
        self._rag_config = config["RAG"]
        embeddings = get_embeddings(settings, config)
        self._store = Chroma(
            collection_name=self._rag_config["COLLECTION_NAME"],
            embedding_function=embeddings,
            persist_directory=self._rag_config["PERSIST_DIR"],
        )

    def retrieve(
        self,
        query: str,
        *,
        policy_type: str | None = None,
        top_k: int | None = None,
    ) -> list[tuple[Document, float]]:
        """Return (chunk, distance) pairs below the configured distance cutoff,
        most-relevant first, deduplicated to one chunk per source file.

        An empty list means "nothing found" — callers (the policy_rag tool in
        Phase 4) must treat that as a hard stop and never let the LLM improvise
        a policy answer from general knowledge.
        """
        k = top_k or self._rag_config["TOP_K"]
        max_distance = self._rag_config["COSINE_DISTANCE_THRESHOLD"]

        search_filter = {"policy_type": policy_type} if policy_type else None
        results = self._store.similarity_search_with_score(query, k=k, filter=search_filter)

        kept = [(doc, distance) for doc, distance in results if distance <= max_distance]
        deduped = self._deduplicate_by_source(kept)
        logger.info(
            "policy_retrieval",
            query=query,
            policy_type=policy_type,
            candidates=len(results),
            kept=len(deduped),
        )
        return deduped

    @staticmethod
    def _deduplicate_by_source(
        results: list[tuple[Document, float]],
    ) -> list[tuple[Document, float]]:
        """Keep only the best-scoring chunk per source file."""
        best: dict[str, tuple[Document, float]] = {}
        for doc, distance in results:
            source = doc.metadata.get("source", "unknown")
            if source not in best or distance < best[source][1]:
                best[source] = (doc, distance)
        return sorted(best.values(), key=lambda pair: pair[1])


@lru_cache
def get_retriever() -> PolicyRetriever:
    """Cached singleton — opening the Chroma collection once per process."""
    return PolicyRetriever()
