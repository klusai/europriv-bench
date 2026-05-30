"""Shared logging setup (mirrors the convention used across KlusAI repos)."""

import logging


def get_logger(name: str) -> logging.Logger:
    # Configure once, and only if nothing else has (avoid a library import side-effect).
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    return logging.getLogger(name)
