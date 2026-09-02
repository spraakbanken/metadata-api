"""Logging utilities for gen_pids."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from gen_pids.settings import LOG_FORMAT


def configure_logging(log_dir: Path, logger: logging.Logger) -> None:
    """Ensure logging is configured."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{datetime.datetime.now():%Y-%m}.log"

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file:
            return

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)


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
