from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from ..amount_utils import RAW_TEXT_SOURCE, parse_amount_context
from ..attachment_utils import apply_attachment_result, discover_attachments
from ..html_extract import extract_accepts_consortium, html_to_text
from ..models import Notice
from .base import BaseAdapter


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DETAIL_RISK_NOTE = "详情页不可访问或解析失败"
MISSING_VALUE = "未提取到"
ATTACHMENT_LIMIT_NOTE = "附件仅做发现，未下载或解析"
GENERIC_SUMMARY_VALUES = {
    "",
    "详见采购文件",
    "详见招标文件",
    "详见磋商文件",
    "详见谈判文件",
    "详见附件",
    "详见相关附件",
}
CONTENT_MARKERS = (
    "项目概况",
    "采购需求",
    "采购标的",
    "简要技术需求",
    "简要技术要求",
    "项目基本情况",
    "合同履行期限",
    "采购内容",
    "服务内容",
)
QUALIFICATION_MARKERS = (
    "申请人的资格要求",
    "供应商资格要求",
    "投标人的资格要求",
    "投标人资格要求",
    "本项目的特定资格要求",
    "参加政府采购活动应当具备的条件",
    "落实政府采购政策需满足的资格要求",
    "满足《中华人民共和国政府采购法》第二十二条规定",
)
RESULT_NOTICE_KEYWORDS = ("中标", "成交", "结果公告", "结果", "更正公告", "更正")
LIST_ITEM_RE = re.compile(
    r"<li>\s*<a[^>]+href=['\"](?P<href>[^'\"]+)['\"][^>]+title=['\"](?P<title>[^'\"]+)['\"][^>]*>.*?</a>"
    r"\s*<em[^>]*>\s*(?P<notice_type>.*?)\s*</em>\s*发布时间：<em>(?P<publish_time>.*?)</em>"
    r"\s*地域：<em>(?P<region>.*?)</em>\s*采购人：<em>(?P<purchaser>.*?)</em>",
    re.IGNORECASE | re.DOTALL,
)
ARTICLE_ID_RE = re.compile(r"t\d+_(\d+)\.htm", re.IGNORECASE)
DATETIME_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y年%m月%d日 %H时%M分%S秒",
    "%Y年%m月%d日 %H时%M分",
    "%Y年%m月%d日 %H:%M:%S",
    "%Y年%m月%d日 %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y年%m月%d日",
)
SECTION_HEADING_RE = re.compile(r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.]|\(?[一二三四五六七八九十]+\)|\d+\))")


class CcgpLocalAdapter(BaseAdapter):
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
        self.browser_headers = dict(BROWSER_HEADERS)
        timeout_value = getattr(fetcher, "timeout", 20)
        self.timeout = int(timeout_value) if isinstance(timeout_value, (int, float, str)) else 20

    def fetch_list(self) -> list[dict[str, Any]]:
        html, status_code, error_note = self._request_text(self.url)
        if not html:
            self._list_stats = {
                "pages_scanned": 1,
                "page_size": int(self.source_config.get("page_size", 20) or 20),
                "fetched_total": 0,
                "error_count": 1,
                "fetch_failed": 1,
                "status_code": status_code,
                "error_note": error_note,
            }
            return []

        records = self._parse_list_html(html)
        self._list_stats = {
            "pages_scanned": 1,
            "page_size": int(self.source_config.get("page_size", 20) or 20),
            "fetched_total": len(records),
            "error_count": 0,
            "fetch_failed": 0,
            "status_code": status_code,
            "error_note": error_note,
        }
        return records

    def fetch_detail(self, item: dict[str, Any]) -> dict[str, Any] | None:
        canonical_url = str(item.get("canonical_detail_url") or "").strip()
        if not canonical_url:
            return None

        html, status_code, error_note = self._request_text(canonical_url)
        if not html:
            return {
                "detail_checked": True,
                "detail_available": False,
                "detail_html": "",
                "meta": {},
                "attachments": [],
                "raw_api_url": "",
                "employee_url": canonical_url,
                "detail_risk_note": error_note or DETAIL_RISK_NOTE,
                "status_code": status_code,
            }

        meta, attachments, detail_html = _parse_detail_html(html, canonical_url)
        return {
            "detail_checked": True,
            "detail_available": True,
            "detail_html": detail_html,
            "meta": meta,
            "attachments": attachments,
            "raw_api_url": "",
            "employee_url": canonical_url,
            "detail_risk_note": None,
            "status_code": status_code,
        }

    def normalize(self, item: dict[str, Any], detail: dict[str, Any] | None = None) -> Notice:
        meta = (detail or {}).get("meta") or {}
        detail_html = str((detail or {}).get("detail_html") or "")
        detail_text = html_to_text(detail_html)
        content_summary = _extract_section_summary(detail_text, CONTENT_MARKERS)
        qualification_summary = _extract_section_summary(detail_text, QUALIFICATION_MARKERS)
        notice_type = str(item.get("notice_type") or "").strip()
        is_result_notice = _is_result_notice(notice_type)

        if not content_summary:
            content_summary = MISSING_VALUE
        if not qualification_summary:
            qualification_summary = MISSING_VALUE

        project_name = str(
            meta.get("采购项目名称") or meta.get("项目名称") or item.get("notice_title") or ""
        ).strip()
        project_code = _extract_project_code(detail_text) or str(
            meta.get("项目编号") or meta.get("采购项目编号") or meta.get("招标编号") or ""
        ).strip()
        file_get_deadline = _normalize_range_or_text(
            str(meta.get("获取招标文件时间") or meta.get("获取采购文件时间") or "").strip()
        )
        bid_deadline = _normalize_detail_deadline(meta, detail_text, notice_type)

        budget_context = parse_amount_context(
            _extract_raw_amount_value(str(meta.get("预算金额") or meta.get("总中标金额") or "").strip()),
            field_text=str(meta.get("预算金额") or meta.get("总中标金额") or "").strip(),
            text_sources=[(RAW_TEXT_SOURCE, detail_text)],
            field_hints=("预算", "中标金额", "成交金额", "合同包"),
        )
        ceiling_context = parse_amount_context(
            _extract_raw_amount_value(str(meta.get("最高限价") or "").strip()),
            field_text=str(meta.get("最高限价") or "").strip(),
            text_sources=[(RAW_TEXT_SOURCE, detail_text)],
            field_hints=("最高限价", "限价", "控制价"),
        )

        notice = Notice(
            source=self.source_config.get("source", "中国政府采购网"),
            source_subtype=self.source_config.get("source_subtype", "地方公告"),
            dedupe_key="",
            section_id=str(item.get("article_id") or item.get("canonical_detail_url") or "").strip(),
            project_name=project_name,
            notice_id=str(item.get("article_id") or "").strip(),
            notice_title=str(item.get("notice_title") or "").strip(),
            notice_publish_time=str(item.get("publish_time") or "").strip(),
            notice_type=notice_type,
            project_code=project_code,
            purchaser_or_tenderer=str(
                item.get("purchaser_or_tenderer") or meta.get("采购单位") or meta.get("采购人") or ""
            ).strip(),
            agency=str(meta.get("代理机构名称") or meta.get("采购代理机构") or "").strip(),
            region=str(item.get("region") or meta.get("行政区域") or self.region).strip() or "地区未确认",
            publish_time=str(item.get("publish_time") or "").strip(),
            file_get_deadline=file_get_deadline,
            bid_open_or_response_deadline=bid_deadline,
            budget_amount=budget_context.raw_value,
            ceiling_price=ceiling_context.raw_value,
            budget_amount_unit=budget_context.unit or "",
            budget_amount_unit_source=budget_context.unit_source,
            budget_amount_raw_text_snippet=budget_context.raw_text_snippet,
            ceiling_price_unit=ceiling_context.unit or "",
            ceiling_price_unit_source=ceiling_context.unit_source,
            ceiling_price_raw_text_snippet=ceiling_context.raw_text_snippet,
            procurement_method=str(meta.get("采购方式") or notice_type or "").strip(),
            content_summary=content_summary,
            qualification_summary=qualification_summary,
            accepts_consortium=extract_accepts_consortium(detail_text),
            original_url=str(item.get("canonical_detail_url") or ""),
            employee_readable_url=str(item.get("canonical_detail_url") or ""),
            raw_api_url="",
            fetched_at=self.now_string(),
        )
        apply_attachment_result(
            notice,
            discover_attachments(
                detail_checked=bool((detail or {}).get("detail_checked")),
                detail_available=bool((detail or {}).get("detail_available")),
                detail_html=detail_html,
                base_url=notice.employee_readable_url or self.url,
                structured_records=(detail or {}).get("attachments") or [],
                detail_risk_note=self._build_detail_risk_note(
                    detail=detail,
                    notice_type=notice_type,
                    content_summary=content_summary,
                    qualification_summary=qualification_summary,
                    project_code=project_code,
                    bid_deadline=bid_deadline,
                    budget_context=budget_context,
                    ceiling_context=ceiling_context,
                ),
            ),
        )
        notice.dedupe_key = _build_dedupe_key(
            source=notice.source,
            source_subtype=notice.source_subtype,
            article_id=str(item.get("article_id") or "").strip(),
            canonical_url=notice.original_url,
        )
        return notice

    def crawl(self) -> list[Notice]:
        notices: list[Notice] = []
        detail_success = 0
        detail_partial = 0
        detail_failed = 0
        latest_site_publish_time = ""

        for item in self.fetch_list():
            detail = self.fetch_detail(item)
            if not detail:
                detail_failed += 1
                continue
            notice = self.normalize(item, detail)
            notices.append(notice)
            latest_site_publish_time = max(latest_site_publish_time, notice.publish_time or "")
            if notice.detail_available:
                detail_success += 1
                if _notice_has_partial_gap(notice):
                    detail_partial += 1
            else:
                detail_failed += 1

        list_stats = getattr(self, "_list_stats", {})
        self.last_crawl_stats = {
            "pages_scanned": 1,
            "page_size": list_stats.get("page_size", 20),
            "list_count": list_stats.get("fetched_total", 0),
            "fetched_total": list_stats.get("fetched_total", 0),
            "detail_success_count": detail_success,
            "detail_partial_count": detail_partial,
            "detail_failed_count": detail_failed,
            "real_notice_count": len(notices),
            "error_count": list_stats.get("error_count", 0),
            "fetch_failed": list_stats.get("fetch_failed", 0),
            "latest_site_publish_time": latest_site_publish_time,
            "detail_unavailable_count": detail_failed,
        }
        return notices

    def parse(self, html: str) -> list[Notice]:
        raise NotImplementedError("HTML adapter uses fetch_list/fetch_detail/normalize pipeline")

    def _request_text(self, url: str) -> tuple[str | None, int | None, str | None]:
        try:
            response = self.session.get(url, headers=self.browser_headers, timeout=self.timeout)
        except Exception:
            return None, None, "请求失败"

        status_code = int(response.status_code)
        if status_code == 403:
            return None, status_code, "请求被拒绝(403)，该来源需要浏览器型请求头"
        if status_code >= 400:
            return None, status_code, f"请求失败({status_code})"
        return response.content.decode("utf-8", errors="ignore"), status_code, None

    def _parse_list_html(self, html: str) -> list[dict[str, Any]]:
        return _parse_list_html(html, self.url)

    def _build_detail_risk_note(
        self,
        *,
        detail: dict[str, Any] | None,
        notice_type: str,
        content_summary: str,
        qualification_summary: str,
        project_code: str,
        bid_deadline: str,
        budget_context,
        ceiling_context,
    ) -> str | None:
        notes: list[str] = []
        base_note = str((detail or {}).get("detail_risk_note") or "").strip()
        relaxed_core_fields = _allows_relaxed_core_fields(notice_type)
        if base_note:
            notes.append(base_note)
        if content_summary == MISSING_VALUE:
            if relaxed_core_fields:
                notes.append("\u7ed3\u679c/\u66f4\u6b63\u7c7b\u516c\u544a\u672a\u63d0\u4f9b\u53ef\u590d\u7528\u7684\u9879\u76ee\u5185\u5bb9\u6458\u8981")
            else:
                notes.append("\u9879\u76ee\u5185\u5bb9\u6458\u8981\u672a\u63d0\u53d6\u5230")
        if not relaxed_core_fields and qualification_summary == MISSING_VALUE:
            notes.append("\u8d44\u8d28\u8981\u6c42\u672a\u63d0\u53d6\u5230")
        if not relaxed_core_fields and not (project_code or "").strip():
            notes.append("\u9879\u76ee\u7f16\u53f7\u672a\u63d0\u53d6\u5230")
        if not relaxed_core_fields and not (bid_deadline or "").strip():
            notes.append("\u622a\u6b62\u65f6\u95f4\u672a\u63d0\u53d6\u5230")
        if (
            not relaxed_core_fields
            and not (budget_context.raw_value or "").strip()
            and not (ceiling_context.raw_value or "").strip()
        ):
            notes.append("\u9884\u7b97\u91d1\u989d/\u9650\u4ef7\u672a\u63d0\u53d6\u5230")
        if (budget_context.raw_value or "").strip() and not (budget_context.unit or "").strip():
            notes.append("\u91d1\u989d\u5355\u4f4d\u672a\u786e\u8ba4")
        if ((detail or {}).get("attachments") or []):
            notes.append(ATTACHMENT_LIMIT_NOTE)
        deduped: list[str] = []
        seen: set[str] = set()
        for note in notes:
            compact = note.strip()
            if not compact or compact in seen:
                continue
            seen.add(compact)
            deduped.append(compact)
        return "\uff1b".join(deduped) or None


def _allows_relaxed_core_fields(notice_type: str) -> bool:
    normalized = (notice_type or "").strip()
    return _is_result_notice(normalized) or "\u66f4\u6b63" in normalized


def _notice_has_partial_gap(notice: Notice) -> bool:
    if notice.content_summary == MISSING_VALUE:
        return True
    if _allows_relaxed_core_fields(notice.notice_type):
        return False
    if notice.qualification_summary == MISSING_VALUE:
        return True
    if not (notice.project_code or "").strip():
        return True
    if not (notice.bid_open_or_response_deadline or "").strip():
        return True
    if not (notice.budget_amount or "").strip() and not (notice.ceiling_price or "").strip():
        return True
    return False


def _parse_list_html(html: str, base_url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    match = re.search(r"<ul\s+class=['\"]c_list_bid['\"]>(?P<body>.*?)</ul>", html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return results

    for item_match in LIST_ITEM_RE.finditer(match.group("body")):
        href = _clean_text(item_match.group("href"))
        canonical_url = urljoin(base_url, href)
        article_id = _extract_article_id(canonical_url)
        publish_time = _normalize_datetime(_clean_text(item_match.group("publish_time")))
        results.append(
            {
                "notice_title": _clean_text(item_match.group("title")),
                "notice_type": _clean_text(item_match.group("notice_type")),
                "publish_time": publish_time,
                "region": _clean_text(item_match.group("region")),
                "purchaser_or_tenderer": _clean_text(item_match.group("purchaser")),
                "relative_detail_url": href,
                "canonical_detail_url": canonical_url,
                "article_id": article_id,
                "source": "中国政府采购网",
                "source_subtype": "地方公告",
                "original_url": canonical_url,
                "employee_readable_url": canonical_url,
                "raw_api_url": "",
                "dedupe_key": _build_dedupe_key(
                    source="中国政府采购网",
                    source_subtype="地方公告",
                    article_id=article_id,
                    canonical_url=canonical_url,
                ),
            }
        )
    return results


def _parse_detail_html(html: str, base_url: str) -> tuple[dict[str, str], list[dict[str, str]], str]:
    parser = _DetailParser()
    parser.feed(html)
    meta = _rows_to_meta(parser.rows)
    attachments = _build_attachment_records(parser.rows, base_url)
    detail_html = _extract_detail_html(html)
    return meta, attachments, detail_html


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self._in_tr = False
        self._in_td = False
        self._current_row_cells: list[str] = []
        self._current_cell_parts: list[str] = []
        self._current_row_anchors: list[dict[str, str]] = []
        self._current_anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (value or "") for key, value in attrs}
        if tag == "tr":
            self._in_tr = True
            self._current_row_cells = []
            self._current_row_anchors = []
        elif self._in_tr and tag == "td":
            self._in_td = True
            self._current_cell_parts = []
        elif self._in_tr and tag == "a":
            self._current_anchor = {
                "href": attr_map.get("href", ""),
                "id": attr_map.get("id", ""),
                "title": "",
            }

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_td:
            text = _clean_text(" ".join(self._current_cell_parts))
            if text:
                self._current_row_cells.append(text)
            self._current_cell_parts = []
            self._in_td = False
        elif tag == "a" and self._current_anchor is not None:
            self._current_anchor["title"] = _clean_text(self._current_anchor.get("title", ""))
            self._current_row_anchors.append(self._current_anchor)
            self._current_anchor = None
        elif tag == "tr" and self._in_tr:
            if self._current_row_cells or self._current_row_anchors:
                self.rows.append({"cells": list(self._current_row_cells), "anchors": list(self._current_row_anchors)})
            self._in_tr = False

    def handle_data(self, data: str) -> None:
        if self._in_td:
            text = _clean_text(data)
            if text:
                self._current_cell_parts.append(text)
        if self._current_anchor is not None:
            text = _clean_text(data)
            if text:
                current = self._current_anchor.get("title", "")
                self._current_anchor["title"] = f"{current} {text}".strip() if current else text


def _rows_to_meta(rows: list[dict[str, Any]]) -> dict[str, str]:
    meta: dict[str, str] = {}
    for row in rows:
        cells = [str(value).strip() for value in row.get("cells", []) if str(value).strip()]
        if not cells or cells[0] == "公告信息：" or cells[0].startswith("附件"):
            continue
        if cells[0].startswith("附件") or cells[0].startswith("合同包") or re.match(r"^\d+-\d+$", cells[0]):
            continue
        if len(cells) == 2:
            meta[cells[0]] = cells[1]
            continue
        if len(cells) == 4:
            meta[cells[0]] = cells[1]
            meta[cells[2]] = cells[3]
            continue
        meta[cells[0]] = " ".join(cells[1:])
    return meta


def _build_attachment_records(rows: list[dict[str, Any]], base_url: str) -> list[dict[str, str]]:
    attachments: list[dict[str, str]] = []
    for row in rows:
        cells = [str(value).strip() for value in row.get("cells", []) if str(value).strip()]
        anchors = row.get("anchors", []) or []
        if not cells or not anchors:
            continue
        if not (cells[0].startswith("附件") or cells[0].startswith("合同包")):
            continue
        for anchor in anchors:
            title = _clean_text(anchor.get("title", ""))
            href = _clean_text(anchor.get("href", ""))
            anchor_id = _clean_text(anchor.get("id", ""))
            if not _is_business_attachment(href, title):
                continue
            url = _normalize_attachment_url(base_url, href, anchor_id)
            attachments.append(
                {
                    "title": title,
                    "url": url,
                    "file_type": "",
                    "source_section": cells[0],
                }
            )
    return attachments


def _extract_detail_html(html: str) -> str:
    notice_area_html = _extract_target_div_html(html, attr_name="id", attr_value="noticeArea")
    if notice_area_html:
        return notice_area_html

    content_html = _extract_target_div_html(html, attr_name="class", attr_value="vF_detail_content")
    if content_html:
        return content_html
    return html


def _extract_target_div_html(html: str, *, attr_name: str, attr_value: str) -> str:
    parser = _TargetDivExtractor(attr_name=attr_name, attr_value=attr_value)
    parser.feed(html)
    parser.close()
    return parser.captured_html


class _TargetDivExtractor(HTMLParser):
    def __init__(self, *, attr_name: str, attr_value: str) -> None:
        super().__init__(convert_charrefs=False)
        self.attr_name = attr_name
        self.attr_value = attr_value
        self.captured_html = ""
        self._capturing = False
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (value or "") for key, value in attrs}
        matched = (
            tag == "div"
            and (
                attr_map.get(self.attr_name, "") == self.attr_value
                or (
                    self.attr_name == "class"
                    and self.attr_value in {part.strip() for part in attr_map.get("class", "").split()}
                )
            )
        )
        if matched and not self._capturing:
            self._capturing = True
            self._depth = 1
            return
        if self._capturing:
            self.captured_html += self.get_starttag_text()
            if tag == "div":
                self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing:
            return
        if tag == "div":
            self._depth -= 1
            if self._depth == 0:
                self._capturing = False
                return
        self.captured_html += f"</{tag}>"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._capturing:
            self.captured_html += self.get_starttag_text()[:-1] + "/>"

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self.captured_html += data

    def handle_entityref(self, name: str) -> None:
        if self._capturing:
            self.captured_html += f"&{name};"

    def handle_charref(self, name: str) -> None:
        if self._capturing:
            self.captured_html += f"&#{name};"

    def handle_comment(self, data: str) -> None:
        if self._capturing:
            self.captured_html += f"<!--{data}-->"


def _normalize_attachment_url(base_url: str, href: str, anchor_id: str) -> str:
    normalized_href = (href or "").strip()
    if normalized_href:
        return urljoin(base_url, normalized_href)
    if anchor_id:
        return f"{base_url}#attachment-{anchor_id}"
    return base_url


def _is_business_attachment(href: str, title: str) -> bool:
    normalized_href = (href or "").strip().lower()
    normalized_title = (title or "").strip()
    if not normalized_title:
        return False
    if normalized_href.startswith("javascript:"):
        return False
    if "jiucuo.html" in normalized_href or "纠错" in normalized_title:
        return False
    if normalized_title in {"首页", "返回首页"}:
        return False
    extension_match = re.search(r"\.(pdf|docx?|xlsx?|zip|rar|wps)$", normalized_title, flags=re.IGNORECASE)
    if extension_match:
        return True
    return normalized_title.startswith("附件") or normalized_title.startswith("合同包")


def _extract_project_code(text: str) -> str:
    patterns = (
        r"(?:项目编号|采购项目编号|采购编号|招标编号|项目代码|标项编号|包号)\s*[:：]\s*([A-Za-z0-9.\-_/]+)",
        r"（([A-Za-z]{1,10}\d{2,}[-A-Za-z0-9.]*)）",
    )
    normalized = _normalize_space(text)
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            return match.group(1).strip()
    return ""


def _normalize_detail_deadline(meta: dict[str, str], detail_text: str, notice_type: str) -> str:
    candidates = [
        meta.get("提交投标文件截止时间", ""),
        meta.get("提交响应文件截止时间", ""),
        meta.get("响应文件提交截止时间", ""),
        meta.get("投标截止时间", ""),
        meta.get("递交截止时间", ""),
        meta.get("截止时间", ""),
        meta.get("开标时间", ""),
        meta.get("响应文件开启时间", ""),
        meta.get("提交截止时间", ""),
    ]
    for value in candidates:
        normalized = _extract_datetime(value)
        if normalized:
            return normalized

    label_patterns = [
        r"(?:文件递交截止时间|提交投标文件截止时间|提交响应文件截止时间|响应文件提交截止时间|投标截止时间|递交截止时间|截止时间|开标时间|响应文件开启时间|开启时间)\s*[:：]?\s*(20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?(?:\s+\d{1,2}(?::\d{2}(?::\d{2})?|时\d{1,2}分(?:\d{1,2}秒)?)?)?)"
    ]
    compact_text = _normalize_space(detail_text)
    for pattern in label_patterns:
        match = re.search(pattern, compact_text)
        if match is not None:
            return _normalize_datetime(match.group(1))

    narrative_patterns = [
        r"(?:并于|于)\s*(20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?(?:\s+\d{1,2}(?::\d{2}(?::\d{2})?|时\d{1,2}分(?:\d{1,2}秒)?)?)?)\s*(?:（北京时间）)?前(?:提交|递交)(?:投标|响应)?文件",
        r"(20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?(?:\s+\d{1,2}(?::\d{2}(?::\d{2})?|时\d{1,2}分(?:\d{1,2}秒)?)?)?)\s*(?:开标|开启)",
    ]
    for pattern in narrative_patterns:
        match = re.search(pattern, compact_text)
        if match is not None:
            return _normalize_datetime(match.group(1))

    if _is_result_notice(notice_type):
        return ""
    return ""


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
            if normalized.startswith("http"):
                continue
            collected.append(normalized)
            if len(collected) >= 6:
                break

    summary = "；".join(_dedupe_preserve_order(collected))
    summary = _trim_summary(summary, limit=limit)
    if _is_generic_summary(summary):
        return ""
    return summary


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
    return any(
        value.startswith(prefix)
        for prefix in ("附件", "采购单位", "代理机构", "公告期限", "其他补充事宜", "凡对本次公告内容提出询问")
    )


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


def _extract_raw_amount_value(value: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)", value or "")
    return match.group(1) if match is not None else ""


def _normalize_range_or_text(value: str) -> str:
    if not value:
        return ""
    normalized = _normalize_space(value)
    parts = re.findall(r"20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?", normalized)
    if len(parts) >= 2:
        return f"{_normalize_datetime(parts[0])} 至 {_normalize_datetime(parts[1])}"
    return normalized


def _extract_datetime(value: str) -> str:
    match = re.search(
        r"(20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}(?:日)?(?:\s+\d{1,2}(?::\d{2}(?::\d{2})?|时\d{1,2}分(?:\d{1,2}秒)?)?)?)",
        value or "",
    )
    if match is None:
        return ""
    return _normalize_datetime(match.group(1))


def _normalize_datetime(value: str) -> str:
    import datetime as _dt

    raw = _normalize_space(value).replace("：", ":")
    for pattern in DATETIME_PATTERNS:
        try:
            parsed = _dt.datetime.strptime(raw, pattern)
        except ValueError:
            continue
        if "%H" in pattern:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        return parsed.strftime("%Y-%m-%d")
    return raw


def _extract_article_id(url: str) -> str:
    match = ARTICLE_ID_RE.search(url or "")
    return match.group(1) if match is not None else ""


def _build_dedupe_key(*, source: str, source_subtype: str, article_id: str, canonical_url: str) -> str:
    prefix = f"{source}-{source_subtype}"
    if article_id:
        return f"{prefix}|{article_id}"
    return f"{prefix}|{canonical_url}"


def _is_result_notice(notice_type: str) -> bool:
    normalized = (notice_type or "").strip()
    return any(keyword in normalized for keyword in RESULT_NOTICE_KEYWORDS)


def _is_generic_summary(value: str) -> bool:
    compact = _normalize_line(value)
    if compact in GENERIC_SUMMARY_VALUES:
        return True
    return compact.startswith("详见") and len(compact) <= 12


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _normalize_line(value: str) -> str:
    return _normalize_space(value).strip("；;")


def _clean_text(value: str) -> str:
    return _normalize_space(re.sub(r"<[^>]+>", " ", value or ""))
