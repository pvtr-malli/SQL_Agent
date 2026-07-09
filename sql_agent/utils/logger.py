import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Logging is configured once at import time."""
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure root logger with a consistent format.
    Call this once at app startup (main.py). All child loggers inherit it.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called more than once.
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers = [handler]
