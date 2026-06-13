from __future__ import annotations

import logging
from datetime import datetime

from .config import LOG_DIR


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tender_radar_lite")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    timestamp = datetime.now().strftime("%Y%m%d")
    log_path = LOG_DIR / f"run-{timestamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger

