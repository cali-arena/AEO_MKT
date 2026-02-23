"""Cron logging: stdout + file per script."""

import logging
import os
from pathlib import Path


def get_logger(script_name: str) -> logging.Logger:
    """Return a logger that writes to stdout and logs/cron_<script_name>.log."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(f"cron.{script_name}")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    log_file = log_dir / f"cron_{script_name}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
