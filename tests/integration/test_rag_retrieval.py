"""End-to-end RAG smoke test against the real Chroma + fastembed pipeline.

Marked `llm` (network/model-download dependent on first run) even though no
LLM call happens, so `make test` (CI-safe) skips it by default. Run explicitly
with `uv run pytest -m llm`.
"""

import pytest

from app.service.rag.ingest_service import build_index
from app.service.rag.retrieval_service import PolicyRetriever


@pytest.mark.llm
def test_cancellation_query_retrieves_cancellation_policy() -> None:
    build_index(rebuild=True)
    retriever = PolicyRetriever()

    results = retriever.retrieve("What happens if I cancel my reservation?")

    assert results, "expected at least one policy chunk above the relevance threshold"
    top_doc, _distance = results[0]
    assert top_doc.metadata["source"] == "cancellation.md"


@pytest.mark.llm
def test_unrelated_query_does_not_surface_cancellation_policy() -> None:
    retriever = PolicyRetriever()

    results = retriever.retrieve("What is the capital of France?")

    sources = {doc.metadata["source"] for doc, _ in results}
    assert "cancellation.md" not in sources
