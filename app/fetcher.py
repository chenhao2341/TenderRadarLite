from __future__ import annotations

import logging
from typing import Any, Optional

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class Fetcher:
    def __init__(self, logger: logging.Logger, timeout: int = 20) -> None:
        self.logger = logger
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False

    def get_text(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            response.raise_for_status()
            encoding = response.apparent_encoding or "utf-8"
            return response.content.decode(encoding, errors="ignore")
        except Exception as exc:
            self.logger.error("fetch failed: %s (%s)", url, exc)
            return None

    def get_json(self, url: str) -> Optional[Any]:
        try:
            response = self.session.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error("json fetch failed: %s (%s)", url, exc)
            return None
