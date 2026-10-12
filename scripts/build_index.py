"""CLI: build or rebuild the Chroma policy index.

Usage:
    uv run python scripts/build_index.py              # build if missing
    uv run python scripts/build_index.py --rebuild     # force a clean rebuild
"""

import argparse

from app.service.rag.ingest_service import build_index
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or rebuild the policy RAG index.")
    parser.add_argument(
        "--rebuild", action="store_true", help="Delete and recreate the index from scratch."
    )
    args = parser.parse_args()

    count = build_index(rebuild=args.rebuild)
    logger.info("build_index_complete", chunk_count=count)
    print(f"Indexed {count} chunks.")


if __name__ == "__main__":
    main()
