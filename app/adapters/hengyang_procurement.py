from __future__ import annotations

from typing import Any, List

from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import base_origin, summarize_notice_html


class HengyangProcurementAdapter(BaseAdapter):
    def crawl(self) -> List[Notice]:
        payload = self.fetcher.get_json(self.url) or {}
        records = ((payload.get("data") or {}).get("records")) or []
        notices: List[Notice] = []
        detail_success = 0
        skipped = 0
        origin = base_origin(self.url)

        for record in records:
            section_id = (record.get("bidSectionId") or "").strip()
            if not section_id:
                skipped += 1
                continue

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
                skipped += 1
                continue

            detail = project_payload.get("data") or {}
            project = detail.get("governmentProcurementProjectInformation") or {}
            section_list = detail.get("GovernmentProcureSectionInformationList") or []
            files = detail.get("GovernmentPurchaseFile") or []
            section = section_list[0] if section_list else {}
            ann = ann_list[0]

            content_summary, qualification_summary, deadline, consortium = summarize_notice_html(
                ann.get("noticeContent") or ""
            )

            notices.append(
                Notice(
                    source=self.source_config.get("source", "衡阳分平台"),
                    source_subtype=self.source_config.get("source_subtype", "政府采购交易"),
                    dedupe_key=f"{self.source_name}|{section_id}",
                    section_id=section_id,
                    project_name=(project.get("purchaseProjectName") or record.get("purchaseProjectName") or "").strip(),
                    section_name=(section.get("purchaseSectionName") or record.get("purchaseSectionName") or "").strip(),
                    notice_type=(ann.get("bulletinType") or record.get("noticeType") or "公告").strip(),
                    project_code=(project.get("purchaseProjectCode") or record.get("projectId") or "").strip(),
                    purchaser_or_tenderer=(project.get("purchaserName") or "").strip(),
                    agency=(project.get("purchaserAgencyName") or "").strip(),
                    region=(project.get("regionCode") or record.get("regionName") or self.region).strip(),
                    publish_time=(ann.get("noticeSendTime") or record.get("noticeSendTime") or "").strip(),
                    file_get_deadline=deadline if "截止" in deadline else "",
                    bid_open_or_response_deadline=deadline,
                    budget_amount=_stringify_number(project.get("programBudget") or section.get("sectionBudget")),
                    ceiling_price=_stringify_number(section.get("controlPrice") or section.get("sectionBudget")),
                    procurement_method=(section.get("tenderType") or project.get("purchaserMode") or "").strip(),
                    content_summary=content_summary,
                    qualification_summary=qualification_summary,
                    accepts_consortium=consortium,
                    original_url=raw_api_url,
                    employee_readable_url="",
                    raw_api_url=raw_api_url,
                    has_attachment=bool(files),
                    attachment_count=len(files),
                    fetched_at=self.now_string(),
                )
            )
            detail_success += 1

        self.last_crawl_stats = {
            "list_count": len(records),
            "detail_success_count": detail_success,
            "skipped_count": skipped,
            "real_notice_count": detail_success,
        }
        return notices

    def parse(self, html: str) -> List[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")


def _stringify_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
