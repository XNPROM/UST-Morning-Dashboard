from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from analytics.quality import compute_quality_grade, find_blocking_quality_issues
from analytics.summary import chg, latest_fixing_info, rows_by_section
from config.settings import settings
from dates.windows import ReportWindows


SECTION_LABELS = {
    "A. Rates": "A 利率",
    "B. Real & Inflation": "B 实际利率与通胀补偿",
    "C. Treasury Futures": "C 美债期货",
    "D. USD & FX": "D 美元与外汇",
    "E. RMB": "E 人民币",
    "F. Commodities": "F 大宗商品",
}


def html_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if cols:
        df = df[[c for c in cols if c in df.columns]].copy()
    if max_rows:
        df = df.head(max_rows)
    if df.empty or len(df.columns) == 0:
        return "<div class='empty-state'>本部分当前没有可展示的数据。</div>"
    return df.to_html(index=False, escape=True, classes="clean-table", border=0)


def metric_card(title: str, body: str, detail: str = "") -> str:
    detail_html = f"<div class='metric-detail'>{detail}</div>" if detail else ""
    return (
        "<div class='metric-card'>"
        f"<div class='metric-title'>{title}</div>"
        f"<div class='metric-body'>{body}</div>"
        f"{detail_html}"
        "</div>"
    )


def _grade_badge(grade: str) -> str:
    colors = {"A": "#2f6b60", "B": "#a86a2a", "C": "#a94438"}
    color = colors.get(grade, "#6b7280")
    return (
        "<span style='display:inline-block;padding:4px 10px;border-radius:999px;"
        f"background:{color};color:white;font-size:12px;font-weight:700'>{grade}</span>"
    )


def _section_label(section: str) -> str:
    return SECTION_LABELS.get(section, section)


def _quality_banner(summary_main: pd.DataFrame, quality_df: pd.DataFrame) -> str:
    blocking = find_blocking_quality_issues(quality_df)
    if not blocking.empty:
        sample = "；".join(
            f"{row['Asset']}：{row['Issue']}" for _, row in blocking.head(4).iterrows()
        )
        more = "" if len(blocking) <= 4 else f"；其余 {len(blocking) - 4} 项见下方数据检查。"
        return (
            "<div class='status-banner status-banner-danger'>"
            "<div class='status-banner-title'>本批次数据存在关键缺口</div>"
            "<div class='status-banner-body'>"
            "高优先级问题已经出现，页面内容仅适合用于排查数据状态。"
            f"{sample}{more}</div></div>"
        )

    medium = quality_df[quality_df.get("Severity", pd.Series(dtype=str)).eq("MEDIUM")] if not quality_df.empty else pd.DataFrame()
    if not medium.empty:
        sample = "；".join(
            f"{row['Asset']}：{row['Issue']}" for _, row in medium.head(3).iterrows()
        )
        return (
            "<div class='status-banner status-banner-warn'>"
            "<div class='status-banner-title'>本批次含有待继续核对的数据项</div>"
            f"<div class='status-banner-body'>{sample}</div></div>"
        )

    if summary_main.empty:
        return (
            "<div class='status-banner status-banner-warn'>"
            "<div class='status-banner-title'>主观察区间暂无可用数据</div>"
            "<div class='status-banner-body'>图表和摘要会保留页面结构，但本批次不适合用于晨会引用。</div>"
            "</div>"
        )

    return ""


def _quality_summary_text(summary_main: pd.DataFrame, quality_df: pd.DataFrame) -> str:
    blocking = find_blocking_quality_issues(quality_df)
    if not blocking.empty:
        return f"共有 {len(blocking)} 项高优先级问题，本页仅保留排查信息。"
    if summary_main.empty:
        return "主观察区间为空，页面结构保留用于检查运行状态。"
    medium_count = int(quality_df["Severity"].eq("MEDIUM").sum()) if not quality_df.empty and "Severity" in quality_df.columns else 0
    if medium_count:
        return f"当前没有高优先级问题，另有 {medium_count} 项待继续核对。"
    return "当前批次没有发现高优先级缺口。"


def _notes_section(morning_notes: list[str]) -> str:
    if not morning_notes:
        return "<div class='empty-state'>当前批次没有生成晨会摘要，通常意味着主观察区间数据不足。</div>"
    return "<ul class='notes-list'>" + "".join(f"<li>{note}</li>" for note in morning_notes) + "</ul>"


def _ai_section(interpretation: dict[str, str] | None) -> str:
    if not interpretation:
        return """
        <div class="section-shell section-ai">
            <div class="section-head">
                <div class="section-kicker">Research Reading</div>
                <h2>四维分析</h2>
            </div>
            <div class="ai-empty">
                当前没有载入分析文本。只有在主观察区间数据完整且未出现高优先级问题时，才建议生成这一部分。
            </div>
        </div>
        """

    dims = [
        ("attribution", "变化归因"),
        ("key_levels", "关键价位与观察信号"),
        ("historical_analogy", "近阶段历史参照"),
        ("outlook", "短线观察"),
    ]

    cards = []
    for key, title in dims:
        content = interpretation.get(key, "当日数据不足，当前段落暂无法写入。")
        cards.append(
            "<article class='analysis-card'>"
            f"<div class='analysis-title'>{title}</div>"
            f"<div class='analysis-body'>{content}</div>"
            "</article>"
        )

    return f"""
    <div class="section-shell section-ai">
        <div class="section-head">
            <div class="section-kicker">Research Reading</div>
            <h2>四维分析</h2>
        </div>
        <div class="analysis-grid">{"".join(cards)}</div>
        <div class="section-footnote">以下文字仅在数据完整时展示，用于辅助阅读摘要与图表。</div>
    </div>
    """


def _render_figures(figs: list) -> str:
    blocks = []
    for i, fig in enumerate(figs):
        figure_html = fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)
        blocks.append(f"<div class='chart-card'>{figure_html}</div>")
    if not blocks:
        return "<div class='empty-state'>当前批次没有生成图表。</div>"
    return "<div class='charts-grid'>" + "".join(blocks) + "</div>"


def generate_html_report(
    summary_main: pd.DataFrame,
    summary_24h: pd.DataFrame,
    summary_ny: pd.DataFrame,
    morning_notes: list[str],
    quality_df: pd.DataFrame,
    figs: list,
    daily_panel: pd.DataFrame,
    all_logs: pd.DataFrame,
    windows: ReportWindows,
    trading_hours: pd.DataFrame,
    event_calendar: pd.DataFrame,
    interpretation: dict[str, str] | None = None,
    timestamp: str | None = None,
) -> tuple[str, str, str]:
    timestamp = timestamp or datetime.now(settings.REPORT_TZ).strftime("%Y%m%d_%H%M")
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    html_path = os.path.join(settings.OUTPUT_DIR, f"morning_dashboard_{timestamp}.html")
    csv_path = os.path.join(settings.OUTPUT_DIR, f"summary_{timestamp}.csv")
    log_path = os.path.join(settings.OUTPUT_DIR, f"ric_log_{timestamp}.csv")

    summary_main.to_csv(csv_path, index=False, encoding="utf-8-sig")
    all_logs.to_csv(log_path, index=False, encoding="utf-8-sig")

    summary_cols = ["Group", "Asset", "Level", "Change Text", "% Change Text", "High", "Low", "Obs"]

    rates_tbl = html_table(rows_by_section(summary_main, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_tbl = html_table(rows_by_section(summary_main, ["D. USD & FX", "E. RMB"]), summary_cols)
    fut_cmd_tbl = html_table(rows_by_section(summary_main, ["C. Treasury Futures", "F. Commodities"]), summary_cols)

    rates_24h_tbl = html_table(rows_by_section(summary_24h, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_24h_tbl = html_table(rows_by_section(summary_24h, ["D. USD & FX", "E. RMB"]), summary_cols)

    rates_ny_tbl = html_table(rows_by_section(summary_ny, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_ny_tbl = html_table(rows_by_section(summary_ny, ["D. USD & FX", "E. RMB"]), summary_cols)
    fut_cmd_ny_tbl = html_table(rows_by_section(summary_ny, ["C. Treasury Futures", "F. Commodities"]), summary_cols)

    fix = latest_fixing_info(daily_panel, windows.target_fixing_date)
    fixing_value = "当前不可用"
    fixing_detail = ""
    if fix.get("status") in ("ok", "stale"):
        fixing_value = f"{fix['last']:.4f}"
        chg_txt = "" if pd.isna(fix.get("chg_pips")) else f"{fix['chg_pips']:+.1f} pips"
        fixing_detail = (
            f"{chg_txt}；最新发布日期 {fix['last_date']}；"
            f"目标观察日 {fix['target_date']}"
        )

    grades = compute_quality_grade(quality_df)
    grade_badges = " ".join(
        f"{_section_label(sec)} {_grade_badge(grade)}" for sec, grade in sorted(grades.items())
    )
    status_banner_html = _quality_banner(summary_main, quality_df)
    status_summary_text = _quality_summary_text(summary_main, quality_df)

    cards_html = "".join(
        [
            metric_card(
                "观察时点",
                windows.asof_dt.strftime("%Y-%m-%d %H:%M"),
                "Asia/Shanghai",
            ),
            metric_card(
                "主观察区间",
                f"{windows.main_start.strftime('%m-%d %H:%M')} 至 {windows.main_end.strftime('%m-%d %H:%M')}",
                "上一中国收盘后至早会",
            ),
            metric_card("十年期美债", chg(summary_main, "UST 10Y")),
            metric_card("美元指数", chg(summary_main, "DXY")),
            metric_card("人民币中间价", fixing_value, fixing_detail),
        ]
    )

    notes_html = _notes_section(morning_notes)
    figs_block = _render_figures(figs)

    quality_html = html_table(quality_df)
    trading_html = html_table(trading_hours)
    events_html = html_table(event_calendar)
    log_html = html_table(
        all_logs[["freq", "section", "group", "name", "ric", "field", "rows", "status", "error"]]
    )

    ai_section = _ai_section(interpretation)

    main_window_desc = f"上一中国交易日 {windows.main_start.strftime('%H:%M')} 至今日 {windows.main_end.strftime('%H:%M')}"
    ny_window_desc = f"{windows.ny_start.strftime('%m-%d %H:%M')} 至 {windows.ny_end.strftime('%m-%d %H:%M')} Asia/Shanghai"

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>美债与美元市场晨间报告 {windows.asof_dt.strftime('%Y-%m-%d')}</title>
<style>
:root {{
    --page-bg: #f5f0e5;
    --page-bg-2: #fcfaf4;
    --paper: #fffdf8;
    --paper-2: #f8f3e8;
    --ink: #182530;
    --muted: #6f7880;
    --line: #ded4c4;
    --accent: #24564f;
    --accent-2: #b16d2e;
    --danger: #8d3f33;
    --shadow: 0 22px 50px rgba(24, 37, 48, 0.12);
}}
* {{
    box-sizing: border-box;
}}
body {{
    margin: 0;
    color: var(--ink);
    font-family: "Bahnschrift", "Aptos", "PingFang SC", "Microsoft YaHei", sans-serif;
    background:
        radial-gradient(circle at top left, rgba(36, 86, 79, 0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(177, 109, 46, 0.10), transparent 22%),
        linear-gradient(180deg, var(--page-bg) 0%, var(--page-bg-2) 48%, #f9f8f3 100%);
}}
.page {{
    max-width: 1440px;
    margin: 0 auto;
    padding: 28px 22px 44px 22px;
}}
.hero {{
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.9fr);
    gap: 20px;
    margin-bottom: 20px;
}}
.hero-main,
.hero-side {{
    background: linear-gradient(160deg, rgba(255,255,255,0.96), rgba(250,245,235,0.95));
    border: 1px solid rgba(222, 212, 196, 0.9);
    border-radius: 28px;
    box-shadow: var(--shadow);
}}
.hero-main {{
    padding: 28px 30px 26px 30px;
    position: relative;
    overflow: hidden;
}}
.hero-main::after {{
    content: "";
    position: absolute;
    inset: 0;
    background:
        linear-gradient(115deg, transparent 0%, transparent 58%, rgba(36, 86, 79, 0.05) 100%);
    pointer-events: none;
}}
.hero-kicker {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 10px;
}}
.hero-main h1 {{
    margin: 0;
    font-size: 40px;
    line-height: 1.15;
    font-weight: 700;
    font-family: "Source Han Serif SC", "STSong", "SimSun", Georgia, serif;
}}
.hero-lead {{
    margin: 14px 0 18px 0;
    max-width: 760px;
    font-size: 15px;
    line-height: 1.75;
    color: #33424f;
}}
.hero-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
    color: var(--muted);
}}
.hero-chip {{
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(36, 86, 79, 0.08);
    border: 1px solid rgba(36, 86, 79, 0.12);
}}
.hero-side {{
    padding: 24px 24px 22px 24px;
}}
.status-label {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent-2);
    margin-bottom: 8px;
}}
.status-summary {{
    font-size: 16px;
    line-height: 1.7;
    color: #283540;
    margin-bottom: 18px;
}}
.status-grades {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    font-size: 13px;
    line-height: 1.8;
}}
.status-banner {{
    border-radius: 22px;
    padding: 16px 20px;
    margin: 0 0 20px 0;
    box-shadow: 0 14px 30px rgba(24, 37, 48, 0.08);
}}
.status-banner-danger {{
    background: linear-gradient(135deg, rgba(141, 63, 51, 0.13), rgba(177, 109, 46, 0.08));
    border: 1px solid rgba(141, 63, 51, 0.20);
}}
.status-banner-warn {{
    background: linear-gradient(135deg, rgba(177, 109, 46, 0.12), rgba(255, 255, 255, 0.95));
    border: 1px solid rgba(177, 109, 46, 0.18);
}}
.status-banner-title {{
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 6px;
}}
.status-banner-body {{
    font-size: 14px;
    line-height: 1.75;
    color: #34424e;
}}
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 20px;
}}
.metric-card,
.section-shell,
.collapsible {{
    background: rgba(255, 253, 248, 0.95);
    border: 1px solid rgba(222, 212, 196, 0.88);
    border-radius: 24px;
    box-shadow: 0 18px 36px rgba(24, 37, 48, 0.08);
}}
.metric-card {{
    padding: 16px 18px 18px 18px;
}}
.metric-title {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 10px;
}}
.metric-body {{
    font-size: 23px;
    line-height: 1.3;
    font-weight: 700;
    color: #1c2a34;
}}
.metric-detail {{
    margin-top: 10px;
    font-size: 12px;
    line-height: 1.65;
    color: var(--muted);
}}
.section-shell {{
    padding: 20px 22px 22px 22px;
    margin-bottom: 18px;
}}
.section-head {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 16px;
}}
.section-kicker {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.16em;
    color: var(--accent);
    text-transform: uppercase;
}}
.section-head h2 {{
    margin: 4px 0 0 0;
    font-size: 26px;
    line-height: 1.2;
    font-family: "Source Han Serif SC", "STSong", "SimSun", Georgia, serif;
}}
.section-footnote {{
    margin-top: 14px;
    font-size: 12px;
    color: var(--muted);
}}
.notes-list {{
    margin: 0;
    padding-left: 20px;
    font-size: 15px;
    line-height: 1.9;
}}
.notes-list li + li {{
    margin-top: 8px;
}}
.analysis-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}}
.analysis-card {{
    min-height: 190px;
    padding: 18px;
    border-radius: 20px;
    background:
        linear-gradient(180deg, rgba(248, 243, 232, 0.96), rgba(255, 253, 248, 0.98));
    border: 1px solid rgba(222, 212, 196, 0.86);
}}
.analysis-title {{
    font-size: 16px;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 10px;
}}
.analysis-body {{
    font-size: 14px;
    line-height: 1.88;
    color: #24323e;
}}
.ai-empty,
.empty-state {{
    padding: 18px;
    border-radius: 18px;
    background: rgba(248, 243, 232, 0.92);
    border: 1px dashed rgba(177, 109, 46, 0.42);
    color: #5d6770;
    font-size: 14px;
    line-height: 1.75;
}}
.grade-strip {{
    padding: 14px 16px;
    margin-bottom: 14px;
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(36, 86, 79, 0.07), rgba(255, 255, 255, 0.78));
    border: 1px solid rgba(36, 86, 79, 0.12);
    font-size: 13px;
    line-height: 2;
}}
.table-wrap {{
    overflow-x: auto;
}}
.clean-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
.clean-table th {{
    text-align: left;
    padding: 12px 12px;
    background: rgba(36, 86, 79, 0.08);
    color: #22313d;
    border-bottom: 1px solid rgba(222, 212, 196, 0.95);
    white-space: nowrap;
}}
.clean-table td {{
    padding: 11px 12px;
    border-bottom: 1px solid rgba(232, 224, 212, 0.96);
    white-space: nowrap;
}}
.clean-table tbody tr:nth-child(even) {{
    background: rgba(248, 243, 232, 0.58);
}}
.clean-table tbody tr:hover {{
    background: rgba(36, 86, 79, 0.05);
}}
.collapsible {{
    margin-bottom: 18px;
    overflow: hidden;
}}
.collapsible-header {{
    padding: 18px 22px;
    cursor: pointer;
    font-size: 18px;
    font-weight: 700;
    color: #1f3a39;
    background: linear-gradient(135deg, rgba(36, 86, 79, 0.07), rgba(255, 255, 255, 0.9));
}}
.collapsible-header.active {{
    border-bottom: 1px solid rgba(222, 212, 196, 0.9);
}}
.collapsible-body {{
    display: none;
    padding: 0 22px 22px 22px;
}}
.collapsible-header.active + .collapsible-body {{
    display: block;
}}
.charts-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
}}
.chart-card {{
    padding: 12px;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(248, 243, 232, 0.92), rgba(255, 253, 248, 0.98));
    border: 1px solid rgba(222, 212, 196, 0.82);
}}
.chart-card .plotly-graph-div {{
    border-radius: 16px;
}}
details {{
    margin-top: 14px;
}}
summary {{
    cursor: pointer;
    font-weight: 700;
    color: var(--accent);
}}
.muted {{
    color: var(--muted);
    font-size: 12px;
}}
code {{
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 0.95em;
}}
@media (max-width: 1180px) {{
    .hero {{
        grid-template-columns: 1fr;
    }}
    .metrics-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .analysis-grid,
    .charts-grid {{
        grid-template-columns: 1fr;
    }}
}}
@media (max-width: 760px) {{
    .page {{
        padding: 18px 12px 28px 12px;
    }}
    .hero-main h1 {{
        font-size: 32px;
    }}
    .metrics-grid {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>
<body>
<div class="page">
    <div class="hero">
        <div class="hero-main">
            <div class="hero-kicker">Shenzhen Morning Brief</div>
            <h1>美债与美元市场晨间报告</h1>
            <div class="hero-lead">
                围绕隔夜利率、美元、人民币与大宗商品的晨会观察。主观察区间覆盖上一中国收盘后至今日早会前，
                页面同时保留纽约时段与滚动二十四小时的补充视角。
            </div>
            <div class="hero-meta">
                <div class="hero-chip">主观察区间：{main_window_desc}</div>
                <div class="hero-chip">纽约时段：{ny_window_desc}</div>
                <div class="hero-chip">页面生成时间：{datetime.now(settings.REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
        </div>
        <div class="hero-side">
            <div class="status-label">Data Status</div>
            <div class="status-summary">{status_summary_text}</div>
            <div class="status-grades">{grade_badges}</div>
        </div>
    </div>

    {status_banner_html}

    <div class="metrics-grid">{cards_html}</div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Morning Brief</div>
            <h2>晨会摘要</h2>
        </div>
        {notes_html}
    </div>

    {ai_section}

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Primary Tables</div>
            <h2>1. 利率与通胀补偿</h2>
        </div>
        <div class="grade-strip">数据完整性与一致性：{grade_badges}</div>
        <div class="table-wrap">{rates_tbl}</div>
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Primary Tables</div>
            <h2>2. 美元、外汇与人民币</h2>
        </div>
        <div class="table-wrap">{usd_rmb_tbl}</div>
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Primary Tables</div>
            <h2>3. 美债期货与大宗商品</h2>
        </div>
        <div class="table-wrap">{fut_cmd_tbl}</div>
    </div>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">滚动二十四小时</div>
        <div class="collapsible-body">
            <div class="section-head">
                <div class="section-kicker">Rolling Window</div>
                <h2>补充区间观察</h2>
            </div>
            <h3>利率与通胀补偿</h3>
            <div class="table-wrap">{rates_24h_tbl}</div>
            <h3>美元、外汇与人民币</h3>
            <div class="table-wrap">{usd_rmb_24h_tbl}</div>
        </div>
    </div>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">纽约时段</div>
        <div class="collapsible-body">
            <div class="section-head">
                <div class="section-kicker">New York Session</div>
                <h2>纽约交易时段观察</h2>
            </div>
            <h3>利率与通胀补偿</h3>
            <div class="table-wrap">{rates_ny_tbl}</div>
            <h3>美元、外汇与人民币</h3>
            <div class="table-wrap">{usd_rmb_ny_tbl}</div>
            <h3>美债期货与大宗商品</h3>
            <div class="table-wrap">{fut_cmd_ny_tbl}</div>
        </div>
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Charts</div>
            <h2>4. 图表观察</h2>
        </div>
        {figs_block}
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Reference</div>
            <h2>5. 主要交易时段</h2>
        </div>
        <div class="table-wrap">{trading_html}</div>
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Calendar</div>
            <h2>6. 美国重要经济数据日程</h2>
        </div>
        <div class="table-wrap">{events_html}</div>
        <div class="section-footnote">
            维护方式：FOMC、CPI、PCE、NFP、GDP、Retail Sales 等高重要性日期可填写在
            <code>config/settings.py</code> 的 <code>MANUAL_US_EVENTS</code>；周度初请仍按周四 08:30 ET 自动生成。
        </div>
    </div>

    <div class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Diagnostics</div>
            <h2>7. 数据检查</h2>
        </div>
        <div class="table-wrap">{quality_html}</div>
        <details>
            <summary>查看 RIC 拉取日志</summary>
            <div class="table-wrap">{log_html}</div>
        </details>
    </div>
</div>
<script>
document.querySelectorAll('.collapsible-header').forEach(h => {{
    if (!h.classList.contains('bound')) {{
        h.classList.add('bound');
    }}
}});
</script>
</body>
</html>
"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html_path, csv_path, log_path
