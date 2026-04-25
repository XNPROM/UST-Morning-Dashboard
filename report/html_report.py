from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from config.settings import settings
from analytics.summary import chg, rows_by_section, latest_fixing_info
from analytics.quality import compute_quality_grade
from dates.windows import ReportWindows


def html_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if cols:
        df = df[[c for c in cols if c in df.columns]].copy()
    if max_rows:
        df = df.head(max_rows)
    return df.to_html(index=False, escape=True, classes="clean-table", border=0)


def metric_card(title, body):
    return f"<div class='card'><div class='card-title'>{title}</div><div class='card-body'>{body}</div></div>"


def _grade_badge(grade: str) -> str:
    colors = {"A": "#22c55e", "B": "#f59e0b", "C": "#ef4444"}
    color = colors.get(grade, "#9ca3af")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:8px;background:{color};color:white;font-size:12px;font-weight:700'>{grade}</span>"


def _ai_section(interpretation: dict[str, str] | None) -> str:
    if not interpretation:
        return """
        <div class="section">
            <h2>AI 深度解读</h2>
            <div class="ai-pending">
                <p>AI 解读尚未生成。运行后请在 Claude Code 中读取上下文文件并生成解读，然后重新运行看板。</p>
            </div>
        </div>
        """

    dims = [
        ("attribution", "驱动因素归因"),
        ("key_levels", "关键点位与信号"),
        ("historical_analogy", "历史情景类比"),
        ("outlook", "前瞻观点"),
    ]

    cards = []
    for key, title in dims:
        content = interpretation.get(key, "分析数据不足，无法生成解读。")
        cards.append(
            f"<div class='ai-card'><div class='ai-card-title'>{title}</div>"
            f"<div class='ai-card-body'>{content}</div></div>"
        )

    return f"""
    <div class="section">
        <h2>AI 深度解读</h2>
        <div class="ai-grid">{"".join(cards)}</div>
        <p class="muted" style="margin-top:12px">AI 辅助生成，仅供参考</p>
    </div>
    """


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

    # Main window tables
    rates_tbl = html_table(rows_by_section(summary_main, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_tbl = html_table(rows_by_section(summary_main, ["D. USD & FX", "E. RMB"]), summary_cols)
    fut_cmd_tbl = html_table(rows_by_section(summary_main, ["C. Treasury Futures", "F. Commodities"]), summary_cols)

    # Rolling 24h tables
    rates_24h_tbl = html_table(rows_by_section(summary_24h, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_24h_tbl = html_table(rows_by_section(summary_24h, ["D. USD & FX", "E. RMB"]), summary_cols)

    # NY session tables
    rates_ny_tbl = html_table(rows_by_section(summary_ny, ["A. Rates", "B. Real & Inflation"]), summary_cols)
    usd_rmb_ny_tbl = html_table(rows_by_section(summary_ny, ["D. USD & FX", "E. RMB"]), summary_cols)
    fut_cmd_ny_tbl = html_table(rows_by_section(summary_ny, ["C. Treasury Futures", "F. Commodities"]), summary_cols)

    # Fixing info
    fix = latest_fixing_info(daily_panel, windows.target_fixing_date)
    fixing_card_html = "不可用"
    if fix.get("status") in ("ok", "stale"):
        chg_txt = "" if pd.isna(fix.get("chg_pips")) else f"{fix['chg_pips']:+.1f} pips"
        fixing_card_html = f"{fix['last']:.4f}｜{chg_txt}<br><span class='muted'>latest {fix['last_date']} / target {fix['target_date']}</span>"

    # Quality grades (sorted by section name)
    grades = compute_quality_grade(quality_df)
    grade_badges = " ".join([
        f"{sec}: {_grade_badge(g)}" for sec, g in sorted(grades.items())
    ])

    # Cards
    cards_html = "".join([
        metric_card("As-of", f"{windows.asof_dt.strftime('%Y-%m-%d %H:%M')}<br><span class='muted'>Asia/Shanghai</span>"),
        metric_card("主窗口", f"{windows.main_start.strftime('%m-%d %H:%M')} → {windows.main_end.strftime('%m-%d %H:%M')}<br><span class='muted'>上一中国收盘后至早会</span>"),
        metric_card("10Y UST", chg(summary_main, "UST 10Y")),
        metric_card("DXY", chg(summary_main, "DXY")),
        metric_card("USD/CNY fixing", fixing_card_html),
    ])

    notes_html = "<ul>" + "".join([f"<li>{n}</li>" for n in morning_notes]) + "</ul>"

    fig_html = []
    for i, fig in enumerate(figs):
        fig_html.append(fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False))
    figs_block = "\n".join(fig_html)

    quality_html = html_table(quality_df)
    trading_html = html_table(trading_hours)
    events_html = html_table(event_calendar)
    log_html = html_table(all_logs[["freq", "section", "group", "name", "ric", "field", "rows", "status", "error"]])

    ai_section = _ai_section(interpretation)

    # Window description for subtitle
    main_window_desc = f"上一中国交易日{windows.main_start.strftime('%H:%M')} → 今日{windows.main_end.strftime('%H:%M')}"
    ny_window_desc = f"{windows.ny_start.strftime('%m-%d %H:%M')} → {windows.ny_end.strftime('%m-%d %H:%M')} Asia/Shanghai"

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>深圳早会看板 {windows.asof_dt.strftime('%Y-%m-%d')}</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
    background: #f6f7fb;
    color: #111827;
    margin: 0;
}}
.container {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px;
}}
.header {{
    background: linear-gradient(135deg, #111827, #334155);
    color: white;
    padding: 28px 32px;
    border-radius: 22px;
    box-shadow: 0 12px 30px rgba(15,23,42,.18);
}}
.header h1 {{
    margin: 0 0 8px 0;
    font-size: 30px;
}}
.subtitle {{
    color: #d1d5db;
    font-size: 14px;
    line-height: 1.6;
}}
.cards {{
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin: 18px 0 22px 0;
}}
.card {{
    background: white;
    border-radius: 18px;
    padding: 16px;
    box-shadow: 0 8px 20px rgba(15,23,42,.08);
}}
.card-title {{
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 8px;
}}
.card-body {{
    font-size: 18px;
    font-weight: 700;
    line-height: 1.35;
}}
.section {{
    background: white;
    border-radius: 20px;
    padding: 18px 20px;
    margin: 18px 0;
    box-shadow: 0 8px 20px rgba(15,23,42,.06);
}}
.section h2 {{
    font-size: 20px;
    margin: 0 0 12px 0;
    border-left: 5px solid #2563eb;
    padding-left: 10px;
}}
.section h3 {{
    font-size: 16px;
    margin: 16px 0 8px 0;
    color: #374151;
}}
.clean-table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
}}
.clean-table th {{
    text-align: left;
    background: #f3f4f6;
    color: #374151;
    padding: 9px 10px;
    border-bottom: 1px solid #e5e7eb;
    white-space: nowrap;
}}
.clean-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid #eef2f7;
    white-space: nowrap;
}}
.clean-table tr:hover {{
    background: #f9fafb;
}}
.muted {{
    color: #6b7280;
    font-size: 12px;
    font-weight: 400;
}}
.ai-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}}
.ai-card {{
    background: linear-gradient(135deg, #fefce8, #fef9c3);
    border: 1px solid #fde68a;
    border-radius: 16px;
    padding: 16px;
}}
.ai-card-title {{
    font-size: 15px;
    font-weight: 700;
    color: #92400e;
    margin-bottom: 8px;
}}
.ai-card-body {{
    font-size: 13px;
    line-height: 1.75;
    color: #1c1917;
}}
.ai-pending {{
    background: #f3f4f6;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    color: #6b7280;
    font-size: 14px;
}}
.grade-bar {{
    background: #f3f4f6;
    border-radius: 12px;
    padding: 10px 16px;
    margin-bottom: 12px;
    font-size: 13px;
    line-height: 2;
}}
details {{
    margin-top: 10px;
}}
summary {{
    cursor: pointer;
    color: #2563eb;
    font-weight: 600;
}}
ul {{
    margin-top: 8px;
    line-height: 1.75;
}}
.collapsible {{
    background: white;
    border-radius: 20px;
    margin: 18px 0;
    box-shadow: 0 8px 20px rgba(15,23,42,.06);
    overflow: hidden;
}}
.collapsible-header {{
    padding: 16px 20px;
    cursor: pointer;
    font-size: 18px;
    font-weight: 600;
    border-left: 5px solid #6366f1;
    padding-left: 10px;
    user-select: none;
}}
.collapsible-header:hover {{
    background: #f9fafb;
}}
.collapsible-body {{
    padding: 0 20px 18px 20px;
    display: none;
}}
.collapsible-header.active + .collapsible-body {{
    display: block;
}}
@media (max-width: 1000px) {{
    .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .ai-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>LSEG 美债收益率 & 美元晨间看板</h1>
        <div class="subtitle">
            深圳早会版 v6｜主窗口：{main_window_desc}｜
            纽约窗口：{ny_window_desc}｜
            生成时间：{datetime.now(settings.REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    <div class="cards">{cards_html}</div>

    <div class="section">
        <h2>一屏结论</h2>
        {notes_html}
    </div>

    {ai_section}

    <div class="section">
        <div class="grade-bar">数据质量评级：{grade_badges}</div>
        <h2>1. 利率、曲线、真实利率、BEI</h2>
        {rates_tbl}
    </div>

    <div class="section">
        <h2>2. 美元、外汇、人民币</h2>
        {usd_rmb_tbl}
    </div>

    <div class="section">
        <h2>3. 美债期货、油铜金</h2>
        {fut_cmd_tbl}
    </div>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">▸ 滚动24小时概览</div>
        <div class="collapsible-body">
            <h3>利率、曲线、真实利率、BEI（24h）</h3>
            {rates_24h_tbl}
            <h3>美元、外汇、人民币（24h）</h3>
            {usd_rmb_24h_tbl}
        </div>
    </div>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">▸ 纽约交易时段概览</div>
        <div class="collapsible-body">
            <h3>利率、曲线、真实利率、BEI（NY）</h3>
            {rates_ny_tbl}
            <h3>美元、外汇、人民币（NY）</h3>
            {usd_rmb_ny_tbl}
            <h3>美债期货、油铜金（NY）</h3>
            {fut_cmd_ny_tbl}
        </div>
    </div>

    <div class="section">
        <h2>4. 图表</h2>
        {figs_block}
    </div>

    <div class="section">
        <h2>5. 交易时段对照</h2>
        {trading_html}
    </div>

    <div class="section">
        <h2>6. 美国重要数据日历</h2>
        {events_html}
        <p class="muted">说明：FOMC、CPI、PCE、NFP、GDP、Retail Sales 等高重要性日期建议填入 config/settings.py 的 MANUAL_US_EVENTS；周度初请按周四 08:30 ET 自动生成。</p>
    </div>

    <div class="section">
        <h2>7. 数据质量 / 口径检查</h2>
        {quality_html}
        <details>
            <summary>展开 RIC 拉取日志</summary>
            {log_html}
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
