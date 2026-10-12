"""Optional rotating file handler, for environments that want logs on disk
in addition to stdout/stderr (the console/JSON handler wired in config.py).
Not attached by default — see configure_logging() if you want to add it.
"""

import logging
import logging.handlers
from pathlib import Path


def build_file_handler(log_dir: str = "logs", filename: str = "app.log") -> logging.Handler:
    """Create a 5MB-rotating file handler, keeping 3 backups."""
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path / filename, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler
