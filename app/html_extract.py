from __future__ import annotations

import re
from html import unescape
from typing import Iterable, List, Optional
from urllib.parse import urljoin


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    cleaned = TAG_RE.sub(" ", text)
    return " ".join(unescape(cleaned).split())


def html_to_text(html: str) -> str:
    text = re.sub(r"</li>|</div>|</p>|</tr>|</h\d>|<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    return strip_tags(text)


def find_anchor_blocks(html: str) -> Iterable[tuple[str, str]]:
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        yield match.group(1), strip_tags(match.group(2))


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def extract_date(text: str) -> str:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""


def find_nearby_date(lines: List[str], idx: int) -> str:
    for offset in range(0, 3):
        check = idx - offset
        if 0 <= check < len(lines):
            date = extract_date(lines[check])
            if date:
                return date
    return ""


def line_blocks(html: str) -> List[str]:
    text = html_to_text(html)
    return [line.strip() for line in text.splitlines() if line.strip()]


def find_links_with_dates(html: str, base_url: str, link_hint: str) -> List[tuple[str, str, str]]:
    lines = line_blocks(html)
    results: List[tuple[str, str, str]] = []
    seen = set()

    anchor_pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    anchor_matches = list(anchor_pattern.finditer(html))
    cleaned_lines = line_blocks(re.sub(r"<a", "\n<a", html, flags=re.IGNORECASE))

    for idx, line in enumerate(cleaned_lines):
        if link_hint not in line:
            continue
        for href, text in find_anchor_blocks(line):
            if link_hint not in href:
                continue
            if len(text) < 6:
                continue
            full_url = normalize_url(base_url, href)
            key = (full_url, text)
            if key in seen:
                continue
            seen.add(key)
            results.append((text, full_url, find_nearby_date(cleaned_lines, idx)))

    if results:
        return results

    for match in anchor_matches:
        href = match.group(1)
        if link_hint not in href:
            continue
        text = strip_tags(match.group(2))
        if len(text) < 6:
            continue
        start = max(0, match.start() - 200)
        snippet = strip_tags(html[start:match.end() + 200])
        date = extract_date(snippet)
        full_url = normalize_url(base_url, href)
        key = (full_url, text)
        if key in seen:
            continue
        seen.add(key)
        results.append((text, full_url, date))

    return results


def compact_text(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def extract_between(text: str, start_markers: List[str], end_markers: List[str], limit: int = 300) -> str:
    start_idx = -1
    start_len = 0
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
            start_len = len(marker)
    if start_idx == -1:
        return ""

    snippet = text[start_idx + start_len :]
    end_idx = len(snippet)
    for marker in end_markers:
        idx = snippet.find(marker)
        if idx != -1:
            end_idx = min(end_idx, idx)
    return compact_text(snippet[:end_idx], limit=limit)


def extract_datetime_after_label(text: str, labels: List[str]) -> str:
    patterns = [
        r"(20\d{2}[-年/.]\d{1,2}[-月/.]\d{1,2}[日]?\s*\d{1,2}[:：]\d{2}(?::\d{2})?)",
        r"(20\d{2}[-年/.]\d{1,2}[-月/.]\d{1,2}[日]?)",
    ]
    for label in labels:
        idx = text.find(label)
        if idx == -1:
            continue
        snippet = text[idx : idx + 120]
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                return match.group(1).replace("：", ":").strip()
    return ""


def extract_accepts_consortium(text: str) -> str:
    for marker in ["不接受联合体", "本项目不接受联合体", "是否支持联合体投标：否", "不接受联合体投标"]:
        if marker in text:
            return "否"
    for marker in ["接受联合体", "本项目接受联合体", "是否支持联合体投标：是", "接受联合体投标"]:
        if marker in text:
            return "是"
    return ""
