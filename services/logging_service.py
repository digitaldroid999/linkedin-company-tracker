from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


_LOGGER_NAME = "linkedin_company_tracker"


class ImmediateRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that flushes and fsyncs on every record.

    This ensures log lines are written to disk as soon as possible.
    """

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        super().emit(record)
        try:
            self.flush()
            if self.stream and hasattr(self.stream, "fileno"):
                os.fsync(self.stream.fileno())
        except Exception:
            # Never let logging failures crash the app
            pass


def _configure_logger() -> logging.Logger:
    """Configure application-wide logger writing to app.log next to the executable.

    - When running a frozen build (PyInstaller), app.log is created in the same
      directory as the .exe file.
    - When running from source, app.log is created in the project root
      (same folder as main.py).
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Determine base directory: exe folder when frozen, project root otherwise
    if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent

    log_file = base_dir / "app.log"

    # Start each run with a fresh, empty log file
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("", encoding="utf-8")
    except Exception:
        # If we can't truncate, we still try to log; handler will append
        pass

    handler = ImmediateRotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


_LOGGER = _configure_logger()


def get_logger() -> logging.Logger:
    """Return the shared application logger."""
    return _LOGGER


def install_global_exception_hook() -> None:
    """Log all uncaught exceptions to the app logger."""

    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt behave normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        _LOGGER.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        # Also forward to default handler so crashes are still visible during development
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception

