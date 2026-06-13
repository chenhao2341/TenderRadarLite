from __future__ import annotations

from .models import Notice


def build_dedupe_key(notice: Notice) -> str:
    if notice.dedupe_key:
        return notice.dedupe_key
    if notice.section_id and notice.notice_id:
        return f"{notice.source_site}|{notice.section_id}|{notice.notice_id}"
    if notice.section_id and notice.notice_type and notice.notice_publish_time:
        return f"{notice.source_site}|{notice.section_id}|{notice.notice_type}|{notice.notice_publish_time}"
    if notice.section_id:
        return f"{notice.source_site}|{notice.section_id}"
    if notice.source_url:
        return f"{notice.source_site}|{notice.source_url}"
    return f"{notice.source_site}|{notice.title}|{notice.published_at}"
