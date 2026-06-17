from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import html
from pathlib import Path
import re
from typing import Iterable
import webbrowser

from .ai_analysis import AIAnalysisResult, MISSING_TEXT, UNIT_UNCONFIRMED_TEXT
from .amount_utils import build_amount_context_from_notice, format_amount_with_context
from .models import Notice


REPORT_TITLE = "TenderRadarLite 本地招投标线索报告"
TIER_ORDER = ["DIRECT", "WATCHLIST", "EXCLUDE"]
TIER_LABELS = {
    "DIRECT": "DIRECT 直接商机",
    "WATCHLIST": "WATCHLIST 待复核",
    "EXCLUDE": "EXCLUDE 排除项",
}
TIER_HINTS = {
    "DIRECT": "优先展示高确定性的直接商机，适合人工尽快复核。",
    "WATCHLIST": "保留潜在线索与关联项目，适合继续观察和人工判断。",
    "EXCLUDE": "排除项默认折叠，避免干扰主要业务判断，必要时再展开核查。",
}
TIER_EMPTY_HINTS = {
    "DIRECT": "本轮没有直接商机。",
    "WATCHLIST": "本轮没有待复核线索。",
    "EXCLUDE": "本轮没有排除项。",
}
NOTICE_TYPE_LABELS = {
    "ZHAOBIAO_NOTICE": "招标公告",
    "CHENGQING_NOTICE": "澄清公告",
    "GENGZHENG_NOTICE": "更正公告",
    "ZANTING_NOTICE": "暂停公告",
    "REVIEW_NOTICE": "评审/复议公告",
    "CHONGXIN_ZHAOBIAO_NOTICE": "重新招标公告",
}
TIER_PRIORITY = {"DIRECT": 0, "WATCHLIST": 1, "EXCLUDE": 2}
AI_RECOMMENDATION_LABELS = {
    "follow_up": "建议跟进",
    "watch": "继续观察",
    "skip": "建议跳过",
}


@dataclass
class ProjectReportItem:
    aggregation_key: str
    project_name: str
    project_tier: str
    representative: Notice
    notices: list[Notice]
    notice_count: int
    notice_labels: list[str]
    latest_publish_time: str
    earliest_publish_time: str
    keyword_labels: list[str]
    positive_signals: list[str]
    negative_signals: list[str]
    content_summary: str
    content_summary_source_label: str | None
    qualification_summary: str
    qualification_summary_source_label: str | None


def write_html_report(
    path: Path,
    notices: Iterable[Notice],
    *,
    source_count: int = 0,
    generated_at: str | None = None,
    profile_name: str | None = None,
    ai_results: dict[str, AIAnalysisResult] | None = None,
    ai_status_message: str = "",
) -> Path:
    notice_list = list(notices)
    output_path = path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_html_report(
        notice_list,
        source_count=source_count,
        generated_at=generated_at,
        profile_name=profile_name,
        ai_results=ai_results,
        ai_status_message=ai_status_message,
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def build_html_report(
    notices: list[Notice],
    *,
    source_count: int = 0,
    generated_at: str | None = None,
    profile_name: str | None = None,
    ai_results: dict[str, AIAnalysisResult] | None = None,
    ai_status_message: str = "",
) -> str:
    timestamp = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    projects = aggregate_notices(notices)
    ai_results = ai_results or {}
    project_counts = Counter(item.project_tier for item in projects)
    stat_cards = [
        ("本轮公告数", str(len(notices)), "本轮抓取并进入本地报告的公告总数"),
        ("聚合项目数", str(len(projects)), "按项目或标段聚合后的展示对象数量"),
        ("DIRECT 直接商机", str(project_counts.get("DIRECT", 0)), "优先人工跟进的高价值线索"),
        ("WATCHLIST 待复核", str(project_counts.get("WATCHLIST", 0)), "需要继续观察或人工判断的线索"),
        ("EXCLUDE 排除项", str(project_counts.get("EXCLUDE", 0)), "默认折叠的排除项"),
    ]
    grouped = {tier: [item for item in projects if item.project_tier == tier] for tier in TIER_ORDER}

    if not notices:
        body_sections = f"""
        <section class="empty-state">
          <h2>本轮未发现新线索</h2>
          <p>运行时间：{_escape(timestamp)}</p>
          <p>后续建议：检查来源配置或稍后再运行。</p>
        </section>
        """
    else:
        body_sections = "".join(
            [
                _render_primary_section("DIRECT", grouped["DIRECT"], ai_results=ai_results),
                _render_primary_section("WATCHLIST", grouped["WATCHLIST"], ai_results=ai_results),
                _render_exclude_section(grouped["EXCLUDE"], ai_results=ai_results),
                _render_footer_note(),
            ]
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(REPORT_TITLE)}</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --surface: rgba(255, 255, 255, 0.88);
      --surface-strong: #fffdfa;
      --surface-soft: rgba(252, 248, 241, 0.9);
      --text: #211c16;
      --muted: #6f675d;
      --border: rgba(74, 60, 44, 0.12);
      --shadow: 0 24px 70px rgba(84, 64, 41, 0.12);
      --shadow-soft: 0 14px 40px rgba(84, 64, 41, 0.08);
      --direct: #0f6c4d;
      --direct-soft: #dff5ea;
      --watch: #9b6308;
      --watch-soft: #fff2d9;
      --exclude: #9d2f2f;
      --exclude-soft: #fbe1e1;
      --accent: #2457f5;
      --hero-a: #fcf1df;
      --hero-b: #eef7ef;
      --hero-c: #f6e8ef;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 0% 0%, rgba(255,255,255,0.92), transparent 32%),
        linear-gradient(135deg, var(--hero-a), var(--hero-b) 48%, var(--hero-c));
      min-height: 100vh;
    }}
    a {{ color: inherit; }}
    .page {{
      width: min(1320px, calc(100% - 40px));
      margin: 0 auto;
      padding: 34px 0 64px;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      padding: 34px;
      border-radius: 30px;
      border: 1px solid rgba(255,255,255,0.64);
      background: linear-gradient(145deg, rgba(255,252,247,0.92), rgba(255,255,255,0.76));
      box-shadow: var(--shadow);
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -40px;
      top: -50px;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(36,87,245,0.14), transparent 68%);
    }}
    .hero-grid {{
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(310px, 0.95fr);
      gap: 28px;
      align-items: start;
    }}
    .hero-copy h1 {{
      margin: 0;
      font-size: clamp(38px, 5vw, 56px);
      line-height: 1.02;
      letter-spacing: -0.045em;
    }}
    .hero-copy h2 {{
      margin: 10px 0 14px;
      font-size: clamp(20px, 2vw, 28px);
      font-weight: 700;
      letter-spacing: -0.03em;
    }}
    .hero-copy p {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.8;
      max-width: 720px;
    }}
    .hero-meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .hero-pill {{
      padding: 15px 16px;
      border-radius: 18px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.72);
      box-shadow: var(--shadow-soft);
      backdrop-filter: blur(10px);
    }}
    .hero-pill strong {{
      display: block;
      font-size: 12px;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .hero-pill span {{
      display: block;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin: 24px 0 30px;
    }}
    .stat-card {{
      padding: 20px;
      border-radius: 22px;
      border: 1px solid var(--border);
      background: var(--surface);
      box-shadow: var(--shadow-soft);
    }}
    .stat-card strong {{
      display: block;
      font-size: 12px;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .stat-card span {{
      display: block;
      font-size: clamp(28px, 3vw, 38px);
      font-weight: 800;
      letter-spacing: -0.05em;
      margin-bottom: 6px;
    }}
    .stat-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.65;
    }}
    .status-banner {{
      margin: 18px 0 0;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(155, 99, 8, 0.18);
      background: rgba(255, 242, 217, 0.92);
      color: #7b520b;
      font-size: 14px;
      line-height: 1.7;
    }}
    .report-flow {{
      display: grid;
      gap: 22px;
    }}
    .section {{
      border-radius: 28px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.82);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
      padding: 22px 24px 18px;
      border-bottom: 1px solid var(--border);
    }}
    .section-heading {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .section-title {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      font-size: 24px;
      letter-spacing: -0.03em;
    }}
    .section-dot {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }}
    .section-note {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.7;
    }}
    .section-count {{
      color: var(--muted);
      font-size: 14px;
      white-space: nowrap;
      padding-top: 4px;
    }}
    .project-list {{
      display: grid;
      gap: 16px;
      padding: 18px 22px 22px;
    }}
    .project-card {{
      display: grid;
      gap: 16px;
      padding: 22px;
      border-radius: 24px;
      border: 1px solid var(--border);
      background: var(--surface-strong);
      box-shadow: var(--shadow-soft);
    }}
    .project-top {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
    }}
    .project-title-wrap {{
      min-width: 0;
    }}
    .project-title {{
      margin: 0;
      font-size: 28px;
      line-height: 1.22;
      letter-spacing: -0.04em;
      word-break: break-word;
    }}
    .project-subtitle {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.7;
    }}
    .tier-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }}
    .tier-badge.direct {{ color: var(--direct); background: var(--direct-soft); }}
    .tier-badge.watchlist {{ color: var(--watch); background: var(--watch-soft); }}
    .tier-badge.exclude {{ color: var(--exclude); background: var(--exclude-soft); }}
    .fact-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px 12px;
    }}
    .fact {{
      padding: 12px 14px;
      border-radius: 16px;
      background: var(--surface-soft);
      border: 1px solid rgba(110, 94, 72, 0.08);
    }}
    .fact strong {{
      display: block;
      font-size: 12px;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .fact span {{
      display: block;
      font-size: 14px;
      line-height: 1.65;
      word-break: break-word;
    }}
    .signal-grid {{
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr;
      gap: 12px;
    }}
    .signal-card {{
      padding: 16px 18px;
      border-radius: 18px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.78);
    }}
    .signal-card strong {{
      display: block;
      margin-bottom: 8px;
      font-size: 12px;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .signal-card p {{
      margin: 0;
      font-size: 14px;
      line-height: 1.75;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      line-height: 1;
      color: #4a4035;
      background: rgba(244, 236, 221, 0.86);
      border: 1px solid rgba(145, 115, 74, 0.12);
    }}
    .chip.notice-type {{
      background: rgba(232, 239, 255, 0.82);
      border-color: rgba(64, 105, 204, 0.12);
      color: #2948a3;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .summary-box {{
      border-radius: 18px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.76);
      overflow: hidden;
    }}
    .summary-box summary {{
      cursor: pointer;
      padding: 14px 16px;
      list-style: none;
      font-weight: 700;
      font-size: 14px;
    }}
    .summary-box summary::-webkit-details-marker {{ display: none; }}
    .summary-box p {{
      margin: 0;
      padding: 0 16px 16px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.75;
    }}
    .summary-source {{
      color: #5f564c;
      font-weight: 700;
    }}
    .summary-body {{
      display: block;
      color: var(--muted);
      line-height: 1.75;
    }}
    .qualification-panel {{
      border-radius: 18px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.76);
      padding: 14px 16px 16px;
    }}
    .qualification-panel h5 {{
      margin: 0 0 10px;
      font-size: 14px;
      font-weight: 700;
    }}
    .qualification-panel p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.75;
    }}
    .qualification-missing {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
      margin-top: 8px;
    }}
    .qualification-details {{
      margin-top: 12px;
      border-top: 1px solid rgba(120, 102, 79, 0.1);
      padding-top: 12px;
    }}
    .qualification-details summary {{
      cursor: pointer;
      list-style: none;
      font-weight: 700;
      color: var(--accent);
      font-size: 14px;
    }}
    .qualification-details summary::-webkit-details-marker {{ display: none; }}
    .qualification-details p {{
      margin-top: 10px;
    }}
    .ai-panel {{
      border-radius: 18px;
      border: 1px solid rgba(36, 87, 245, 0.12);
      background: rgba(236, 243, 255, 0.74);
      padding: 16px 18px;
    }}
    .ai-panel h5 {{
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 800;
    }}
    .ai-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 12px;
      margin-bottom: 12px;
    }}
    .ai-meta {{
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255,255,255,0.76);
      border: 1px solid rgba(36, 87, 245, 0.08);
    }}
    .ai-meta strong {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .ai-meta span {{
      display: block;
      font-size: 14px;
      line-height: 1.6;
    }}
    .ai-panel p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.75;
    }}
    .qualification-fulltext {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.75;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .project-actions {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      border-top: 1px solid rgba(120, 102, 79, 0.1);
      padding-top: 14px;
    }}
    .link-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      font-weight: 800;
      box-shadow: 0 12px 24px rgba(36, 87, 245, 0.18);
    }}
    .action-note {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      text-align: right;
    }}
    .exclude-shell {{
      padding: 18px 22px 22px;
    }}
    .exclude-panel {{
      border-radius: 22px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.8);
      overflow: hidden;
    }}
    .exclude-panel > summary {{
      cursor: pointer;
      list-style: none;
      padding: 16px 18px;
      font-weight: 800;
      font-size: 15px;
      color: var(--exclude);
      background: rgba(253, 234, 234, 0.76);
    }}
    .exclude-panel > summary::-webkit-details-marker {{ display: none; }}
    .exclude-preview {{
      padding: 0 18px 14px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
    }}
    .footer-note {{
      padding: 20px 24px;
      border-radius: 24px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.78);
      box-shadow: var(--shadow-soft);
    }}
    .footer-note p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.8;
    }}
    .empty-state {{
      margin-top: 20px;
      padding: 54px 32px;
      border-radius: 28px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.84);
      box-shadow: var(--shadow);
      text-align: center;
    }}
    .empty-state h2 {{
      margin: 0 0 12px;
      font-size: 32px;
      letter-spacing: -0.04em;
    }}
    .empty-state p {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.8;
    }}
    @media (max-width: 1180px) {{
      .hero-grid,
      .stats,
      .fact-grid,
      .signal-grid,
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 860px) {{
      .page {{ width: min(100% - 24px, 1320px); padding-top: 18px; }}
      .hero {{ padding: 24px; }}
      .hero-meta {{ grid-template-columns: 1fr; }}
      .project-top,
      .project-actions,
      .section-header {{
        flex-direction: column;
        align-items: flex-start;
      }}
      .action-note {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="hero-grid">
        <div class="hero-copy">
          <h1>TenderRadarLite</h1>
          <h2>本地招投标线索报告</h2>
          <p>当前页面基于本轮抓取到的公告生成，展示层按项目或标段做聚合，用于快速判断 DIRECT 与 WATCHLIST 线索。飞书、AI 和 EXE 都不是当前本地报告的必要依赖。</p>
        </div>
        <div class="hero-meta">
          <div class="hero-pill"><strong>生成时间</strong><span>{_escape(timestamp)}</span></div>
          <div class="hero-pill"><strong>扫描来源数量</strong><span>{source_count}</span></div>
          <div class="hero-pill"><strong>本轮公告数</strong><span>{len(notices)}</span></div>
          <div class="hero-pill"><strong>聚合项目数</strong><span>{len(projects)}</span></div>
          <div class="hero-pill"><strong>DIRECT 项目数</strong><span>{project_counts.get("DIRECT", 0)}</span></div>
          <div class="hero-pill"><strong>WATCHLIST 项目数</strong><span>{project_counts.get("WATCHLIST", 0)}</span></div>
          <div class="hero-pill"><strong>EXCLUDE 项目数</strong><span>{project_counts.get("EXCLUDE", 0)}</span></div>
          <div class="hero-pill"><strong>报告定位</strong><span>本地聚合报告</span></div>
        </div>
      </div>
    </section>
    {_render_status_banner(ai_status_message)}
    <section class="stats">
      {"".join(_render_stat_card(title, value, note) for title, value, note in stat_cards)}
    </section>
    <section class="report-flow">
      {body_sections}
    </section>
  </main>
</body>
</html>
"""


def open_html_report(path: Path) -> bool:
    try:
        return bool(webbrowser.open(path.resolve().as_uri()))
    except Exception:
        return False


def aggregate_notices(notices: Iterable[Notice]) -> list[ProjectReportItem]:
    grouped: dict[str, list[Notice]] = {}
    for notice in notices:
        key = _aggregation_key(notice)
        grouped.setdefault(key, []).append(notice)

    items = [_build_project_item(key, project_notices) for key, project_notices in grouped.items()]
    return sorted(
        items,
        key=lambda item: (
            TIER_PRIORITY.get(item.project_tier, 9),
            _sortable_datetime(item.latest_publish_time),
            _completeness_score(item.representative),
            item.project_name,
        ),
        reverse=False,
    )


def _build_project_item(key: str, notices: list[Notice]) -> ProjectReportItem:
    sorted_notices = sorted(
        notices,
        key=lambda notice: (
            -_tier_rank(notice.lead_tier),
            -_sortable_datetime(notice.publish_time or notice.notice_publish_time),
            -_completeness_score(notice),
        ),
    )
    representative = sorted_notices[0]
    tier_candidates = [
        (notice.lead_tier or "EXCLUDE").upper()
        for notice in notices
        if (notice.lead_tier or "").upper() in TIER_PRIORITY
    ]
    project_tier = min(tier_candidates, key=lambda tier: TIER_PRIORITY[tier]) if tier_candidates else (representative.lead_tier or "EXCLUDE")
    latest_publish_time = max((notice.publish_time or notice.notice_publish_time or "") for notice in notices)
    earliest_publish_time = min((notice.publish_time or notice.notice_publish_time or "") for notice in notices)
    notice_labels = _unique_preserve_order(
        [_notice_type_label(notice.notice_type) for notice in sorted(notices, key=lambda item: _sortable_datetime(item.publish_time or item.notice_publish_time), reverse=True)]
    )
    keyword_labels = _unique_preserve_order(keyword for notice in sorted_notices for keyword in notice.hit_keywords if keyword)
    positive_signals = _unique_preserve_order(signal for notice in sorted_notices for signal in notice.matched_positive_signals if signal)
    negative_signals = _unique_preserve_order(signal for notice in sorted_notices for signal in notice.matched_negative_signals if signal)
    content_summary, content_summary_source_label = _select_best_summary(notices, "content_summary")
    qualification_summary, qualification_summary_source_label = _select_best_summary(notices, "qualification_summary")
    return ProjectReportItem(
        aggregation_key=key,
        project_name=representative.project_name or representative.title or "未提取到项目名称",
        project_tier=project_tier,
        representative=representative,
        notices=sorted(
            notices,
            key=lambda item: _sortable_datetime(item.publish_time or item.notice_publish_time),
            reverse=True,
        ),
        notice_count=len(notices),
        notice_labels=notice_labels,
        latest_publish_time=latest_publish_time,
        earliest_publish_time=earliest_publish_time,
        keyword_labels=keyword_labels,
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        content_summary=content_summary,
        content_summary_source_label=content_summary_source_label,
        qualification_summary=qualification_summary,
        qualification_summary_source_label=qualification_summary_source_label,
    )


def _render_stat_card(title: str, value: str, note: str) -> str:
    return (
        f'<article class="stat-card"><strong>{_escape(title)}</strong>'
        f"<span>{_escape(value)}</span><p>{_escape(note)}</p></article>"
    )


def _render_status_banner(message: str) -> str:
    if not message:
        return ""
    return f'<section class="status-banner">{_escape(message)}</section>'


def _render_primary_section(tier: str, items: list[ProjectReportItem], *, ai_results: dict[str, AIAnalysisResult]) -> str:
    section_body = (
        "".join(_render_project_card(item, ai_result=ai_results.get(item.aggregation_key)) for item in items)
        if items
        else f'<article class="project-card"><p class="section-note">{_escape(TIER_EMPTY_HINTS[tier])}</p></article>'
    )
    return f"""
    <section class="section">
      <div class="section-header">
        <div class="section-heading">
          <h3 class="section-title"><span class="section-dot" style="background:{_tier_color(tier)}"></span>{_escape(TIER_LABELS[tier])}</h3>
          <p class="section-note">{_escape(TIER_HINTS[tier])}</p>
        </div>
        <div class="section-count">{len(items)} 个项目</div>
      </div>
      <div class="project-list">{section_body}</div>
    </section>
    """


def _render_exclude_section(items: list[ProjectReportItem], *, ai_results: dict[str, AIAnalysisResult]) -> str:
    preview = "；".join(item.project_name for item in items[:5]) if items else TIER_EMPTY_HINTS["EXCLUDE"]
    body = (
        "".join(_render_project_card(item, compact=True, ai_result=ai_results.get(item.aggregation_key)) for item in items)
        if items
        else f'<article class="project-card"><p class="section-note">{_escape(TIER_EMPTY_HINTS["EXCLUDE"])}</p></article>'
    )
    return f"""
    <section class="section">
      <div class="section-header">
        <div class="section-heading">
          <h3 class="section-title"><span class="section-dot" style="background:{_tier_color("EXCLUDE")}"></span>{_escape(TIER_LABELS["EXCLUDE"])}</h3>
          <p class="section-note">{_escape(TIER_HINTS["EXCLUDE"])}</p>
        </div>
        <div class="section-count">{len(items)} 个项目</div>
      </div>
      <div class="exclude-shell">
        <details class="exclude-panel">
          <summary>展开查看 EXCLUDE 排除项（{len(items)} 个项目）</summary>
          <div class="exclude-preview">预览：{_escape(preview)}</div>
          <div class="project-list">{body}</div>
        </details>
      </div>
    </section>
    """


def _render_footer_note() -> str:
    return """
    <section class="footer-note">
      <p>本报告为本地自动生成，仅依赖当前抓取结果与本地 SQLite。飞书、AI、EXE 均不是当前本地报告的必要依赖；原文链接仅用于人工复核。</p>
    </section>
    """


def _render_project_card(item: ProjectReportItem, *, compact: bool = False, ai_result: AIAnalysisResult | None = None) -> str:
    rep = item.representative
    notice_types = "".join(f'<span class="chip notice-type">{_escape(label)}</span>' for label in item.notice_labels)
    keywords = _render_chip_row(item.keyword_labels, empty_label="无")
    positive = _render_chip_row(item.positive_signals, empty_label="无")
    negative = _render_chip_row(item.negative_signals, empty_label="无")
    content_summary = _truncate(item.content_summary, 320 if not compact else 220)
    qualification_summary = _truncate(item.qualification_summary, 320 if not compact else 220)
    content_source = _render_summary_source("项目内容摘要来源", item.content_summary_source_label)
    qualification_source = _render_summary_source("资质要求摘要来源", item.qualification_summary_source_label)
    return f"""
    <article class="project-card">
      <div class="project-top">
        <div class="project-title-wrap">
          <h4 class="project-title">【{_escape(item.project_tier)}】{_escape(item.project_name)}</h4>
          <p class="project-subtitle">关联公告 {item.notice_count} 条 · 最近发布时间 {_escape(_friendly_time(item.latest_publish_time))}</p>
        </div>
        <span class="tier-badge {_escape_attr(item.project_tier.lower())}"><span class="tier-code">{_escape(item.project_tier)}</span><span class="tier-text">{_escape(TIER_LABELS[item.project_tier])}</span></span>
      </div>
      <div class="fact-grid">
        {_fact("地区", rep.region or "未提取到")}
        {_fact("关联公告类型", "、".join(item.notice_labels) or "未提取到")}
        {_fact("招标人或采购单位", rep.purchaser_or_tenderer or "未提取到")}
        {_fact("代理机构", rep.agency or "未提取到")}
        {_fact("发布时间", _friendly_time(item.latest_publish_time))}
        {_fact("截止时间", _friendly_time(rep.bid_open_or_response_deadline or rep.file_get_deadline or "未提取到"))}
        {_fact("预算金额", _format_amount_display(rep, field_name="budget_amount"))}
        {_fact("最高限价", _format_amount_display(rep, field_name="ceiling_price"))}
      </div>
      <div class="signal-grid">
        <div class="signal-card">
          <strong>命中关键词</strong>
          <div class="chip-row">{keywords}</div>
        </div>
        <div class="signal-card">
          <strong>正向信号</strong>
          <div class="chip-row">{positive}</div>
        </div>
        <div class="signal-card">
          <strong>排除信号</strong>
          <div class="chip-row">{negative}</div>
        </div>
      </div>
      <div class="signal-card">
        <strong>分类理由</strong>
        <p>{_escape(rep.lead_reason or "未提取到")}</p>
      </div>
      <div class="chip-row">{notice_types}</div>
      <div class="summary-grid">
        <details class="summary-box" open>
          <summary>项目内容摘要</summary>
          <p>{content_source}<span class="summary-body">{_escape(content_summary)}</span></p>
        </details>
        {_render_qualification_panel(item, compact=compact)}
      </div>
      {_render_ai_panel(ai_result)}
      <div class="project-actions">
        {_render_link_button(rep)}
        <div class="action-note">原文链接用于人工复核。展示层已按项目聚合，不改变底层公告级去重。</div>
      </div>
    </article>
    """


def _render_link_button(notice: Notice) -> str:
    link_url = notice.employee_readable_url or notice.original_url or notice.raw_api_url or ""
    if not link_url:
        return '<span class="action-note">未提供原文链接</span>'
    return f'<a class="link-button" href="{_escape_attr(link_url)}" target="_blank" rel="noreferrer">打开原文链接</a>'


def _fact(label: str, value: str) -> str:
    return f'<div class="fact"><strong>{_escape(label)}</strong><span>{_escape(value)}</span></div>'


def _format_amount_display(notice: Notice, *, field_name: str) -> str:
    if field_name == "budget_amount":
        context = build_amount_context_from_notice(
            notice.budget_amount,
            unit=notice.budget_amount_unit,
            unit_source=notice.budget_amount_unit_source,
            raw_text_snippet=notice.budget_amount_raw_text_snippet,
        )
    else:
        context = build_amount_context_from_notice(
            notice.ceiling_price,
            unit=notice.ceiling_price_unit,
            unit_source=notice.ceiling_price_unit_source,
            raw_text_snippet=notice.ceiling_price_raw_text_snippet,
        )
    return format_amount_with_context(
        context.raw_value,
        unit=context.unit,
        missing_text=MISSING_TEXT,
        unit_unconfirmed_text=UNIT_UNCONFIRMED_TEXT,
    )


def _render_chip_row(values: list[str], *, empty_label: str) -> str:
    items = values or [empty_label]
    return "".join(f'<span class="chip">{_escape(item)}</span>' for item in items)


def _render_summary_source(label: str, source_label: str | None) -> str:
    if not source_label:
        return ""
    return f'<span class="summary-source">{_escape(label)}：{_escape(source_label)}</span><br>'


def _render_qualification_panel(item: ProjectReportItem, *, compact: bool) -> str:
    qualification_summary = item.qualification_summary
    source = _render_summary_source("资质要求摘要来源", item.qualification_summary_source_label)
    if _is_missing_summary(qualification_summary):
        return """
        <section class="qualification-panel">
          <h5>资质要求摘要</h5>
          <p>未提取到</p>
          <div class="qualification-missing">可能原因：资质要求可能在招标文件 / PDF / 附件中，当前本地报告暂未解析附件。</div>
        </section>
        """

    preview_limit = 260 if compact else 360
    full_text = " ".join(qualification_summary.split())
    should_expand = len(full_text) > preview_limit
    preview_text = _truncate(full_text, preview_limit) if should_expand else full_text
    details_block = ""
    if should_expand:
        details_block = f"""
        <details class="qualification-details">
          <summary>展开完整资质要求</summary>
          <div class="qualification-fulltext">{_escape(full_text)}</div>
        </details>
        """
    return f"""
    <section class="qualification-panel">
      <h5>资质要求摘要</h5>
      <p>{source}<span class="summary-body">{_escape(preview_text)}</span></p>
      {details_block}
    </section>
    """


def _render_ai_panel(ai_result: AIAnalysisResult | None) -> str:
    if ai_result is None or ai_result.skipped:
        return ""
    score_text = str(ai_result.opportunity_score) if ai_result.opportunity_score is not None else MISSING_TEXT
    recommendation_text = _recommendation_label(ai_result.recommendation)
    reasons_text = "；".join(ai_result.reasons) if ai_result.reasons else MISSING_TEXT
    risks_text = "；".join(ai_result.risks) if ai_result.risks else MISSING_TEXT
    follow_up_text = "；".join(ai_result.follow_up_questions) if ai_result.follow_up_questions else MISSING_TEXT
    summary_text = ai_result.summary or MISSING_TEXT
    return f"""
    <section class="ai-panel">
      <h5>AI 辅助研判 Alpha</h5>
      <div class="ai-grid">
        <div class="ai-meta"><strong>评分</strong><span>{_escape(score_text)}</span></div>
        <div class="ai-meta"><strong>建议</strong><span>{_escape(recommendation_text)}</span></div>
      </div>
      <p><strong>摘要：</strong>{_escape(summary_text)}</p>
      <p><strong>跟进理由：</strong>{_escape(reasons_text)}</p>
      <p><strong>风险点：</strong>{_escape(risks_text)}</p>
      <p><strong>建议追问：</strong>{_escape(follow_up_text)}</p>
    </section>
    """


def _recommendation_label(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return MISSING_TEXT
    return AI_RECOMMENDATION_LABELS.get(normalized, normalized)


def _aggregation_key(notice: Notice) -> str:
    if notice.section_id:
        return f"section:{notice.section_id.strip()}"
    project_name = _normalize_text(notice.project_name)
    region = _normalize_text(notice.region)
    if project_name and region:
        return f"project-region:{project_name}|{region}"
    if project_name:
        return f"project:{project_name}"
    if notice.notice_id:
        return f"notice:{notice.notice_id.strip()}"
    return f"fallback:{notice.dedupe_key or notice.title}"


def _normalize_text(value: str) -> str:
    compact = re.sub(r"\s+", "", (value or "").strip().lower())
    return compact


def _tier_rank(lead_tier: str) -> int:
    return {"DIRECT": 3, "WATCHLIST": 2, "EXCLUDE": 1}.get((lead_tier or "").upper(), 0)


def _select_best_summary(notices: Iterable[Notice], field_name: str) -> tuple[str, str | None]:
    best_notice: Notice | None = None
    best_text = ""
    best_score = (-1, -1, -1)
    for notice in notices:
        raw_value = getattr(notice, field_name, "") or ""
        compact = " ".join(raw_value.split())
        if _is_missing_summary(compact):
            continue
        score = (
            len(compact),
            _completeness_score(notice),
            _sortable_datetime(notice.publish_time or notice.notice_publish_time),
        )
        if score > best_score:
            best_notice = notice
            best_text = compact
            best_score = score
    if best_notice is None:
        return "未提取到", None
    return best_text, _notice_type_label(best_notice.notice_type)


def _is_missing_summary(value: str) -> bool:
    compact = " ".join((value or "").split())
    return not compact or compact == "未提取到"


def _completeness_score(notice: Notice) -> int:
    fields = [
        notice.project_name,
        notice.region,
        notice.purchaser_or_tenderer,
        notice.agency,
        notice.publish_time,
        notice.bid_open_or_response_deadline or notice.file_get_deadline,
        notice.budget_amount,
        notice.ceiling_price,
        notice.content_summary,
        notice.qualification_summary,
        notice.employee_readable_url or notice.original_url or notice.raw_api_url,
    ]
    return sum(1 for value in fields if value)


def _sortable_datetime(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f+08:00",
        "%Y-%m-%dT%H:%M:%S+08:00",
    ]
    for fmt in candidates:
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _friendly_time(value: str) -> str:
    raw = (value or "").strip()
    return raw or "未提取到"


def _notice_type_label(value: str) -> str:
    key = (value or "").strip()
    return NOTICE_TYPE_LABELS.get(key, key or "未提取到")


def _tier_color(tier: str) -> str:
    return {
        "DIRECT": "var(--direct)",
        "WATCHLIST": "var(--watch)",
        "EXCLUDE": "var(--exclude)",
    }.get(tier, "var(--muted)")


def _truncate(value: str, limit: int) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results


def _escape(value: str) -> str:
    return html.escape(value or "", quote=False)


def _escape_attr(value: str) -> str:
    return html.escape(value or "", quote=True)
