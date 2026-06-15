from __future__ import annotations

from abc import ABC
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

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError(f"{type(self).__name__} must implement parse() or normalize()")

    def fetch_list(self) -> list[Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_list() or parse()")

    def fetch_detail(self, item: Any) -> Any | None:
        return None

    def normalize(self, item: Any, detail: Any | None = None) -> Notice:
        raise NotImplementedError(f"{type(self).__name__} must implement normalize() or parse()")

    def crawl(self) -> list[Notice]:
        if self._uses_structured_pipeline():
            notices: list[Notice] = []
            for item in self.fetch_list():
                detail = self.fetch_detail(item)
                notices.append(self.normalize(item, detail))
            return notices

        html = self.fetcher.get_text(self.url)
        if not html:
            return []
        return self.parse(html)

    def now_string(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def source_id(self) -> str:
        return str(self.source_config.get("adapter_key") or self.source_config.get("name") or self.source_name)

    @property
    def source_type(self) -> str:
        return str(self.source_config.get("source_type") or self.source_config.get("source_subtype") or "")

    def _uses_structured_pipeline(self) -> bool:
        adapter_type = type(self)
        return (
            adapter_type.fetch_list is not BaseAdapter.fetch_list
            and adapter_type.normalize is not BaseAdapter.normalize
        )
