from __future__ import annotations

from typing import Any

from ..amount_utils import RAW_TEXT_SOURCE, parse_amount_context
from ..html_extract import html_to_text
from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import base_origin, summarize_notice_html


class HengyangProcurementAdapter(BaseAdapter):
    def fetch_list(self) -> list[dict[str, Any]]:
        payload = self.fetcher.get_json(self.url) or {}
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
        raw_api_url = (
            f"{origin}/tradeApi/governmentPurchase/projectInformation/getAnnouncementBySectionId"
            f"?sectionId={section_id}"
        )
        ann_payload = self.fetcher.get_json(raw_api_url) or {}
        ann_list = ((ann_payload.get("data") or {}).get("governmentProcureAnnouncementInformation")) or []
        if ann_payload.get("code") != 200 or not ann_list:
            return None

        return {
            "detail": project_payload.get("data") or {},
            "announcement": ann_list[0],
            "raw_api_url": raw_api_url,
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        if not detail:
            raise ValueError("procurement detail is required")

        section_id = (item.get("bidSectionId") or "").strip()
        payload = detail.get("detail") or {}
        project = payload.get("governmentProcurementProjectInformation") or {}
        section_list = payload.get("GovernmentProcureSectionInformationList") or []
        files = payload.get("GovernmentPurchaseFile") or []
        section = section_list[0] if section_list else {}
        ann = detail.get("announcement") or {}
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

        return Notice(
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
            original_url=str(detail.get("raw_api_url") or ""),
            employee_readable_url="",
            raw_api_url=str(detail.get("raw_api_url") or ""),
            has_attachment=bool(files),
            attachment_count=len(files),
            fetched_at=self.now_string(),
        )

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
        skipped = 0

        for item in self.fetch_list():
            if not (item.get("bidSectionId") or "").strip():
                skipped += 1
                continue

            detail = self.fetch_detail(item)
            if not detail:
                skipped += 1
                continue

            notices.append(self.normalize(item, detail))
            detail_success += 1

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "list_count": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
            "skipped_count": skipped,
            "real_notice_count": detail_success,
            "fetch_failed": list_stats.get("fetch_failed", 0),
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")


def _stringify_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
