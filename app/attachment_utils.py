from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from .html_extract import find_anchor_blocks, normalize_url
from .models import AttachmentInfo, Notice


FILE_TYPE_BY_EXTENSION = {
    ".docx": "DOCX",
    ".xlsx": "XLSX",
    ".pdf": "PDF",
    ".doc": "DOC",
    ".xls": "XLS",
    ".zip": "ZIP",
    ".rar": "RAR",
    ".html": "HTML",
    ".htm": "HTML",
}

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("correction_file", ("更正", "澄清", "答疑", "补遗", "变更", "修改", "补充通知")),
    ("bill_file", ("工程量清单", "报价表", "最高限价", "招标控制价", "控制价", "预算", "清单")),
    ("drawing", ("图纸", "设计图", "施工图", "CAD")),
    ("qualification", ("资格审查", "资格预审", "资格", "资质")),
    ("procurement_file", ("采购文件", "竞争性磋商文件", "竞争性谈判文件", "询价文件", "磋商文件")),
    ("bidding_file", ("招标文件", "投标文件格式")),
    ("price_sheet", ("报价表",)),
]

CATEGORY_LABELS = {
    "bidding_file": "疑似招标文件",
    "procurement_file": "疑似采购文件",
    "correction_file": "疑似更正/澄清文件",
    "bill_file": "疑似工程量清单",
    "drawing": "疑似图纸",
    "qualification": "疑似资格文件",
    "price_sheet": "疑似报价表",
    "unknown": "未识别类别",
}

ATTACHMENT_REVIEW_HINT = "需要人工查看附件确认金额单位、资质、评分办法、采购需求"

_ATTACHMENT_TEXT_HINTS = (
    "附件",
    "招标文件",
    "采购文件",
    "更正",
    "澄清",
    "答疑",
    "补遗",
    "清单",
    "报价表",
    "图纸",
    "资格",
)
_ATTACHMENT_URL_HINTS = ("download", "attach", "annex", "file", "upload")


@dataclass(frozen=True)
class AttachmentDiscoveryResult:
    detail_checked: bool
    detail_available: bool
    attachments: list[AttachmentInfo]
    detail_risk_note: str | None = None


def detect_file_type(url: str = "", title: str = "", content_type: str = "") -> str:
    candidates = [urlparse(url).path.lower(), title.lower(), content_type.lower()]
    for candidate in candidates:
        for extension, file_type in FILE_TYPE_BY_EXTENSION.items():
            if extension in candidate:
                return file_type
    return "UNKNOWN"


def detect_attachment_category(title: str) -> str:
    normalized = (title or "").strip()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return category
    return "unknown"


def attachment_category_label(category: str) -> str:
    return CATEGORY_LABELS.get((category or "").strip(), CATEGORY_LABELS["unknown"])


def extract_attachments_from_html(html: str, *, base_url: str = "") -> list[AttachmentInfo]:
    attachments: list[AttachmentInfo] = []
    seen: set[tuple[str, str]] = set()

    for href, text in find_anchor_blocks(html or ""):
        title = (text or "").strip() or _filename_from_url(href)
        url = normalize_url(base_url, href) if href else ""
        file_type = detect_file_type(url, title)
        category = detect_attachment_category(title)
        if not _looks_like_attachment(href=href, title=title, file_type=file_type, category=category):
            continue
        key = (url, title)
        if key in seen:
            continue
        seen.add(key)
        attachments.append(
            AttachmentInfo(
                title=title or "未命名附件",
                url=url,
                file_type=file_type,
                category=category,
                source="detail_page",
            )
        )

    return attachments


def extract_attachments_from_records(records: Iterable[Any], *, base_url: str = "") -> list[AttachmentInfo]:
    attachments: list[AttachmentInfo] = []
    seen: set[tuple[str, str]] = set()

    for record in records or []:
        if not isinstance(record, dict):
            continue
        title = _first_non_empty(
            record,
            "title",
            "name",
            "fileName",
            "filename",
            "attachName",
            "attachmentName",
            "annexName",
            "file_title",
        )
        href = _first_non_empty(
            record,
            "url",
            "fileUrl",
            "downloadUrl",
            "attachUrl",
            "annexUrl",
            "path",
            "filePath",
            "address",
            "fileHttpUrl",
        )
        url = normalize_url(base_url, href) if href else ""
        if not title and not url:
            continue
        if not title:
            title = _filename_from_url(url)
        file_type = detect_file_type(url, title, _first_non_empty(record, "contentType", "mimeType", "type"))
        category = detect_attachment_category(title)
        key = (url, title)
        if key in seen:
            continue
        seen.add(key)
        attachments.append(
            AttachmentInfo(
                title=title or "未命名附件",
                url=url,
                file_type=file_type,
                category=category,
                source="raw_text" if not href else "detail_page",
            )
        )

    return attachments


def merge_attachments(*groups: Iterable[AttachmentInfo]) -> list[AttachmentInfo]:
    merged: list[AttachmentInfo] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for item in group or []:
            key = ((item.url or "").strip(), (item.title or "").strip())
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def discover_attachments(
    *,
    detail_checked: bool,
    detail_available: bool,
    detail_html: str = "",
    base_url: str = "",
    structured_records: Iterable[Any] | None = None,
    detail_risk_note: str | None = None,
) -> AttachmentDiscoveryResult:
    record_attachments = extract_attachments_from_records(structured_records or [], base_url=base_url)
    html_attachments = extract_attachments_from_html(detail_html, base_url=base_url) if detail_html else []
    attachments = merge_attachments(record_attachments, html_attachments)
    return AttachmentDiscoveryResult(
        detail_checked=detail_checked,
        detail_available=detail_available,
        attachments=attachments,
        detail_risk_note=detail_risk_note,
    )


def apply_attachment_result(notice: Notice, result: AttachmentDiscoveryResult) -> Notice:
    notice.detail_checked = result.detail_checked
    notice.detail_available = result.detail_available
    notice.attachments = list(result.attachments)
    notice.attachments_found = len(result.attachments)
    notice.has_attachment = bool(result.attachments)
    notice.attachment_count = len(result.attachments)
    notice.has_likely_bidding_file = any(item.category == "bidding_file" for item in result.attachments)
    notice.has_likely_procurement_file = any(item.category == "procurement_file" for item in result.attachments)
    notice.has_likely_correction_file = any(item.category == "correction_file" for item in result.attachments)
    notice.has_likely_bill_file = any(item.category in {"bill_file", "price_sheet"} for item in result.attachments)
    notice.needs_attachment_review = notice.detail_checked and (
        not notice.detail_available or bool(result.attachments)
    )
    notice.detail_risk_note = result.detail_risk_note
    return notice


def attachment_titles_summary(notice: Notice, *, max_items: int = 5) -> list[str]:
    titles: list[str] = []
    for attachment in notice.attachments[:max_items]:
        if attachment.title:
            titles.append(attachment.title)
    return titles


def _looks_like_attachment(*, href: str, title: str, file_type: str, category: str) -> bool:
    normalized_title = (title or "").strip()
    normalized_href = (href or "").lower()
    if file_type != "UNKNOWN" or category != "unknown":
        return True
    if any(hint in normalized_title for hint in _ATTACHMENT_TEXT_HINTS):
        return True
    return any(hint in normalized_href for hint in _ATTACHMENT_URL_HINTS) and bool(normalized_title)


def _filename_from_url(url: str) -> str:
    path = urlparse(url or "").path
    if not path:
        return ""
    return path.rsplit("/", 1)[-1].strip()


def _first_non_empty(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
