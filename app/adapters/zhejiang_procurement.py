from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import quote

import requests

from ..attachment_utils import apply_attachment_result, discover_attachments
from ..html_extract import extract_datetime_after_label, html_to_text
from ..models import Notice
from .base import BaseAdapter


SEARCH_HOME_API = "https://zfcg.czt.zj.gov.cn/portal/searchHome"
DETAIL_API = "https://zfcg.czt.zj.gov.cn/portal/detail"
DETAIL_PAGE = "https://zfcg.czt.zj.gov.cn/site/detail"
LIST_DEFAULT_CODE = "110-606633"
LIST_DEFAULT_SUB_CODES = ["110-306476", "110-684034", "110-511933"]
LIST_DEFAULT_EXCLUDE_PREFIX = ["90", "006011", "H0", "001111"]
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
MISSING_SUMMARY = "未提取到"
ATTACHMENT_LIMIT_NOTE = "附件仅做发现，未下载或解析"
DETAIL_API_RISK_NOTE = "详情页本身是前端壳页，当前依赖 /portal/detail 返回正文 HTML"
ORDERING_RISK_NOTE = "默认结果可能存在置顶旧文或非严格时序"
FIELD_LIMIT_NOTE = "JSON 门户流字段有限"
DEADLINE_LABELS = [
    "投标截止时间",
    "开标时间",
    "提交投标文件截止时间",
    "递交投标文件截止时间",
    "提交响应文件截止时间",
    "响应文件提交截止时间",
]
CONTENT_MARKERS = (
    "项目概况",
    "招标项目概况",
    "采购需求",
    "采购内容",
    "采购标的",
    "简要技术要求",
)
QUALIFICATION_MARKERS = (
    "供应商资格要求",
    "投标人资格要求",
    "申请人的资格要求",
    "落实政府采购政策需满足的资格要求",
    "本项目的特定资格要求",
)
SECTION_HEADING_RE = re.compile(r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.]|\(?[一二三四五六七八九十]+\))")


class ZhejiangProcurementAdapter(BaseAdapter):
    def __init__(
        self,
        source_name: str,
        url: str,
        region: str,
        fetcher,
        source_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(source_name, url, region, fetcher, source_config)
        self.session = requests.Session()
        self.session.trust_env = False
        timeout_value = getattr(fetcher, "timeout", 20)
        self.timeout = int(timeout_value) if isinstance(timeout_value, (int, float, str)) else 20

    def fetch_list(self) -> list[dict[str, Any]]:
        payload = _build_search_payload(self.source_config)
        response = self._post_json(self.url or SEARCH_HOME_API, payload)
        data = ((response or {}).get("result") or {}).get("data") or {}
        children = data.get("children") or []
        first_id = str(data.get("firstId") or self.source_config.get("parent_id") or "600007")
        page_size = int(payload.get("pageSize") or self.source_config.get("page_size") or 10)

        records: list[dict[str, Any]] = []
        for item in children[:page_size]:
            if not isinstance(item, dict):
                continue
            enriched = dict(item)
            enriched["_first_id"] = first_id
            enriched["_search_code"] = str(payload.get("code") or "")
            records.append(enriched)

        self._list_stats = {
            "fetched_total": len(records),
            "fetch_failed": 0 if records else 1,
            "page_size": page_size,
            "first_id": first_id,
        }
        return records

    def fetch_detail(self, item: dict[str, Any]) -> dict[str, Any] | None:
        article_id = str(item.get("articleId") or "").strip()
        if not article_id:
            return None

        payload = self._get_json(DETAIL_API, {"articleId": article_id}) or {}
        detail = ((payload.get("result") or {}).get("data")) or {}
        detail_available = bool(detail and detail.get("content"))
        if not detail_available:
            return {
                "detail_checked": True,
                "detail_available": False,
                "detail": detail,
                "raw_api_url": _build_detail_api_url(article_id),
                "employee_url": _build_detail_page_url(str(item.get("_first_id") or "600007"), article_id),
                "detail_risk_note": "详情正文未获取，当前仅保留列表字段",
            }

        return {
            "detail_checked": True,
            "detail_available": True,
            "detail": detail,
            "raw_api_url": _build_detail_api_url(article_id),
            "employee_url": _build_detail_page_url(str(item.get("_first_id") or "600007"), article_id),
            "structured_attachments": _normalize_attachment_records(detail.get("attachmentVO") or {}),
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        article_id = str(item.get("articleId") or "").strip()
        detail_payload = (detail or {}).get("detail") or {}
        detail_html = str(detail_payload.get("content") or "")
        attachment_payload = detail_payload.get("attachmentVO") or {}
        detail_text = html_to_text(detail_html)
        publish_time = _normalize_timestamp(item.get("pubDate")) or str(item.get("publishDateString") or "").strip()
        deadline = _normalize_timestamp(item.get("bidOpeningTime")) or extract_datetime_after_label(detail_text, DEADLINE_LABELS)
        content_summary = _extract_section_summary(detail_text, CONTENT_MARKERS)
        if not content_summary:
            content_summary = _build_minimal_summary(
                title=str(item.get("title") or detail_payload.get("title") or "").strip(),
                region=str(item.get("districtName") or self.region or "浙江省").strip(),
                procurement_method=str(item.get("purchaseMethod") or "").strip(),
            )
        qualification_summary = _extract_section_summary(detail_text, QUALIFICATION_MARKERS) or MISSING_SUMMARY
        project_name = str(detail_payload.get("projectName") or item.get("title") or "").strip()
        project_code = str(detail_payload.get("projectCode") or "").strip()
        category_names = detail_payload.get("categoryNames") or []
        notice_type = ""
        if isinstance(category_names, list) and category_names:
            notice_type = str(category_names[-1] or "").strip()
        if not notice_type:
            notice_type = str(item.get("purchaseMethod") or "").strip()

        notice = Notice(
            source=self.source_config.get("source", "浙江政府采购网"),
            source_subtype=self.source_config.get("source_subtype", "政府采购 / JSON门户流"),
            dedupe_key=f"{self.source_name}|{article_id}",
            section_id=article_id,
            project_name=project_name,
            notice_id=article_id,
            notice_title=str(item.get("title") or detail_payload.get("title") or "").strip(),
            notice_publish_time=publish_time,
            notice_type=notice_type,
            project_code=project_code,
            purchaser_or_tenderer=str(item.get("purchaseName") or "").strip(),
            agency=str(detail_payload.get("author") or "").strip(),
            region=str(item.get("districtName") or self.region or "浙江省").strip() or "浙江省",
            publish_time=publish_time,
            bid_open_or_response_deadline=deadline,
            procurement_method=str(item.get("purchaseMethod") or "").strip(),
            content_summary=content_summary,
            qualification_summary=qualification_summary,
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
                detail_html=detail_html,
                base_url=attachment_payload.get("domain") or DETAIL_PAGE,
                structured_records=(detail or {}).get("structured_attachments") or [],
                detail_risk_note=_build_detail_risk_note(
                    detail_available=bool((detail or {}).get("detail_available")),
                    qualification_summary=qualification_summary,
                    deadline=deadline,
                ),
            ),
        )
        return notice

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
        detail_partial = 0
        detail_failed = 0

        for item in self.fetch_list():
            detail = self.fetch_detail(item)
            if not detail:
                detail_failed += 1
                continue
            notice = self.normalize(item, detail)
            notices.append(notice)
            if notice.detail_available:
                detail_success += 1
                if _notice_has_partial_gap(notice):
                    detail_partial += 1
            else:
                detail_failed += 1

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "list_count": list_stats.get("fetched_total", 0),
            "page_size": list_stats.get("page_size", 10),
            "detail_success_count": detail_success,
            "detail_partial_count": detail_partial,
            "detail_failed_count": detail_failed,
            "real_notice_count": len(notices),
            "fetch_failed": list_stats.get("fetch_failed", 0),
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("JSON adapter does not use parse()")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = self.session.post(url, headers=BROWSER_HEADERS, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = self.session.get(url, headers=BROWSER_HEADERS, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def _build_search_payload(source_config: dict[str, Any]) -> dict[str, Any]:
    page_size = int(source_config.get("page_size") or 10)
    return {
        "code": str(source_config.get("category_code") or LIST_DEFAULT_CODE),
        "subCodes": list(source_config.get("sub_codes") or LIST_DEFAULT_SUB_CODES),
        "excludeDistrictPrefix": list(source_config.get("exclude_district_prefix") or LIST_DEFAULT_EXCLUDE_PREFIX),
        "isGov": True,
        "districtCode": source_config.get("district_code"),
        "needNewCnt": True,
        "needValidCount": True,
        "needTotal": True,
        "pageSize": page_size,
        "isStick": False,
    }


def _build_detail_page_url(parent_id: str, article_id: str) -> str:
    return f"{DETAIL_PAGE}?parentId={parent_id}&articleId={quote(article_id, safe='')}"


def _build_detail_api_url(article_id: str) -> str:
    return f"{DETAIL_API}?articleId={quote(article_id, safe='')}"


def _normalize_timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_attachment_records(attachment_payload: dict[str, Any]) -> list[dict[str, str]]:
    domain = str(attachment_payload.get("domain") or "").strip()
    attachments = attachment_payload.get("attachments") or []
    records: list[dict[str, str]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("fileId") or "").strip()
        name = str(item.get("name") or "").strip()
        if not (file_id or name):
            continue
        url = f"{domain}{file_id}" if domain and file_id else file_id
        records.append({"name": name, "url": url})
    return records


def _extract_section_summary(text: str, markers: tuple[str, ...], *, limit: int = 220) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    collected: list[str] = []
    collecting = False

    for line in lines:
        normalized = _normalize_line(line)
        if not normalized:
            continue
        matched_marker = next((marker for marker in markers if marker in normalized), "")
        if matched_marker and not collecting:
            collecting = True
            snippet = _trim_marker_prefix(normalized, matched_marker)
            if snippet and not _is_generic_summary(snippet):
                collected.append(snippet)
            elif len(normalized) >= 6:
                collected.append(normalized)
            continue
        if collecting:
            if _looks_like_new_section(normalized, markers):
                break
            collected.append(normalized)
            if len(collected) >= 6:
                break

    summary = "；".join(_dedupe_preserve_order(collected))
    summary = _trim_summary(summary, limit=limit)
    if _is_generic_summary(summary):
        return ""
    return summary or ""


def _build_minimal_summary(*, title: str, region: str, procurement_method: str) -> str:
    parts = [part for part in [region, procurement_method, title] if part]
    return " / ".join(parts) if parts else MISSING_SUMMARY


def _build_detail_risk_note(*, detail_available: bool, qualification_summary: str, deadline: str) -> str:
    notes = [FIELD_LIMIT_NOTE, DETAIL_API_RISK_NOTE, ORDERING_RISK_NOTE]
    if not detail_available:
        notes.append("详情正文未获取，当前仅保留列表字段")
    if not deadline:
        notes.append("deadline 缺失不能视为 parser 必然失败")
    if qualification_summary == MISSING_SUMMARY:
        notes.append("qualification_summary 缺失不能视为 parser 必然失败")
    deduped: list[str] = []
    seen: set[str] = set()
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        deduped.append(note)
    return "；".join(deduped)


def _notice_has_partial_gap(notice: Notice) -> bool:
    return (
        notice.qualification_summary == MISSING_SUMMARY
        or not (notice.bid_open_or_response_deadline or "").strip()
        or not notice.detail_available
    )


def _trim_marker_prefix(value: str, marker: str) -> str:
    index = value.find(marker)
    if index < 0:
        return value
    trimmed = value[index:]
    for separator in ("：", ":"):
        prefix = f"{marker}{separator}"
        if trimmed.startswith(prefix):
            return trimmed[len(prefix) :].strip()
    return trimmed


def _looks_like_new_section(value: str, markers: tuple[str, ...]) -> bool:
    if any(marker in value for marker in markers):
        return False
    if SECTION_HEADING_RE.match(value):
        return True
    return any(value.startswith(prefix) for prefix in ("附件", "预算金额", "最高限价", "获取招标文件"))


def _trim_summary(value: str, *, limit: int) -> str:
    compact = _normalize_line(value)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip("；， ") + "..."


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


def _is_generic_summary(value: str) -> bool:
    compact = _normalize_line(value)
    return compact in {"", "详见附件", "详见采购文件", "详见招标文件"}


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip().strip("；")
