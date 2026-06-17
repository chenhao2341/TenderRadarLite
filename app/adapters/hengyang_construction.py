from __future__ import annotations

from typing import Any

from ..amount_utils import RAW_TEXT_SOURCE, parse_amount_context
from ..attachment_utils import apply_attachment_result, discover_attachments
from ..dedupe import build_dedupe_key
from ..html_extract import html_to_text
from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import (
    base_origin,
    build_paged_url,
    build_transaction_detail_url,
    summarize_notice_html,
)


class HengyangConstructionAdapter(BaseAdapter):
    def fetch_list(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        error_count = 0
        successful_pages = 0
        pages_scanned = max(int(self.source_config.get("pages_scanned", 1) or 1), 1)
        page_size = max(int(self.source_config.get("page_size", 10) or 10), 1)

        for page in range(1, pages_scanned + 1):
            page_url = build_paged_url(self.url, current=page, size=page_size)
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
        }
        return records

    def fetch_detail(self, item: dict[str, Any]) -> dict[str, Any] | None:
        section_id = (item.get("bidSectionId") or "").strip()
        if not section_id:
            return None

        origin = base_origin(self.url)
        employee_url = build_transaction_detail_url(
            origin=origin,
            tender_project_type=(item.get("tenderProjectType") or "CONSTRUCTION"),
            section_id=section_id,
        )
        raw_api_url = f"{origin}/tradeApi/constructionNotice/getBySectionId?sectionId={section_id}"
        project_payload = self.fetcher.get_json(
            f"{origin}/tradeApi/constructionTender/getBySectionId?sectionId={section_id}"
        ) or {}
        notice_payload = self.fetcher.get_json(
            raw_api_url
        ) or {}
        attachment_payload = self.fetcher.get_json(
            f"{origin}/tradeApi/attach/proxy/getFileListBySectionId?sectionId={section_id}"
        ) or {}

        detail = project_payload.get("data") or {}
        notice_list = (notice_payload.get("data") or {}).get("noticeList") or []
        detail_available = bool(detail and notice_list)
        if not detail_available:
            return {
                "detail_checked": True,
                "detail_available": False,
                "attachments": attachment_payload.get("data") or [],
                "raw_api_url": raw_api_url,
                "employee_url": employee_url,
                "detail_risk_note": "详情页不可访问或解析失败",
            }

        return {
            "detail_checked": True,
            "detail_available": True,
            "detail": detail,
            "notice_list": notice_list,
            "attachments": attachment_payload.get("data") or [],
            "raw_api_url": raw_api_url,
            "employee_url": employee_url,
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        section_id = (item.get("bidSectionId") or "").strip()
        payload = (detail or {}).get("detail") or {}
        tender = payload.get("constructionTender") or {}
        project = payload.get("constructionProject") or {}
        section_list = payload.get("constructionSectionList") or []
        section = section_list[0] if section_list else {}
        attachments = (detail or {}).get("attachments") or []
        notice_info = ((detail or {}).get("notice") or (((detail or {}).get("notice_list") or [{}])[0])) or {}
        notice_html = notice_info.get("noticeContent") or ""
        notice_text = html_to_text(notice_html)
        content_summary, qualification_summary, deadline, consortium = summarize_notice_html(notice_html)
        budget_context = parse_amount_context(
            _stringify_number(section.get("contractReckonPrice")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("预算", "估算", "投资", "合同估算价"),
        )
        ceiling_context = parse_amount_context(
            _stringify_number(section.get("tenderControlPrice")),
            text_sources=[(RAW_TEXT_SOURCE, notice_text)],
            field_hints=("最高", "限价", "控制价", "招标控制价"),
        )

        notice = Notice(
            source=self.source_config.get("source", "衡阳分平台"),
            source_subtype=self.source_config.get("source_subtype", "建设工程交易"),
            dedupe_key="",
            section_id=section_id,
            notice_id=(notice_info.get("id") or notice_info.get("noticeId") or "").strip(),
            notice_title=(notice_info.get("noticeName") or "").strip(),
            notice_publish_time=(notice_info.get("noticeSendTime") or item.get("noticeSendTime") or "").strip(),
            project_name=(tender.get("tenderProjectName") or item.get("tenderProjectName") or "").strip(),
            section_name=(section.get("bidSectionName") or item.get("bidSectionName") or "").strip(),
            notice_type=(notice_info.get("bulletinType") or item.get("noticeType") or "招标公告").strip(),
            project_code=(tender.get("tenderProjectCode") or project.get("projectCode") or "").strip(),
            purchaser_or_tenderer=(tender.get("ownerName") or tender.get("tendererName") or "").strip(),
            agency=(tender.get("tenderAgencyName") or "").strip(),
            region=_normalize_region(project.get("regionCode") or item.get("name") or self.region),
            publish_time=(notice_info.get("noticeSendTime") or item.get("noticeSendTime") or "").strip(),
            file_get_deadline=(notice_info.get("docGetEndTime") or "").strip(),
            bid_open_or_response_deadline=(
                notice_info.get("bidOpenTime") or notice_info.get("bidOpeningTimeStart") or deadline
            ).strip(),
            budget_amount=budget_context.raw_value,
            ceiling_price=ceiling_context.raw_value,
            budget_amount_unit=budget_context.unit or "",
            budget_amount_unit_source=budget_context.unit_source,
            budget_amount_raw_text_snippet=budget_context.raw_text_snippet,
            ceiling_price_unit=ceiling_context.unit or "",
            ceiling_price_unit_source=ceiling_context.unit_source,
            ceiling_price_raw_text_snippet=ceiling_context.raw_text_snippet,
            procurement_method=(tender.get("tenderMode") or section.get("tenderType") or "").strip(),
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
                structured_records=attachments,
                detail_risk_note=(detail or {}).get("detail_risk_note"),
            ),
        )
        notice.dedupe_key = build_dedupe_key(notice)
        return notice

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
        skipped = 0
        latest_site_publish_time = ""
        inaccessible_count = 0

        for item in self.fetch_list():
            if not (item.get("bidSectionId") or "").strip():
                skipped += 1
                continue

            detail = self.fetch_detail(item)
            if not detail:
                skipped += 1
                continue

            notice_list = detail.get("notice_list") or [None]
            for notice_info in notice_list:
                notice = self.normalize(item, {**detail, "notice": notice_info})
                notices.append(notice)
                if notice.detail_available:
                    detail_success += 1
                else:
                    inaccessible_count += 1
                latest_site_publish_time = max(latest_site_publish_time, notice.publish_time or "")

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "pages_scanned": list_stats.get("pages_scanned", 1),
            "page_size": list_stats.get("page_size", 10),
            "list_count": list_stats.get("fetched_total", 0),
            "fetched_total": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
            "skipped_count": skipped,
            "real_notice_count": detail_success,
            "error_count": list_stats.get("error_count", 0),
            "fetch_failed": 1 if list_stats.get("successful_pages", 0) == 0 else 0,
            "latest_site_publish_time": latest_site_publish_time,
            "detail_unavailable_count": inaccessible_count,
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")


def _stringify_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_region(value: str) -> str:
    region = (value or "").strip()
    return region.replace("路", "-")
