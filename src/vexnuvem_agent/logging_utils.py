from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import LOG_FILE


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("vexnuvem")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_500_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
