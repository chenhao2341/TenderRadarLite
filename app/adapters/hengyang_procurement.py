from __future__ import annotations

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
            region=(project.get("regionCode") or item.get("regionName") or self.region).strip(),
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
            "list_count": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
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
