from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Notice:
    source: str
    source_subtype: str
    dedupe_key: str
    section_id: str
    project_name: str
    notice_id: str = ""
    notice_title: str = ""
    notice_publish_time: str = ""
    section_name: str = ""
    notice_type: str = ""
    project_code: str = ""
    purchaser_or_tenderer: str = ""
    agency: str = ""
    region: str = ""
    publish_time: str = ""
    file_get_deadline: str = ""
    bid_open_or_response_deadline: str = ""
    budget_amount: str = ""
    ceiling_price: str = ""
    procurement_method: str = ""
    content_summary: str = ""
    qualification_summary: str = ""
    accepts_consortium: str = ""
    original_url: str = ""
    employee_readable_url: str = ""
    raw_api_url: str = ""
    has_attachment: bool = False
    attachment_count: int = 0
    fetched_at: str = ""
    hit_keywords: list[str] = field(default_factory=list)
    lead_tier: str = ""
    lead_reason: str = ""
    matched_positive_signals: list[str] = field(default_factory=list)
    matched_negative_signals: list[str] = field(default_factory=list)
    is_new: bool = False
    manual_judgement: str = "待确认"
    newness_label: str | None = None

    @property
    def title(self) -> str:
        return self.notice_title or self.section_name or self.project_name

    @property
    def source_site(self) -> str:
        return f"{self.source}-{self.source_subtype}" if self.source_subtype else self.source

    @property
    def published_at(self) -> str:
        return self.publish_time

    @property
    def source_url(self) -> str:
        return self.employee_readable_url or self.raw_api_url or self.original_url
