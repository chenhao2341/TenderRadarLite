from __future__ import annotations

from typing import List

from ..html_extract import find_links_with_dates
from ..models import Notice
from .base import BaseAdapter


class HengyangTzggAdapter(BaseAdapter):
    def parse(self, html: str) -> List[Notice]:
        notices: List[Notice] = []
        for title, full_url, published_at in find_links_with_dates(html, self.url, "/xwzx/tzgg/"):
            notices.append(
                Notice(
                    source=self.source_config.get("source", self.source_name),
                    source_subtype=self.source_config.get("source_subtype", "通知公告"),
                    dedupe_key=f"{self.source_name}|{full_url}",
                    section_id="",
                    project_name=title,
                    section_name="",
                    notice_type="通知公告",
                    purchaser_or_tenderer="",
                    agency="",
                    region=self.region,
                    publish_time=published_at,
                    original_url=full_url,
                    fetched_at=self.now_string(),
                )
            )
        return notices
