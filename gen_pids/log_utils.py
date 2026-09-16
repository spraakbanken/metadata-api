"""Logging utilities for gen_pids."""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

from gen_pids.settings import LOG_FORMAT


class _BelowErrorFilter(logging.Filter):
    """Allow records below ERROR through to stdout."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether the record belongs on stdout."""
        return super().filter(record) and record.levelno < logging.ERROR


class _StdoutHandler(logging.StreamHandler):
    """Stream handler used for non-error console output."""


class _StderrHandler(logging.StreamHandler):
    """Stream handler used for error console output."""


def configure_logging(log_dir: Path, logger: logging.Logger) -> None:
    """Ensure logging is configured."""
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    logger.propagate = False

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{datetime.datetime.now():%Y-%m}.log"

    formatter = logging.Formatter(LOG_FORMAT)
    if not any(
        isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file
        for handler in logger.handlers
    ):
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not any(isinstance(handler, _StdoutHandler) for handler in logger.handlers):
        stdout_handler = _StdoutHandler(sys.stdout)
        stdout_handler.addFilter(_BelowErrorFilter())
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

    if not any(isinstance(handler, _StderrHandler) for handler in logger.handlers):
        stderr_handler = _StderrHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)


def rotate_logs(log_dir: Path, logger: logging.Logger, keep_months: int = 6) -> None:
    """Remove log files older than keep_months based on YYYY-MM filenames."""
    today = datetime.date.today()
    for log_file in log_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].log"):
        try:
            year_str, month_str = log_file.stem.split("-")
            year = int(year_str)
            month = int(month_str)
        except ValueError:
            continue

        diff_months = (today.year - year) * 12 + (today.month - month)
        if diff_months > keep_months:
            logger.info("Removing out-dated log file %s", log_file.name)
            try:
                log_file.unlink()
            except Exception:
                logger.exception("Failed to remove log file %s", log_file)
