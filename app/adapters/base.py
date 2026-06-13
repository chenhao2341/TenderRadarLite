from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..fetcher import Fetcher
from ..models import Notice


class BaseAdapter(ABC):
    def __init__(
        self,
        source_name: str,
        url: str,
        region: str,
        fetcher: Fetcher,
        source_config: dict[str, Any] | None = None,
    ) -> None:
        self.source_name = source_name
        self.url = url
        self.region = region
        self.fetcher = fetcher
        self.source_config = source_config or {}
        self.last_crawl_stats: dict[str, Any] = {}

    @abstractmethod
    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError

    def crawl(self) -> list[Notice]:
        html = self.fetcher.get_text(self.url)
        if not html:
            return []
        return self.parse(html)

    def now_string(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
