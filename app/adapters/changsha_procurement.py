from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..amount_utils import RAW_TEXT_SOURCE, parse_amount_context
from ..attachment_utils import apply_attachment_result, discover_attachments
from ..html_extract import extract_accepts_consortium, extract_datetime_after_label, html_to_text
from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import base_origin, build_paged_url


DETAIL_RISK_NOTE = "详情页不可访问或解析失败"
MISSING_SUMMARY = "未提取到"
ATTACHMENT_LIMIT_NOTE = "附件仅做发现，未下载或解析"
ANNOUNCEMENT_MISMATCH_RISK_NOTE = "详情公告类型与列表类型不一致，已按列表类型回退选择"
LIST_DEFAULT_PARAMS = {
    "descs": "noticeSendTime",
    "notice": "1",
    "tenderMode": "公开招标",
}
NOTICE_TYPE_TO_BULLETIN_TYPE = {
    "ZHAOBIAO_NOTICE": "招标公告",
    "GENGZHENG_NOTICE": "更正公告",
    "CHENGQING_NOTICE": "澄清公告",
}
CONTENT_MARKERS = (
    "项目概况",
    "采购需求",
    "服务内容",
    "项目内容",
    "标的",
    "采购项目",
    "合同履行期限",
    "简要技术要求",
    "服务要求",
    "采购范围",
)
QUALIFICATION_MARKERS = (
    "供应商资格要求",
    "投标人资格要求",
    "投标人的资格要求",
    "申请人的资格要求",
    "本项目的特定资格要求",
    "资格条件",
    "具有独立承担民事责任的能力",
    "政府采购法第二十二条",
    "信用中国",
    "中国政府采购网",
    "联合体",
    "专门面向中小企业",
    "落实政府采购政策",
    "资质证书",
    "资格审查",
)
GENERIC_SUMMARY_VALUES = {
    "",
    "详见招标文件",
    "详见采购文件",
    "详见磋商文件",
    "详见谈判文件",
    "详见附件",
}
SECTION_HEADING_RE = re.compile(r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.]|\(?[一二三四五六七八九十]+\)|\d+\))")


class ChangshaProcurementAdapter(BaseAdapter):
    def fetch_list(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        error_count = 0
        successful_pages = 0
        pages_scanned = max(int(self.source_config.get("pages_scanned", 1) or 1), 1)
        page_size = max(int(self.source_config.get("page_size", 10) or 10), 1)

        for page in range(1, pages_scanned + 1):
            page_url = _build_changsha_list_url(self.url, current=page, size=page_size)
            payload = self.fetcher.get_json(page_url) or {}
            if not payload:
                error_count += 1
                continue

            page_records = ((payload.get("data") or {}).get("records")) or []
            successful_pages += 1
            records.extend(page_records)

        self._list_stats = {
            "pages_scanned": pages_scanned,
            "page_size": page_size,
            "fetched_total": len(records),
            "error_count": error_count,
            "successful_pages": successful_pages,
            "fetch_failed": 1 if successful_pages == 0 else 0,
        }
        return records

    def fetch_detail(self, item: dict[str, Any]) -> dict[str, Any] | None:
        section_id = (item.get("bidSectionId") or "").strip()
        if not section_id:
            return None

        origin = base_origin(self.url)
        employee_url = _build_employee_readable_url(
            origin=origin,
            project_id=str(item.get("projectId") or ""),
            region_code=str(item.get("regionCode") or self.source_config.get("region_code") or ""),
            section_id=section_id,
        )
        project_payload = self.fetcher.get_json(
            f"{origin}/tradeApi/governmentPurchase/projectInformation/getBySectionId?sectionId={section_id}"
        ) or {}
        raw_api_url = (
            f"{origin}/tradeApi/governmentPurchase/projectInformation/getAnnouncementBySectionId"
            f"?sectionId={section_id}"
        )
        announcement_payload = self.fetcher.get_json(raw_api_url) or {}
        announcements = (
            ((announcement_payload.get("data") or {}).get("governmentProcureAnnouncementInformation")) or []
        )
        selected_announcement, selection_used_fallback = _select_announcement_record(
            announcements,
            list_notice_type=str(item.get("noticeType") or ""),
        )
        detail_available = announcement_payload.get("code") == 200 and bool(announcements)

        if not detail_available:
            return {
                "detail_checked": True,
                "detail_available": False,
                "detail": project_payload.get("data") or {},
                "raw_api_url": raw_api_url,
                "employee_url": employee_url,
                "structured_attachments": ((project_payload.get("data") or {}).get("GovernmentPurchaseFile")) or [],
                "detail_risk_note": DETAIL_RISK_NOTE,
            }

        return {
            "detail_checked": True,
            "detail_available": True,
            "detail": project_payload.get("data") or {},
            "announcement": selected_announcement,
            "raw_api_url": raw_api_url,
            "employee_url": employee_url,
            "structured_attachments": ((project_payload.get("data") or {}).get("GovernmentPurchaseFile")) or [],
            "announcement_selection_used_fallback": selection_used_fallback,
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        section_id = (item.get("bidSectionId") or "").strip()
        payload = (detail or {}).get("detail") or {}
        project = payload.get("governmentProcurementProjectInformation") or {}
        section_list = payload.get("GovernmentProcureSectionInformationList") or []
        section = section_list[0] if section_list else {}
        announcement = (detail or {}).get("announcement") or {}
        files = _normalize_attachment_records(
            (detail or {}).get("structured_attachments") or payload.get("GovernmentPurchaseFile") or [],
            base_url=str((detail or {}).get("raw_api_url") or self.url),
        )
        notice_html = announcement.get("noticeContent") or ""
        notice_text = html_to_text(notice_html)
        content_summary, qualification_summary = _summarize_changsha_notice(
            notice_html,
            section_content=section.get("purchaseSectionContent"),
            section_qualification=section.get("purchaseQualification"),
        )
        deadline = extract_datetime_after_label(
            notice_text,
            ["投标截止时间", "开标时间", "提交投标文件截止时间", "提交响应文件截止时间", "响应文件提交截止时间"],
        )
        consortium = extract_accepts_consortium(notice_text)
        budget_context = parse_amount_context(
            _stringify_number(project.get("programBudget") or section.get("sectionBudget")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("预算", "项目预算", "采购预算"),
        )
        ceiling_context = parse_amount_context(
            _stringify_number(section.get("controlPrice") or section.get("sectionBudget")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("最高限价", "限价", "控制价"),
        )
        notice = Notice(
            source=self.source_config.get("source", "Changsha Procurement"),
            source_subtype=self.source_config.get("source_subtype", "长沙政府采购交易"),
            dedupe_key="",
            section_id=section_id,
            notice_id=(announcement.get("id") or "").strip(),
            notice_title=(announcement.get("noticeName") or item.get("noticeName") or "").strip(),
            notice_publish_time=(announcement.get("noticeSendTime") or item.get("noticeSendTime") or "").strip(),
            project_name=(project.get("purchaseProjectName") or item.get("purchaseProjectName") or "").strip(),
            section_name=(section.get("purchaseSectionName") or item.get("purchaseSectionName") or "").strip(),
            notice_type=(
                announcement.get("bulletinType") or announcement.get("noticeType") or item.get("noticeType") or ""
            ).strip(),
            project_code=(project.get("purchaseProjectCode") or item.get("projectId") or "").strip(),
            purchaser_or_tenderer=(project.get("purchaserName") or "").strip(),
            agency=(project.get("purchaserAgencyName") or announcement.get("bulletinDuty") or "").strip(),
            region="长沙",
            publish_time=(announcement.get("noticeSendTime") or item.get("noticeSendTime") or "").strip(),
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
                base_url=notice.employee_readable_url or notice.raw_api_url or self.url,
                structured_records=files,
                detail_risk_note=(detail or {}).get("detail_risk_note"),
            ),
        )
        notice.detail_risk_note = _build_quality_risk_note(notice, detail)
        notice.dedupe_key = _build_dedupe_key(notice)
        return notice

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
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
            else:
                inaccessible_count += 1

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "pages_scanned": list_stats.get("pages_scanned", 1),
            "page_size": list_stats.get("page_size", 10),
            "list_count": list_stats.get("fetched_total", 0),
            "fetched_total": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
            "skipped_count": skipped,
            "real_notice_count": len(notices),
            "error_count": list_stats.get("error_count", 0),
            "fetch_failed": list_stats.get("fetch_failed", 0),
            "detail_unavailable_count": inaccessible_count,
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")


def _summarize_changsha_notice(
    notice_html: str,
    *,
    section_content: Any = None,
    section_qualification: Any = None,
) -> tuple[str, str]:
    lines = _clean_notice_lines(notice_html)
    content_summary = _extract_keyword_summary(lines, CONTENT_MARKERS)
    qualification_summary = _extract_keyword_summary(lines, QUALIFICATION_MARKERS)

    if _is_generic_summary(content_summary):
        content_summary = _clean_detail_fallback(section_content)
    if _is_generic_summary(qualification_summary):
        qualification_summary = _clean_detail_fallback(section_qualification)

    return (
        content_summary or MISSING_SUMMARY,
        qualification_summary or MISSING_SUMMARY,
    )


def _clean_notice_lines(notice_html: str) -> list[str]:
    text = html_to_text(notice_html or "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_keyword_summary(lines: list[str], markers: tuple[str, ...], *, limit: int = 220) -> str:
    if not lines:
        return ""

    collected: list[str] = []
    collecting = False

    for index, line in enumerate(lines):
        normalized = _normalize_line(line)
        if not normalized:
            continue

        matched_marker = next((marker for marker in markers if marker in normalized), "")
        if matched_marker and not collecting:
            collecting = True
            snippet = _trim_marker_prefix(normalized, matched_marker)
            if snippet and not _should_skip_line(snippet):
                collected.append(snippet)
            elif _is_meaningful_line(normalized):
                collected.append(normalized)
            continue

        if collecting:
            if _looks_like_new_section(normalized, markers):
                break
            if _should_skip_line(normalized):
                continue
            collected.append(normalized)
            if len(collected) >= 6:
                break

    if not collected:
        matched_lines = [
            _normalize_line(line)
            for line in lines
            if any(marker in _normalize_line(line) for marker in markers) and not _should_skip_line(_normalize_line(line))
        ]
        collected = matched_lines[:3]

    summary = "；".join(_dedupe_preserve_order(collected))
    summary = _trim_summary(summary, limit=limit)
    if _is_generic_summary(summary):
        return ""
    return summary


def _trim_marker_prefix(value: str, marker: str) -> str:
    index = value.find(marker)
    if index == -1:
        return value
    trimmed = value[index:]
    for separator in ("：", ":"):
        marker_prefix = f"{marker}{separator}"
        if trimmed.startswith(marker_prefix):
            return trimmed[len(marker_prefix) :].strip()
    return trimmed


def _clean_detail_fallback(value: Any) -> str:
    compact = _normalize_line(str(value or ""))
    if _is_generic_summary(compact):
        return ""
    return _trim_summary(compact, limit=180)


def _normalize_line(value: str) -> str:
    compact = re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()
    return compact.strip("；;")


def _looks_like_new_section(value: str, markers: tuple[str, ...]) -> bool:
    if any(marker in value for marker in markers):
        return False
    if SECTION_HEADING_RE.match(value):
        return True
    if value.startswith("附件") or value.startswith("下载") or value.startswith("采购文件"):
        return True
    return False


def _should_skip_line(value: str) -> bool:
    if not value:
        return True
    if value.endswith(".pdf") or value.endswith(".doc") or value.endswith(".docx"):
        return True
    if value.startswith("http://") or value.startswith("https://"):
        return True
    return False


def _is_meaningful_line(value: str) -> bool:
    return len(value) >= 6 and not _is_generic_summary(value)


def _is_generic_summary(value: str) -> bool:
    compact = _normalize_line(value)
    if compact in GENERIC_SUMMARY_VALUES:
        return True
    return compact.startswith("详见") and len(compact) <= 12


def _trim_summary(value: str, *, limit: int) -> str:
    compact = _normalize_line(value)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip("；;，, ") + "..."


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = _normalize_line(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results


def _build_dedupe_key(notice: Notice) -> str:
    if notice.section_id and notice.notice_id:
        return f"{notice.source_site}|{notice.section_id}|{notice.notice_id}"
    if notice.section_id and notice.notice_title and notice.notice_publish_time:
        return f"{notice.source_site}|{notice.section_id}|{notice.notice_title}|{notice.notice_publish_time}"
    if notice.section_id:
        return f"{notice.source_site}|{notice.section_id}"
    return f"{notice.source_site}|{notice.title}|{notice.published_at}"


def _stringify_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_attachment_records(records: list[dict[str, Any]], *, base_url: str) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    origin = base_origin(base_url)
    for record in records or []:
        if not isinstance(record, dict):
            continue
        title = str(record.get("fileNo") or record.get("name") or "").strip()
        file_id = str(record.get("fileId") or "").strip()
        url = ""
        if file_id:
            url = f"{origin}/tradeApi/file/download?id={file_id}"
        normalized.append(
            {
                "name": title,
                "url": url,
            }
        )
    return normalized


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


def _build_quality_risk_note(notice: Notice, detail: dict[str, Any] | None) -> str | None:
    notes: list[str] = []
    base_note = str((detail or {}).get("detail_risk_note") or "").strip()
    if base_note:
        notes.append(base_note)
    if (detail or {}).get("announcement_selection_used_fallback"):
        notes.append(ANNOUNCEMENT_MISMATCH_RISK_NOTE)

    missing_core_fields: list[str] = []
    if not notice.publish_time:
        missing_core_fields.append("发布时间")
    if not notice.notice_type:
        missing_core_fields.append("公告类型")
    if notice.content_summary == MISSING_SUMMARY:
        missing_core_fields.append("项目内容摘要")
    if notice.qualification_summary == MISSING_SUMMARY:
        missing_core_fields.append("资质要求摘要")
    if missing_core_fields:
        notes.append(f"部分核心字段未提取到：{'、'.join(missing_core_fields)}")

    if notice.has_attachment:
        notes.append(ATTACHMENT_LIMIT_NOTE)
    if notice.has_attachment and notice.qualification_summary == MISSING_SUMMARY:
        notes.append("资质要求可能依赖附件，当前未解析")

    deduped: list[str] = []
    seen: set[str] = set()
    for note in notes:
        compact = note.strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        deduped.append(compact)
    return "；".join(deduped) or None


def _build_changsha_list_url(url: str, *, current: int, size: int) -> str:
    paged_url = build_paged_url(url, current=current, size=size)
    parts = urlsplit(paged_url)
    query_items = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in LIST_DEFAULT_PARAMS.items():
        query_items.setdefault(key, value)
    return urlunsplit(parts._replace(query=urlencode(query_items)))


def _select_announcement_record(
    announcements: list[dict[str, Any]],
    *,
    list_notice_type: str,
) -> tuple[dict[str, Any], bool]:
    if not announcements:
        return {}, False

    target_bulletin_type = NOTICE_TYPE_TO_BULLETIN_TYPE.get((list_notice_type or "").strip(), "")
    if target_bulletin_type:
        for announcement in announcements:
            if target_bulletin_type in str(announcement.get("bulletinType") or ""):
                return announcement, announcement is not announcements[0]
    return announcements[0], False
