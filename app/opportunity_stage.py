from __future__ import annotations

from .models import Notice


STAGE_LABELS = {
    "new_opportunity": "新机会",
    "project_update": "项目动态",
    "correction_or_clarification": "更正/澄清/答疑",
    "rebid_signal": "流标/重招线索",
    "award_result": "中标/成交结果",
    "mismatch_procurement": "明显不匹配采购",
    "needs_manual_review": "需人工复核",
    "unknown": "未知",
}


def classify_opportunity_stage(notice: Notice) -> str:
    text = _notice_text(notice)
    notice_type = (notice.notice_type or "").upper()

    if _contains_any(text, ["管材", "材料采购", "纯材料采购", "设备采购", "货物采购", "施工总承包", "安全生产许可证"]):
        return "mismatch_procurement"
    if notice_type in {"GENGZHENG_NOTICE", "CHENGQING_NOTICE"} or _contains_any(text, ["更正", "澄清", "答疑", "补遗", "变更"]):
        return "correction_or_clarification"
    if notice_type == "CHONGXIN_ZHAOBIAO_NOTICE" or _contains_any(text, ["流标", "废标", "终止", "重新招标", "二次招标", "重招"]):
        return "rebid_signal"
    if _contains_any(text, ["中标", "成交", "结果公告", "合同公告", "中标候选人"]):
        return "award_result"
    if _contains_any(text, ["项目动态", "进展", "暂停", "恢复"]):
        return "project_update"
    if notice_type in {"ZHAOBIAO_NOTICE"} or _contains_any(text, ["招标", "采购", "磋商", "谈判", "询价"]):
        return "new_opportunity"
    if text:
        return "needs_manual_review"
    return "unknown"


def opportunity_stage_label(stage: str) -> str:
    return STAGE_LABELS.get((stage or "").strip(), stage or STAGE_LABELS["unknown"])


def _notice_text(notice: Notice) -> str:
    return " ".join(
        value
        for value in [
            notice.notice_title,
            notice.project_name,
            notice.section_name,
            notice.notice_type,
            notice.procurement_method,
            notice.content_summary,
            notice.qualification_summary,
        ]
        if value
    )


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
