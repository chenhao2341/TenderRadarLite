from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawNotice:
    source_id: str
    source_name: str
    source_type: str
    raw_id: str = ""
    title: str = ""
    url: str = ""
    publish_time: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawNoticeDetail:
    source_id: str
    raw_id: str = ""
    detail_url: str = ""
    content_text: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    extracted_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttachmentInfo:
    title: str
    url: str
    file_type: str = "UNKNOWN"
    category: str = "unknown"
    source: str = "unknown"


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
    budget_amount_unit: str = ""
    budget_amount_unit_source: str = ""
    budget_amount_raw_text_snippet: str = ""
    ceiling_price_unit: str = ""
    ceiling_price_unit_source: str = ""
    ceiling_price_raw_text_snippet: str = ""
    procurement_method: str = ""
    content_summary: str = ""
    qualification_summary: str = ""
    accepts_consortium: str = ""
    original_url: str = ""
    employee_readable_url: str = ""
    raw_api_url: str = ""
    has_attachment: bool = False
    attachment_count: int = 0
    detail_checked: bool = False
    detail_available: bool = False
    attachments_found: int = 0
    attachments: list[AttachmentInfo] = field(default_factory=list)
    has_likely_bidding_file: bool = False
    has_likely_procurement_file: bool = False
    has_likely_correction_file: bool = False
    has_likely_bill_file: bool = False
    needs_attachment_review: bool = False
    detail_risk_note: str | None = None
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
