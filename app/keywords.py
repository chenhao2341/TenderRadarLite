from __future__ import annotations

from typing import Iterable, List

from .models import Notice


def match_keywords(title: str, keywords: Iterable[str]) -> List[str]:
    title_compact = title.strip()
    return [keyword for keyword in keywords if keyword and keyword in title_compact]


def build_keyword_text(notice: Notice) -> str:
    return " ".join(
        part.strip()
        for part in [
            notice.project_name,
            notice.section_name,
            notice.content_summary,
            notice.qualification_summary,
        ]
        if part and part.strip()
    )
