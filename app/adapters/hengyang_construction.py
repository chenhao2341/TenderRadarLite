from __future__ import annotations

from typing import Any

from ..dedupe import build_dedupe_key
from ..models import Notice
from .base import BaseAdapter
from .hengyang_trade_utils import (
    base_origin,
    build_paged_url,
    build_transaction_detail_url,
    summarize_notice_html,
)


class HengyangConstructionAdapter(BaseAdapter):
    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        fetched_sections = 0
        detail_success = 0
        skipped = 0
        error_count = 0
        successful_pages = 0
        latest_site_publish_time = ""
        origin = base_origin(self.url)
        pages_scanned = max(int(self.source_config.get("pages_scanned", 1) or 1), 1)
        page_size = max(int(self.source_config.get("page_size", 10) or 10), 1)

        for page in range(1, pages_scanned + 1):
            page_url = build_paged_url(self.url, current=page, size=page_size)
            payload = self.fetcher.get_json(page_url) or {}
            data = payload.get("data") or {}
            records = data.get("records") or []
            if not payload:
                error_count += 1
                continue

            successful_pages += 1
            fetched_sections += len(records)

            for record in records:
                section_id = (record.get("bidSectionId") or "").strip()
                if not section_id:
                    skipped += 1
                    continue

                project_payload = self.fetcher.get_json(
                    f"{origin}/tradeApi/constructionTender/getBySectionId?sectionId={section_id}"
                ) or {}
                notice_payload = self.fetcher.get_json(
                    f"{origin}/tradeApi/constructionNotice/getBySectionId?sectionId={section_id}"
                ) or {}
                attachment_payload = self.fetcher.get_json(
                    f"{origin}/tradeApi/attach/proxy/getFileListBySectionId?sectionId={section_id}"
                ) or {}

                detail = project_payload.get("data") or {}
                notice_list = (notice_payload.get("data") or {}).get("noticeList") or []
                if not detail or not notice_list:
                    skipped += 1
                    continue

                tender = detail.get("constructionTender") or {}
                project = detail.get("constructionProject") or {}
                section_list = detail.get("constructionSectionList") or []
                section = section_list[0] if section_list else {}
                attachments = attachment_payload.get("data") or []
                raw_api_url = f"{origin}/tradeApi/constructionNotice/getBySectionId?sectionId={section_id}"
                employee_url = build_transaction_detail_url(
                    origin=origin,
                    tender_project_type=(record.get("tenderProjectType") or "CONSTRUCTION"),
                    section_id=section_id,
                )

                for notice_info in notice_list:
                    notice_html = notice_info.get("noticeContent") or ""
                    content_summary, qualification_summary, deadline, consortium = summarize_notice_html(notice_html)
                    notice = Notice(
                        source=self.source_config.get("source", "衡阳分平台"),
                        source_subtype=self.source_config.get("source_subtype", "建设工程交易"),
                        dedupe_key="",
                        section_id=section_id,
                        notice_id=(notice_info.get("id") or notice_info.get("noticeId") or "").strip(),
                        notice_title=(notice_info.get("noticeName") or "").strip(),
                        notice_publish_time=(notice_info.get("noticeSendTime") or record.get("noticeSendTime") or "").strip(),
                        project_name=(tender.get("tenderProjectName") or record.get("tenderProjectName") or "").strip(),
                        section_name=(section.get("bidSectionName") or record.get("bidSectionName") or "").strip(),
                        notice_type=(notice_info.get("bulletinType") or record.get("noticeType") or "招标公告").strip(),
                        project_code=(tender.get("tenderProjectCode") or project.get("projectCode") or "").strip(),
                        purchaser_or_tenderer=(tender.get("ownerName") or tender.get("tendererName") or "").strip(),
                        agency=(tender.get("tenderAgencyName") or "").strip(),
                        region=_normalize_region(project.get("regionCode") or record.get("name") or self.region),
                        publish_time=(notice_info.get("noticeSendTime") or record.get("noticeSendTime") or "").strip(),
                        file_get_deadline=(notice_info.get("docGetEndTime") or "").strip(),
                        bid_open_or_response_deadline=(
                            notice_info.get("bidOpenTime") or notice_info.get("bidOpeningTimeStart") or deadline
                        ).strip(),
                        budget_amount=_stringify_number(section.get("contractReckonPrice")),
                        ceiling_price=_stringify_number(section.get("tenderControlPrice")),
                        procurement_method=(tender.get("tenderMode") or section.get("tenderType") or "").strip(),
                        content_summary=content_summary,
                        qualification_summary=qualification_summary,
                        accepts_consortium=consortium,
                        original_url=employee_url,
                        employee_readable_url=employee_url,
                        raw_api_url=raw_api_url,
                        has_attachment=bool(attachments),
                        attachment_count=len(attachments),
                        fetched_at=self.now_string(),
                    )
                    notice.dedupe_key = build_dedupe_key(notice)
                    notices.append(notice)
                    detail_success += 1
                    latest_site_publish_time = max(latest_site_publish_time, notice.publish_time or "")

        self.last_crawl_stats = {
            "pages_scanned": pages_scanned,
            "page_size": page_size,
            "list_count": fetched_sections,
            "fetched_total": fetched_sections,
            "detail_success_count": detail_success,
            "skipped_count": skipped,
            "real_notice_count": detail_success,
            "error_count": error_count,
            "fetch_failed": 1 if successful_pages == 0 else 0,
            "latest_site_publish_time": latest_site_publish_time,
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
    return region.replace("·", "-")
