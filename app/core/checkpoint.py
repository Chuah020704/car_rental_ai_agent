"""SQLite-backed LangGraph checkpointer.

This is the mechanism that makes interrupt() survive across separate HTTP
requests — and even a server restart: the paused graph's entire state is
persisted to disk, keyed by thread_id, and resumed exactly where it left off
via Command(resume=...). Without a checkpointer, interrupt() has nothing to
pause *into* and the conversation would have to restart from scratch.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.utils.config import get_config_dict


@contextmanager
def checkpointer_context() -> Iterator[SqliteSaver]:
    """Open the on-disk checkpoint database for the duration of the `with`
    block. Used by FastAPI's lifespan (Phase 6) and by tests/scripts that
    need a real checkpointer rather than an in-memory one.
    """
    config = get_config_dict()
    db_path = Path(config["AGENT"]["CHECKPOINT_DB"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        yield checkpointer
