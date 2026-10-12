# ADR 0002: Chroma over pgvector/Qdrant for the policy vector store

## Context

The project needs a vector store for the six policy documents (insurance,
cancellation, damage, roadside assistance, fuel, age requirements) — a small,
static corpus (8 chunks total after splitting). The brief allows any local
vector store.

## Decision

Use Chroma with its file-based `persist_directory`, not pgvector (which needs
a running PostgreSQL instance) or a managed Qdrant deployment.

## Consequences

- Zero additional infrastructure: `uv run python scripts/build_index.py`
  creates `.chroma/` directly in the project directory.
- Rebuilding the index uses Chroma's own `delete_collection()` API rather
  than deleting files at the OS level — this was *not* the original design;
  it was changed after a real Windows file-locking bug (Lesson 31) where
  `shutil.rmtree()` failed because an earlier test's cached retriever still
  held the SQLite file open. Chroma manages its own storage lifecycle
  through its client connection, sidestepping the OS-level file lock.
- Not chosen for raw scale — at a few thousand+ documents, or multiple
  concurrent writers, pgvector's transactional guarantees would matter more
  than Chroma's zero-ops simplicity.
