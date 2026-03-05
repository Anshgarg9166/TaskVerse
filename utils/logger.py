# ─────────────────────────────────────────────
#  Taskverse – Structured Logging (Loguru)
# ─────────────────────────────────────────────
from __future__ import annotations

import sys

from loguru import logger

from backend.config import get_settings


def setup_logger() -> None:
    """Configure loguru for the whole application."""
    settings = get_settings()

    logger.remove()  # remove default handler

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> – "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=fmt,
        level=settings.log_level.upper(),
        colorize=True,
    )

    logger.add(
        "logs/taskverse.log",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=fmt,
        level="DEBUG",
        enqueue=True,
    )

    logger.info("Taskverse logger initialised – env={}", settings.app_env)


# Public re-export so callers can just do:
#   from utils.logger import log
log = logger
