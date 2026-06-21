from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..amount_utils import RAW_TEXT_SOURCE, parse_amount_context
from ..attachment_utils import apply_attachment_result, discover_attachments
from ..html_extract import html_to_text
from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import base_origin, build_paged_url, summarize_notice_html


LIST_DEFAULT_PARAMS = {
    "descs": "noticeSendTime",
    "notice": "1",
    "tenderMode": "公开招标",
}
DEADLINE_LABELS = [
    "提交投标文件的截止时间",
    "提交投标文件截止时间",
    "投标截止时间",
    "开标时间",
    "响应文件提交截止时间",
    "响应文件开启时间",
    "提交响应文件截止时间",
    "递交投标文件截止时间",
    "递交响应文件截止时间",
    "截止时间",
]
REGION_CODE_FALLBACKS = {
    "430400": "衡阳市",
}
ATTACHMENT_LIMIT_NOTE = "附件仅做发现，未下载或解析"
TENDER_NOTICE_KEYWORDS = ("招标", "采购", "磋商", "谈判", "询价")
RELAXED_NOTICE_KEYWORDS = ("中标", "成交", "结果", "更正", "澄清", "暂停", "终止", "废标", "流标")
DATETIME_RE_LIST = [
    re.compile(r"(20\d{2}[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}日?\s*\d{1,2}[:：]\d{2}(?::\d{2})?)"),
    re.compile(r"(20\d{2}[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}日?\s*\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?)"),
    re.compile(r"(20\d{2}[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}日?)"),
]


class HengyangProcurementAdapter(BaseAdapter):
    def fetch_list(self) -> list[dict[str, Any]]:
        payload = self.fetcher.get_json(_build_hengyang_list_url(self.url)) or {}
        records = ((payload.get("data") or {}).get("records")) or []
        self._list_stats = {
            "fetched_total": len(records),
            "fetch_failed": 0 if payload else 1,
        }
        return records

    def fetch_detail(self, item: dict[str, Any]) -> dict[str, Any] | None:
        section_id = (item.get("bidSectionId") or "").strip()
        if not section_id:
            return None

        origin = base_origin(self.url)
        project_payload = self.fetcher.get_json(
            f"{origin}/tradeApi/governmentPurchase/projectInformation/getBySectionId?sectionId={section_id}"
        ) or {}
        project_detail = project_payload.get("data") or {}
        project_info = project_detail.get("governmentProcurementProjectInformation") or {}
        employee_url = _build_employee_readable_url(
            origin=origin,
            project_id=str(item.get("projectId") or ""),
            region_code=str(
                item.get("regionCode") or project_info.get("regionCode") or self.source_config.get("region_code") or ""
            ),
            section_id=section_id,
        )
        raw_api_url = (
            f"{origin}/tradeApi/governmentPurchase/projectInformation/getAnnouncementBySectionId"
            f"?sectionId={section_id}"
        )
        ann_payload = self.fetcher.get_json(raw_api_url) or {}
        ann_list = ((ann_payload.get("data") or {}).get("governmentProcureAnnouncementInformation")) or []
        detail_available = ann_payload.get("code") == 200 and bool(ann_list)
        if not detail_available:
            return {
                "detail_checked": True,
                "detail_available": False,
                "detail": project_detail,
                "employee_url": employee_url,
                "raw_api_url": raw_api_url,
                "structured_attachments": ((project_payload.get("data") or {}).get("GovernmentPurchaseFile")) or [],
                "detail_risk_note": "详情页不可访问或解析失败",
            }

        return {
            "detail_checked": True,
            "detail_available": True,
            "detail": project_detail,
            "employee_url": employee_url,
            "announcement": ann_list[0],
            "raw_api_url": raw_api_url,
            "structured_attachments": ((project_payload.get("data") or {}).get("GovernmentPurchaseFile")) or [],
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        section_id = (item.get("bidSectionId") or "").strip()
        payload = (detail or {}).get("detail") or {}
        project = payload.get("governmentProcurementProjectInformation") or {}
        section_list = payload.get("GovernmentProcureSectionInformationList") or []
        files = (detail or {}).get("structured_attachments") or payload.get("GovernmentPurchaseFile") or []
        section = section_list[0] if section_list else {}
        ann = (detail or {}).get("announcement") or {}
        notice_html = ann.get("noticeContent") or ""
        notice_text = html_to_text(notice_html)
        content_summary, qualification_summary, deadline, consortium = summarize_notice_html(notice_html)
        deadline = _extract_hengyang_deadline(
            item=item,
            project=project,
            section=section,
            announcement=ann,
            notice_text=notice_text,
            fallback_deadline=deadline,
        )
        budget_context = parse_amount_context(
            _stringify_number(project.get("programBudget") or section.get("sectionBudget")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("预算", "项目预算", "采购预算"),
        )
        ceiling_context = parse_amount_context(
            _stringify_number(section.get("controlPrice") or section.get("sectionBudget")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("最高", "限价", "控制价"),
        )

        notice = Notice(
            source=self.source_config.get("source", "衡阳分平台"),
            source_subtype=self.source_config.get("source_subtype", "政府采购交易"),
            dedupe_key=f"{self.source_name}|{section_id}",
            section_id=section_id,
            project_name=(project.get("purchaseProjectName") or item.get("purchaseProjectName") or "").strip(),
            section_name=(section.get("purchaseSectionName") or item.get("purchaseSectionName") or "").strip(),
            notice_type=(ann.get("bulletinType") or item.get("noticeType") or "公告").strip(),
            project_code=(project.get("purchaseProjectCode") or item.get("projectId") or "").strip(),
            purchaser_or_tenderer=(project.get("purchaserName") or "").strip(),
            agency=(project.get("purchaserAgencyName") or "").strip(),
            region=_normalize_hengyang_region(
                item.get("regionName") or project.get("regionName") or project.get("regionCode") or item.get("regionCode"),
                fallback=self.region,
            ),
            publish_time=(ann.get("noticeSendTime") or item.get("noticeSendTime") or "").strip(),
            file_get_deadline=deadline if "截止" in deadline else "",
            bid_open_or_response_deadline=deadline,
            budget_amount=budget_context.raw_value,
            ceiling_price=ceiling_context.raw_value,
            budget_amount_unit=budget_context.unit or "",
            budget_amount_unit_source=budget_context.unit_source,
            budget_amount_raw_text_snippet=budget_context.raw_text_snippet,
            ceiling_price_unit=ceiling_context.unit or "",
            ceiling_price_unit_source=ceiling_context.unit_source,
            ceiling_price_raw_text_snippet=ceiling_context.raw_text_snippet,
            procurement_method=(section.get("tenderType") or project.get("purchaserMode") or "").strip(),
            content_summary=content_summary,
            qualification_summary=qualification_summary,
            accepts_consortium=consortium,
            original_url=str((detail or {}).get("employee_url") or ""),
            employee_readable_url=str((detail or {}).get("employee_url") or ""),
            raw_api_url=str((detail or {}).get("raw_api_url") or ""),
            fetched_at=self.now_string(),
        )
        apply_attachment_result(
            notice,
            discover_attachments(
                detail_checked=bool((detail or {}).get("detail_checked")),
                detail_available=bool((detail or {}).get("detail_available")),
                detail_html=notice_html,
                base_url=notice.raw_api_url or self.url,
                structured_records=files,
                detail_risk_note=(detail or {}).get("detail_risk_note"),
            ),
        )
        notice.detail_risk_note = _build_quality_risk_note(notice, detail)
        return notice

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
        detail_partial = 0
        skipped = 0
        inaccessible_count = 0

        for item in self.fetch_list():
            if not (item.get("bidSectionId") or "").strip():
                skipped += 1
                continue

            detail = self.fetch_detail(item)
            if not detail:
                skipped += 1
                continue

            notice = self.normalize(item, detail)
            notices.append(notice)
            if notice.detail_available:
                detail_success += 1
                if _notice_has_partial_gap(notice):
                    detail_partial += 1
            else:
                inaccessible_count += 1

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "list_count": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
            "detail_partial_count": detail_partial,
            "detail_failed_count": inaccessible_count,
            "skipped_count": skipped,
            "real_notice_count": len(notices),
            "fetch_failed": list_stats.get("fetch_failed", 0),
            "detail_unavailable_count": inaccessible_count,
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")


def _stringify_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _build_hengyang_list_url(url: str, *, current: int = 1, size: int = 10) -> str:
    paged_url = build_paged_url(url, current=current, size=size)
    parts = urlsplit(paged_url)
    query_items = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in LIST_DEFAULT_PARAMS.items():
        query_items.setdefault(key, value)
    return urlunsplit(parts._replace(query=urlencode(query_items)))


def _build_employee_readable_url(
    *,
    origin: str,
    project_id: str,
    region_code: str,
    section_id: str,
) -> str:
    if not origin or not section_id:
        return ""
    query = urlencode(
        {
            "id": project_id,
            "regionCode": region_code,
            "bidSectionId": section_id,
            "default": "projectInfo",
        }
    )
    return f"{origin}/#/resources/projectDetail/governmentPurchase?{query}"


def _normalize_hengyang_region(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if text and not text.isdigit():
        return text
    fallback_text = str(fallback or "").strip()
    mapped = REGION_CODE_FALLBACKS.get(text) or REGION_CODE_FALLBACKS.get(fallback_text)
    if mapped:
        return mapped
    if fallback_text and not fallback_text.isdigit():
        return fallback_text
    return fallback_text or text or "衡阳市"


def _extract_hengyang_deadline(
    *,
    item: dict[str, Any],
    project: dict[str, Any],
    section: dict[str, Any],
    announcement: dict[str, Any],
    notice_text: str,
    fallback_deadline: str,
) -> str:
    for candidate in (
        announcement.get("bidOpeningTime"),
        announcement.get("openBidTime"),
        announcement.get("responseFileSubmitTime"),
        announcement.get("responseFileOpenTime"),
        section.get("bidOpeningTime"),
        section.get("responseFileSubmitTime"),
        item.get("bidOpeningTime"),
        item.get("responseFileSubmitTime"),
        fallback_deadline,
    ):
        cleaned = _normalize_deadline_text(candidate)
        if cleaned:
            return cleaned
    return _extract_deadline_from_text(notice_text)


def _extract_deadline_from_text(text: str) -> str:
    cleaned_text = str(text or "")
    for label in DEADLINE_LABELS:
        idx = cleaned_text.find(label)
        if idx == -1:
            continue
        snippet = cleaned_text[idx : idx + 160]
        extracted = _extract_datetime_from_snippet(snippet)
        if extracted:
            return extracted
    for pattern in DATETIME_RE_LIST:
        for match in pattern.finditer(cleaned_text):
            candidate = _canonicalize_deadline_text(match.group(1))
            tail = cleaned_text[match.end() : match.end() + 24]
            if any(keyword in tail for keyword in ("提交响应文件", "递交响应文件", "提交投标文件", "递交投标文件", "开标")):
                return candidate
    return ""


def _extract_datetime_from_snippet(snippet: str) -> str:
    snippet_text = str(snippet or "").replace("：", ":").strip()
    for pattern in DATETIME_RE_LIST:
        match = pattern.search(snippet_text)
        if match:
            return _canonicalize_deadline_text(match.group(1))
    return ""


def _normalize_deadline_text(value: Any) -> str:
    text = str(value or "").replace("：", ":").strip()
    if not text:
        return ""
    return _canonicalize_deadline_text(text)


def _canonicalize_deadline_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").replace("：", ":").strip())
    normalized = normalized.replace("时", ":").replace("分", "").replace("秒", "")
    normalized = normalized.replace("日 ", "日")
    return normalized


def _build_quality_risk_note(notice: Notice, detail: dict[str, Any] | None) -> str | None:
    notes: list[str] = []
    base_note = str((detail or {}).get("detail_risk_note") or "").strip()
    structured_attachments = (detail or {}).get("structured_attachments") or []
    nested_files = ((detail or {}).get("detail") or {}).get("GovernmentPurchaseFile") or []
    if base_note:
        notes.append(base_note)
    if _is_tender_like_notice(notice) and not (notice.bid_open_or_response_deadline or "").strip():
        notes.append("招标/采购类公告未提取到截止时间，可能原文缺失或需查看附件/采购文件")
    if notice.has_attachment or structured_attachments or nested_files:
        notes.append(ATTACHMENT_LIMIT_NOTE)
    deduped: list[str] = []
    seen: set[str] = set()
    for note in notes:
        compact = note.strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        deduped.append(compact)
    return "；".join(deduped) or None


def _is_tender_like_notice(notice: Notice) -> bool:
    notice_type = (notice.notice_type or "").strip()
    procurement_method = (notice.procurement_method or "").strip()
    if any(keyword in notice_type for keyword in RELAXED_NOTICE_KEYWORDS):
        return False
    if any(keyword in notice_type for keyword in TENDER_NOTICE_KEYWORDS):
        return True
    return any(keyword in procurement_method for keyword in TENDER_NOTICE_KEYWORDS)


def _notice_has_partial_gap(notice: Notice) -> bool:
    return _is_tender_like_notice(notice) and not (notice.bid_open_or_response_deadline or "").strip()
