"""Loads data/policies/*.md, chunks it, embeds it, and persists it to Chroma.

Idempotent by default: if the persisted collection already exists, build_index()
skips re-embedding unless `rebuild=True`. Run via `make index` or
`uv run python scripts/build_index.py --rebuild`.
"""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.service.rag.embedding_service import get_embeddings
from app.utils.config import get_config_dict, get_settings
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)

_POLICIES_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"


def _load_documents(policies_dir: Path) -> list[Document]:
    """One Document per policy file, tagged with its filename as metadata —
    the filename IS the citation ("source: cancellation.md")."""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title")])
    documents: list[Document] = []
    for path in sorted(policies_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for chunk in header_splitter.split_text(text):
            chunk.metadata["source"] = path.name
            chunk.metadata["policy_type"] = path.stem
            documents.append(chunk)
    return documents


def build_index(*, rebuild: bool = False) -> int:
    """Chunk every policy doc, embed it, and persist to the Chroma collection.

    Returns the number of chunks indexed.
    """
    settings = get_settings()
    config = get_config_dict()
    rag_config = config["RAG"]
    persist_dir = Path(rag_config["PERSIST_DIR"])
    collection_name = rag_config["COLLECTION_NAME"]

    embeddings = get_embeddings(settings, config)

    store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    existing_count = len(store.get()["ids"])

    if existing_count and not rebuild:
        logger.info(
            "rag_index_already_exists", persist_dir=str(persist_dir), count=existing_count
        )
        return existing_count

    if existing_count:
        # Drop through Chroma's own API rather than deleting files at the OS
        # level: on Windows, shutil.rmtree can fail with PermissionError if
        # another connection (e.g. a cached PolicyRetriever) still holds the
        # sqlite file open. Chroma manages that lifecycle itself.
        store.delete_collection()

    header_docs = _load_documents(_POLICIES_DIR)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=rag_config["CHUNK_SIZE"], chunk_overlap=rag_config["CHUNK_OVERLAP"]
    )
    chunks = splitter.split_documents(header_docs)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(persist_dir),
    )
    logger.info("rag_index_built", chunk_count=len(chunks), persist_dir=str(persist_dir))
    return len(chunks)
