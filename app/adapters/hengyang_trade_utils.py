from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from ..html_extract import compact_text, extract_accepts_consortium, extract_between, extract_datetime_after_label, html_to_text


def base_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def summarize_notice_html(html: str) -> tuple[str, str, str, str]:
    text = html_to_text(html or "")
    content_summary = extract_between(
        text,
        ["项目基本情况：", "项目基本情况", "采购项目内容与数量：", "采购项目内容与数量", "项目概况", "采购需求"],
        ["投标人资格要求", "资格要求", "供应商资格条件", "投标人的资格要求", "三、", "四、", "3.", "4."],
        limit=320,
    )
    qualification_summary = extract_between(
        text,
        ["投标人资格要求", "投标人的资格要求", "供应商资格条件", "资格要求"],
        ["招标文件的获取", "获取磋商文件", "获取采购文件", "响应文件的递交", "提交首次响应文件的截止时间", "五、", "六、", "5.", "6."],
        limit=320,
    )
    deadline = extract_datetime_after_label(
        text,
        ["投标截止时间", "开标时间", "提交首次响应文件的截止时间", "响应文件的递交截止时间"],
    )
    consortium = extract_accepts_consortium(text)
    if not content_summary:
        content_summary = compact_text(text, limit=320)
    return content_summary, qualification_summary, deadline, consortium


def build_transaction_detail_url(
    *,
    origin: str,
    tender_project_type: str,
    section_id: str,
) -> str:
    route_type = normalize_route_type(tender_project_type)
    return (
        f"{origin}/#/resources/transactionDetail/{route_type}"
        f"?bidSectionId={quote(section_id)}&t=GC"
    )


def build_paged_url(url: str, *, current: int, size: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["current"] = str(current)
    query["size"] = str(size)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query),
            parsed.fragment,
        )
    )


def normalize_route_type(value: str) -> str:
    compact = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return compact or "construction"
