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


CORE_PROVENANCE_ASSETS = [
    "UST 2Y",
    "UST 10Y",
    "UST 30Y",
    "DXY",
    "USDCNY",
    "USDCNH",
    "Brent crude",
    "Gold",
]


def html_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if cols:
        df = df[[c for c in cols if c in df.columns]].copy()
    if max_rows:
        df = df.head(max_rows)
    if df.empty or len(df.columns) == 0:
        return "<div class='empty-state'>本部分当前没有可展示的数据。</div>"
    return df.to_html(index=False, escape=True, classes="clean-table", border=0)


def metric_card(title: str, body: str, detail: str = "", tone: str = "default") -> str:
    detail_html = f"<div class='metric-detail'>{detail}</div>" if detail else ""
    return (
        f"<div class='metric-card metric-card-{tone}'>"
        f"<div class='metric-title'>{title}</div>"
        f"<div class='metric-body'>{body}</div>"
        f"{detail_html}"
        "</div>"
    )


def _grade_badge(grade: str) -> str:
    colors = {"A": "#0f766e", "B": "#b45309", "C": "#b91c1c"}
    color = colors.get(grade, "#64748b")
    return (
        "<span class='grade-badge' "
        f"style='background:{color};border-color:{color};'>{grade}</span>"
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
            "当前页面保留用于排查与核对，暂不适合作为晨会正式引用材料。"
            f"{sample}{more}</div></div>"
        )

    medium = (
        quality_df[quality_df.get("Severity", pd.Series(dtype=str)).eq("MEDIUM")]
        if not quality_df.empty
        else pd.DataFrame()
    )
    if not medium.empty:
        sample = "；".join(
            f"{row['Asset']}：{row['Issue']}" for _, row in medium.head(3).iterrows()
        )
        return (
            "<div class='status-banner status-banner-warn'>"
            "<div class='status-banner-title'>本批次仍有待继续核对的数据项</div>"
            f"<div class='status-banner-body'>{sample}</div></div>"
        )

    if summary_main.empty:
        return (
            "<div class='status-banner status-banner-warn'>"
            "<div class='status-banner-title'>主观察区间暂无可用数据</div>"
            "<div class='status-banner-body'>"
            "页面结构和诊断区会保留，但当前批次不适合作为晨会引用版本。"
            "</div></div>"
        )

    return ""


def _quality_summary_text(summary_main: pd.DataFrame, quality_df: pd.DataFrame) -> str:
    blocking = find_blocking_quality_issues(quality_df)
    if not blocking.empty:
        return f"共识别出 {len(blocking)} 项高优先级问题，本页用于排查与核对。"
    if summary_main.empty:
        return "主观察区间为空，当前页面仅用于确认运行状态和数据可得性。"
    medium_count = (
        int(quality_df["Severity"].eq("MEDIUM").sum())
        if not quality_df.empty and "Severity" in quality_df.columns
        else 0
    )
    if medium_count:
        return f"当前没有高优先级缺口，另有 {medium_count} 项待继续核对。"
    return "当前批次通过主要完整性检查，可进入摘要阅读与图表核对。"


def _notes_section(morning_notes: list[str]) -> str:
    if not morning_notes:
        return "<div class='empty-state'>当前批次没有生成晨会摘要，通常意味着主观察区间数据不足。</div>"
    return "<ul class='notes-list'>" + "".join(f"<li>{note}</li>" for note in morning_notes) + "</ul>"


def _primary_message(morning_notes: list[str], status_summary_text: str) -> str:
    if morning_notes:
        return morning_notes[0]
    return status_summary_text


def _ai_section(interpretation: dict[str, str] | None) -> str:
    if not interpretation:
        return """
        <section class="section-shell section-ai" id="analysis">
            <div class="section-head">
                <div class="section-kicker">Research Reading</div>
                <h2>四维分析</h2>
            </div>
            <div class="ai-empty">
                当前没有载入分析文本。只有在主观察区间数据完整且没有高优先级问题时，才建议保留这一部分。
            </div>
        </section>
        """

    dims = [
        ("attribution", "变化归因"),
        ("key_levels", "关键价位与观察信号"),
        ("historical_analogy", "近阶段历史参照"),
        ("outlook", "短线观察"),
    ]

    cards = []
    for key, title in dims:
        content = interpretation.get(key, "当日数据不足，当前段落暂时无法写入。")
        cards.append(
            "<article class='analysis-card'>"
            f"<div class='analysis-title'>{title}</div>"
            f"<div class='analysis-body'>{content}</div>"
            "</article>"
        )

    return f"""
    <section class="section-shell section-ai" id="analysis">
        <div class="section-head">
            <div class="section-kicker">Research Reading</div>
            <h2>四维分析</h2>
        </div>
        <div class="analysis-grid">{"".join(cards)}</div>
        <div class="section-footnote">本区块只在数据完整时显示，用于辅助阅读摘要和图表，不替代表格原始数值。</div>
    </section>
    """


def _render_figures(figs: list) -> str:
    blocks = []
    for i, fig in enumerate(figs):
        figure_html = fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)
        blocks.append(f"<div class='chart-card'>{figure_html}</div>")
    if not blocks:
        return "<div class='empty-state'>当前批次没有生成图表。</div>"
    return "<div class='charts-grid'>" + "".join(blocks) + "</div>"


def _main_quote_time(summary_main: pd.DataFrame, windows: ReportWindows) -> str:
    if summary_main.empty or "Last Time" not in summary_main.columns:
        return windows.main_end.strftime("%Y-%m-%d %H:%M")
    times = summary_main["Last Time"].dropna().astype(str)
    if times.empty:
        return windows.main_end.strftime("%Y-%m-%d %H:%M")
    return max(times)


def _select_log_row(all_logs: pd.DataFrame, asset: str) -> pd.Series | None:
    if all_logs.empty or "name" not in all_logs.columns:
        return None
    rows = all_logs[all_logs["name"].eq(asset)].copy()
    if rows.empty:
        return None
    freq_rank = {"5min": 0, "daily": 1}
    status_rank = {"ok": 0, "invalid": 1, "failed": 2}
    rows["__freq_rank"] = rows.get("freq", pd.Series(dtype=str)).map(freq_rank).fillna(9)
    rows["__status_rank"] = rows.get("status", pd.Series(dtype=str)).map(status_rank).fillna(9)
    rows = rows.sort_values(["__status_rank", "__freq_rank", "rows"], ascending=[True, True, False])
    return rows.iloc[0]


def _provenance_table(summary_main: pd.DataFrame, all_logs: pd.DataFrame) -> str:
    if summary_main.empty:
        return "<div class='empty-state'>主观察区间为空，当前没有可核对的核心资产来源。</div>"

    rows = []
    assets = [asset for asset in CORE_PROVENANCE_ASSETS if asset in set(summary_main.get("Asset", []))]
    if not assets:
        assets = list(summary_main["Asset"].head(8))

    for asset in assets:
        summary_row = summary_main.loc[summary_main["Asset"].eq(asset)].iloc[0]
        log_row = _select_log_row(all_logs, asset)
        rows.append(
            {
                "Asset": asset,
                "Level": summary_row.get("Level", ""),
                "Last Time": summary_row.get("Last Time", ""),
                "RIC": "" if log_row is None else log_row.get("ric", ""),
                "Field": "" if log_row is None else log_row.get("field", ""),
                "Freq": "" if log_row is None else log_row.get("freq", ""),
                "Rows": "" if log_row is None else log_row.get("rows", ""),
            }
        )

    return html_table(pd.DataFrame(rows), ["Asset", "Level", "Last Time", "RIC", "Field", "Freq", "Rows"])


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
    generated_at = datetime.now(settings.REPORT_TZ)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    html_path = os.path.join(settings.OUTPUT_DIR, f"morning_dashboard_{timestamp}.html")
    csv_path = os.path.join(settings.OUTPUT_DIR, f"summary_{timestamp}.csv")
    log_path = os.path.join(settings.OUTPUT_DIR, f"ric_log_{timestamp}.csv")

    summary_main.to_csv(csv_path, index=False, encoding="utf-8-sig")
    all_logs.to_csv(log_path, index=False, encoding="utf-8-sig")

    summary_cols = ["Group", "Asset", "Level", "Change Text", "% Change Text", "High", "Low", "Obs"]
    log_cols = ["freq", "section", "group", "name", "ric", "field", "rows", "status", "error"]
    log_display = all_logs[[c for c in log_cols if c in all_logs.columns]].copy()

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
    grade_badges = "".join(
        f"<span class='grade-line'>{_section_label(sec)} {_grade_badge(grade)}</span>"
        for sec, grade in sorted(grades.items())
    )
    status_banner_html = _quality_banner(summary_main, quality_df)
    status_summary_text = _quality_summary_text(summary_main, quality_df)

    main_quote_time = _main_quote_time(summary_main, windows)
    primary_message = _primary_message(morning_notes, status_summary_text)
    provenance_html = _provenance_table(summary_main, log_display)

    metrics_html = "".join(
        [
            metric_card("报告时点", windows.asof_dt.strftime("%Y-%m-%d %H:%M"), "Asia/Shanghai", "neutral"),
            metric_card("对应美国市场日", windows.prev_us_day.strftime("%Y-%m-%d"), "用于外部公开数据核对", "neutral"),
            metric_card("主窗口末端报价", main_quote_time, "主观察区间最后一个有效点", "neutral"),
            metric_card("十年期美债", chg(summary_main, "UST 10Y"), "名义收益率", "highlight"),
            metric_card("美元指数", chg(summary_main, "DXY"), ".DXY", "highlight"),
            metric_card("人民币中间价", fixing_value, fixing_detail, "neutral"),
        ]
    )

    notes_html = _notes_section(morning_notes)
    figs_block = _render_figures(figs)
    quality_html = html_table(quality_df)
    trading_html = html_table(trading_hours)
    events_html = html_table(event_calendar)
    log_html = html_table(log_display)
    ai_section = _ai_section(interpretation)

    main_window_desc = (
        f"{windows.main_start.strftime('%Y-%m-%d %H:%M')} 至 "
        f"{windows.main_end.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai"
    )
    ny_window_desc = (
        f"{windows.ny_start.strftime('%Y-%m-%d %H:%M')} 至 "
        f"{windows.ny_end.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai"
    )

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>美债与美元晨间简报 {windows.asof_dt.strftime('%Y-%m-%d')}</title>
<style>
:root {{
    --page-bg: #eff3f8;
    --surface: #ffffff;
    --surface-soft: #f7f9fc;
    --surface-strong: #0f172a;
    --ink: #0f172a;
    --muted: #475569;
    --line: #d9e2ec;
    --accent: #0f766e;
    --accent-soft: rgba(15, 118, 110, 0.10);
    --warn: #b45309;
    --warn-soft: rgba(180, 83, 9, 0.12);
    --danger: #b91c1c;
    --danger-soft: rgba(185, 28, 28, 0.10);
    --navy: #10233f;
    --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}}
* {{
    box-sizing: border-box;
}}
html {{
    scroll-behavior: smooth;
}}
body {{
    margin: 0;
    color: var(--ink);
    font-family: "Aptos", "Segoe UI Variable", "PingFang SC", "Microsoft YaHei", sans-serif;
    background:
        radial-gradient(circle at top left, rgba(16, 35, 63, 0.08), transparent 26%),
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.10), transparent 24%),
        linear-gradient(180deg, #f5f8fc 0%, var(--page-bg) 34%, #f8fafc 100%);
}}
.page {{
    max-width: 1500px;
    margin: 0 auto;
    padding: 28px 20px 40px 20px;
}}
.masthead {{
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.85fr);
    gap: 18px;
    align-items: stretch;
    margin-bottom: 18px;
}}
.hero-panel,
.status-panel,
.section-shell,
.side-card,
.collapsible {{
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid rgba(217, 226, 236, 0.92);
    border-radius: 24px;
    box-shadow: var(--shadow);
}}
.hero-panel {{
    padding: 28px 30px;
    background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(247, 249, 252, 0.96)),
        linear-gradient(180deg, rgba(16, 35, 63, 0.03), transparent);
}}
.eyebrow {{
    margin-bottom: 12px;
    font-size: 12px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--accent);
}}
.hero-panel h1 {{
    margin: 0;
    font-size: 42px;
    line-height: 1.12;
    font-family: "Georgia", "Source Han Serif SC", "STSong", serif;
    color: #10233f;
}}
.hero-copy {{
    margin: 16px 0 18px 0;
    max-width: 880px;
    font-size: 16px;
    line-height: 1.8;
    color: #1f3147;
}}
.hero-meta,
.section-nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}}
.hero-chip,
.nav-chip {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 12px;
    border-radius: 999px;
    border: 1px solid rgba(16, 35, 63, 0.08);
    background: rgba(255, 255, 255, 0.72);
    color: var(--muted);
    font-size: 13px;
}}
.nav-chip {{
    text-decoration: none;
    color: #173150;
    background: rgba(15, 118, 110, 0.08);
    border-color: rgba(15, 118, 110, 0.14);
}}
.status-panel {{
    padding: 22px 24px;
    background:
        linear-gradient(180deg, rgba(16, 35, 63, 0.96), rgba(16, 35, 63, 0.90)),
        linear-gradient(135deg, rgba(15, 118, 110, 0.22), transparent 55%);
    color: #f8fafc;
}}
.status-label {{
    margin-bottom: 10px;
    font-size: 12px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.72);
}}
.status-summary {{
    font-size: 16px;
    line-height: 1.8;
    color: #f8fafc;
    margin-bottom: 18px;
}}
.status-grades {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px 10px;
}}
.grade-line {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: rgba(248, 250, 252, 0.92);
    font-size: 13px;
}}
.grade-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid transparent;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
}}
.section-nav {{
    margin-bottom: 18px;
}}
.status-banner {{
    border-radius: 20px;
    padding: 16px 18px;
    margin-bottom: 18px;
}}
.status-banner-danger {{
    background: linear-gradient(135deg, var(--danger-soft), rgba(255, 255, 255, 0.96));
    border: 1px solid rgba(185, 28, 28, 0.18);
}}
.status-banner-warn {{
    background: linear-gradient(135deg, var(--warn-soft), rgba(255, 255, 255, 0.96));
    border: 1px solid rgba(180, 83, 9, 0.18);
}}
.status-banner-title {{
    margin-bottom: 6px;
    font-size: 16px;
    font-weight: 700;
}}
.status-banner-body {{
    font-size: 14px;
    line-height: 1.8;
    color: #334155;
}}
.overview-grid {{
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
    gap: 18px;
    margin-bottom: 18px;
}}
.overview-main {{
    min-width: 0;
}}
.overview-side {{
    display: grid;
    gap: 16px;
    align-content: start;
    position: sticky;
    top: 18px;
    min-width: 0;
}}
.side-card {{
    padding: 18px 20px;
}}
.side-card h3 {{
    margin: 0 0 12px 0;
    font-size: 20px;
    font-family: "Georgia", "Source Han Serif SC", "STSong", serif;
    color: #10233f;
}}
.side-note {{
    font-size: 14px;
    line-height: 1.8;
    color: #334155;
}}
.mini-list {{
    display: grid;
    gap: 10px;
}}
.mini-row {{
    display: grid;
    grid-template-columns: 108px 1fr;
    gap: 10px;
    align-items: start;
    padding-top: 10px;
    border-top: 1px solid rgba(217, 226, 236, 0.92);
}}
.mini-row:first-child {{
    padding-top: 0;
    border-top: 0;
}}
.mini-label {{
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748b;
    font-weight: 700;
}}
.mini-value {{
    font-size: 14px;
    line-height: 1.7;
    color: #1e293b;
}}
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}}
.metric-card {{
    padding: 14px 16px 16px 16px;
    border-radius: 18px;
    border: 1px solid rgba(217, 226, 236, 0.92);
    background: var(--surface-soft);
}}
.metric-card-highlight {{
    background: linear-gradient(135deg, rgba(15, 118, 110, 0.10), rgba(255, 255, 255, 0.92));
    border-color: rgba(15, 118, 110, 0.18);
}}
.metric-title {{
    margin-bottom: 8px;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748b;
    font-weight: 700;
}}
.metric-body {{
    font-size: 22px;
    line-height: 1.35;
    font-weight: 700;
    color: #0f172a;
}}
.metric-detail {{
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.7;
    color: #475569;
}}
.section-shell {{
    padding: 22px 24px;
    margin-bottom: 18px;
}}
.section-head {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 14px;
}}
.section-kicker {{
    font-size: 12px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--accent);
}}
.section-head h2 {{
    margin: 4px 0 0 0;
    font-size: 28px;
    line-height: 1.2;
    color: #10233f;
    font-family: "Georgia", "Source Han Serif SC", "STSong", serif;
}}
.section-footnote {{
    margin-top: 12px;
    font-size: 12px;
    line-height: 1.8;
    color: #64748b;
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
    gap: 14px;
}}
.analysis-card {{
    min-height: 188px;
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(247, 249, 252, 0.96), rgba(255, 255, 255, 0.98));
    border: 1px solid rgba(217, 226, 236, 0.92);
}}
.analysis-title {{
    margin-bottom: 10px;
    font-size: 16px;
    font-weight: 700;
    color: #10233f;
}}
.analysis-body {{
    font-size: 14px;
    line-height: 1.85;
    color: #334155;
}}
.ai-empty,
.empty-state {{
    padding: 16px 18px;
    border-radius: 16px;
    background: #f8fafc;
    border: 1px dashed rgba(148, 163, 184, 0.55);
    color: #475569;
    font-size: 14px;
    line-height: 1.8;
}}
.table-wrap {{
    overflow-x: auto;
}}
.clean-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 13px;
}}
.clean-table thead th {{
    position: sticky;
    top: 0;
    padding: 12px;
    text-align: left;
    background: #eef3f8;
    color: #173150;
    font-weight: 700;
    border-bottom: 1px solid var(--line);
}}
.clean-table tbody td {{
    padding: 12px;
    border-bottom: 1px solid rgba(217, 226, 236, 0.92);
    color: #1e293b;
    white-space: nowrap;
}}
.clean-table tbody tr:nth-child(even) {{
    background: rgba(248, 250, 252, 0.86);
}}
.clean-table tbody tr:hover {{
    background: rgba(15, 118, 110, 0.06);
}}
.section-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
}}
.data-block {{
    padding: 18px;
    border-radius: 20px;
    border: 1px solid rgba(217, 226, 236, 0.92);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 249, 252, 0.98));
}}
.data-block h3 {{
    margin: 0 0 12px 0;
    font-size: 20px;
    color: #10233f;
    font-family: "Georgia", "Source Han Serif SC", "STSong", serif;
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
    color: #10233f;
    background: linear-gradient(135deg, rgba(16, 35, 63, 0.04), rgba(15, 118, 110, 0.07));
}}
.collapsible-header.active {{
    border-bottom: 1px solid rgba(217, 226, 236, 0.92);
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
    gap: 16px;
}}
.chart-card {{
    padding: 10px;
    border-radius: 20px;
    border: 1px solid rgba(217, 226, 236, 0.92);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 249, 252, 0.98));
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
code {{
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 0.95em;
}}
@media (max-width: 1240px) {{
    .masthead,
    .overview-grid,
    .section-grid {{
        grid-template-columns: 1fr;
    }}
    .overview-side {{
        position: static;
    }}
    .analysis-grid,
    .charts-grid {{
        grid-template-columns: 1fr;
    }}
}}
@media (max-width: 760px) {{
    .page {{
        padding: 16px 12px 28px 12px;
    }}
    .hero-panel h1 {{
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
    <header class="masthead">
        <section class="hero-panel">
            <div class="eyebrow">UST Morning Dashboard</div>
            <h1>美债与美元晨间简报</h1>
            <div class="hero-copy">{primary_message}</div>
            <div class="hero-meta">
                <div class="hero-chip">报告时点：{windows.asof_dt.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai</div>
                <div class="hero-chip">对应美国市场日：{windows.prev_us_day.strftime('%Y-%m-%d')}</div>
                <div class="hero-chip">主观察区间：{main_window_desc}</div>
                <div class="hero-chip">页面生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
        </section>
        <aside class="status-panel">
            <div class="status-label">Batch Status</div>
            <div class="status-summary">{status_summary_text}</div>
            <div class="status-grades">{grade_badges}</div>
        </aside>
    </header>

    <nav class="section-nav">
        <a class="nav-chip" href="#summary">摘要</a>
        <a class="nav-chip" href="#analysis">分析</a>
        <a class="nav-chip" href="#tables">主表</a>
        <a class="nav-chip" href="#charts">图表</a>
        <a class="nav-chip" href="#checks">数据检查</a>
    </nav>

    {status_banner_html}

    <section class="overview-grid">
        <div class="overview-main">
            <section class="section-shell" id="summary">
                <div class="section-head">
                    <div class="section-kicker">Morning Brief</div>
                    <h2>晨会摘要</h2>
                </div>
                {notes_html}
            </section>

            {ai_section}
        </div>

        <aside class="overview-side">
            <div class="side-card">
                <h3>关键观察</h3>
                <div class="metrics-grid">{metrics_html}</div>
            </div>

            <div class="side-card">
                <h3>时间口径</h3>
                <div class="mini-list">
                    <div class="mini-row">
                        <div class="mini-label">报告日期</div>
                        <div class="mini-value">{windows.asof_date.strftime('%Y-%m-%d')}，对应上海早会使用时点。</div>
                    </div>
                    <div class="mini-row">
                        <div class="mini-label">美国市场日</div>
                        <div class="mini-value">对应 {windows.prev_us_day.strftime('%Y-%m-%d')}，外部公开网站核对时应以该日期为准。</div>
                    </div>
                    <div class="mini-row">
                        <div class="mini-label">主窗口末端报价</div>
                        <div class="mini-value">{main_quote_time}，表示主观察区间最后一个有效点，部分二十四小时交易品种可能与公开网站按日收盘或结算价存在时点差。</div>
                    </div>
                    <div class="mini-row">
                        <div class="mini-label">纽约时段</div>
                        <div class="mini-value">{ny_window_desc}</div>
                    </div>
                </div>
            </div>

            <div class="side-card">
                <h3>数据时间与来源</h3>
                <div class="table-wrap">{provenance_html}</div>
                <div class="section-footnote">本表列出主观察区间内核心资产的最新展示值、最后报价时间，以及本批次命中的 RIC 与字段。</div>
            </div>
        </aside>
    </section>

    <section class="section-shell" id="tables">
        <div class="section-head">
            <div class="section-kicker">Primary Tables</div>
            <h2>主观察区间表格</h2>
        </div>
        <div class="section-grid">
            <section class="data-block">
                <h3>利率与通胀补偿</h3>
                <div class="table-wrap">{rates_tbl}</div>
            </section>
            <section class="data-block">
                <h3>美元、外汇与人民币</h3>
                <div class="table-wrap">{usd_rmb_tbl}</div>
            </section>
            <section class="data-block">
                <h3>美债期货与大宗商品</h3>
                <div class="table-wrap">{fut_cmd_tbl}</div>
            </section>
        </div>
        <div class="section-footnote">主表展示主观察区间的最新值和区间变化，适合用于晨会首屏阅读。</div>
    </section>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">滚动二十四小时补充区间</div>
        <div class="collapsible-body">
            <div class="section-grid">
                <section class="data-block">
                    <h3>利率与通胀补偿</h3>
                    <div class="table-wrap">{rates_24h_tbl}</div>
                </section>
                <section class="data-block">
                    <h3>美元、外汇与人民币</h3>
                    <div class="table-wrap">{usd_rmb_24h_tbl}</div>
                </section>
            </div>
        </div>
    </div>

    <div class="collapsible">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">纽约交易时段补充区间</div>
        <div class="collapsible-body">
            <div class="section-grid">
                <section class="data-block">
                    <h3>利率与通胀补偿</h3>
                    <div class="table-wrap">{rates_ny_tbl}</div>
                </section>
                <section class="data-block">
                    <h3>美元、外汇与人民币</h3>
                    <div class="table-wrap">{usd_rmb_ny_tbl}</div>
                </section>
                <section class="data-block">
                    <h3>美债期货与大宗商品</h3>
                    <div class="table-wrap">{fut_cmd_ny_tbl}</div>
                </section>
            </div>
        </div>
    </div>

    <section class="section-shell" id="charts">
        <div class="section-head">
            <div class="section-kicker">Charts</div>
            <h2>图表观察</h2>
        </div>
        {figs_block}
    </section>

    <section class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Reference</div>
            <h2>主要交易时段</h2>
        </div>
        <div class="table-wrap">{trading_html}</div>
    </section>

    <section class="section-shell">
        <div class="section-head">
            <div class="section-kicker">Calendar</div>
            <h2>美国重要经济数据日程</h2>
        </div>
        <div class="table-wrap">{events_html}</div>
        <div class="section-footnote">
            FOMC、CPI、PCE、NFP、GDP、Retail Sales 等高重要性日期可以维护在
            <code>config/settings.py</code> 的 <code>MANUAL_US_EVENTS</code> 中；周度初请仍按周四 08:30 ET 自动生成。
        </div>
    </section>

    <section class="section-shell" id="checks">
        <div class="section-head">
            <div class="section-kicker">Diagnostics</div>
            <h2>数据检查</h2>
        </div>
        <div class="table-wrap">{quality_html}</div>
        <details>
            <summary>查看 RIC 拉取日志</summary>
            <div class="table-wrap">{log_html}</div>
        </details>
    </section>
</div>
<script>
document.querySelectorAll('.collapsible-header').forEach(function (header) {{
    header.addEventListener('keydown', function (event) {{
        if (event.key === 'Enter' || event.key === ' ') {{
            event.preventDefault();
            header.click();
        }}
    }});
    header.setAttribute('tabindex', '0');
}});
</script>
</body>
</html>
"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html_path, csv_path, log_path
