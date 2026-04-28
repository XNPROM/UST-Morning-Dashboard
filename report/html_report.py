from __future__ import annotations

import os
from datetime import datetime
import pandas as pd
from analytics.quality import compute_quality_grade, find_blocking_quality_issues
from analytics.summary import chg, latest_fixing_info, rows_by_section
from config.settings import settings
from dates.windows import ReportWindows

SECTION_LABELS = {
    'A. Rates': '1. 利率、曲线、真实利率、BEI',
    'B. Real & Inflation': '1. 利率、曲线、真实利率、BEI',
    'C. Treasury Futures': '3. 美债期货、油铜金',
    'D. USD & FX': '2. 美元、外汇、人民币',
    'E. RMB': '2. 美元、外汇、人民币',
    'F. Commodities': '3. 美债期货、油铜金',
}

SECTION_ORDER = ['A. Rates', 'B. Real & Inflation', 'D. USD & FX', 'E. RMB', 'C. Treasury Futures', 'F. Commodities']


def html_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    """Render a DataFrame as an HTML table."""
    if cols:
        df = df[[c for c in cols if c in df.columns]].copy()
    if max_rows:
        df = df.head(max_rows)
    if df.empty:
        return "<div class='empty-state'>暂无数据可供当前展示。</div>"
    return df.to_html(index=False, classes='clean-table', border=0)


def _grade_badge(grade: str) -> str:
    colors = {'A': '#22c55e', 'B': '#f59e0b', 'C': '#ef4444'}
    color = colors.get(grade, '#6b7280')
    return (
        f"<span style='display:inline-block;padding:2px 8px;border-radius:8px;background:"
        f"{color};color:white;font-size:12px;font-weight:700'>{grade}</span>"
    )


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
    """Generate the full HTML report and return (html_path, csv_path, log_path)."""
    timestamp = timestamp or datetime.now(settings.REPORT_TZ).strftime('%Y%m%d_%H%M')
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    asof_str = windows.asof_dt.strftime('%Y-%m-%d %H:%M')
    date_str = windows.asof_dt.strftime('%Y-%m-%d')

    # Quality grades
    grades = compute_quality_grade(quality_df)
    grade_html = '数据质量评级：'
    grade_keys = ['A. Rates', 'B. Real & Inflation', 'C. Treasury Futures', 'D. USD & FX', 'E. RMB', 'F. Commodities']
    grade_labels = ['A. Rates', 'B. Real & Inflation', 'C. Treasury Futures', 'D. USD & FX', 'E. RMB', 'F. Commodities']
    for i, gk in enumerate(grade_keys):
        grade_html += f'{grade_labels[i]}: {_grade_badge(grades.get(gk, "A"))} '

    # AI section
    if interpretation:
        ai_html = '<div class="ai-grid">'
        dim_titles = {'changes': '变动', 'reasons': '原因', 'synthesis': '综合'}
        for key, title in dim_titles.items():
            content = interpretation.get(key, '数据不足，当前无法生成解读。')
            ai_html += f'<div class="ai-card"><div class="ai-card-title">{title}</div><div class="ai-card-body">{content}</div></div>'
        ai_html += '</div>'
    else:
        ai_html = '<div class="ai-pending"><p>AI 解读尚未生成。运行后请在 Claude Code 中读取上下文文件并生成解读，然后重新运行看板。</p></div>'

    # Quality issues detail
    quality_detail_html = ''
    if quality_df is not None and not quality_df.empty:
        has_ok = quality_df.iloc[0].get('Severity') == 'OK' if len(quality_df) > 0 else True
        if not has_ok:
            quality_detail_html = html_table(quality_df, ['Severity', 'Asset', 'Issue', 'Detail'])

    # Data quality log
    dq_log_html = ''
    if all_logs is not None and not all_logs.empty:
        dq_log_html = f'<details><summary>数据拉取日志</summary>{html_table(all_logs)}</details>'

    # Section tables for main summary
    def _section_table(summary, sections, title):
        df = rows_by_section(summary, sections)
        if df.empty:
            return ''
        cols = ['Group', 'Asset', 'Level', 'Change Text', '% Change Text', 'High', 'Low', 'Obs']
        return html_table(df, cols)

    # Main section tables
    section_tables = {}
    for sec_key in SECTION_ORDER:
        sec_label = SECTION_LABELS.get(sec_key, sec_key)
        if sec_label not in section_tables:
            section_tables[sec_label] = {'dfs': [], 'title': sec_label}
        df = rows_by_section(summary_main, [sec_key])
        if not df.empty:
            section_tables[sec_label]['dfs'].append(df)

    # Build section HTML
    main_sections_html = ''
    for sec_label, sec_data in section_tables.items():
        if not sec_data['dfs']:
            continue
        combined = pd.concat(sec_data['dfs'], ignore_index=True)
        cols = ['Group', 'Asset', 'Level', 'Change Text', '% Change Text', 'High', 'Low', 'Obs']
        main_sections_html += f'<div class="section"><h2>{sec_data["title"]}</h2>{html_table(combined, cols)}</div>'

    # 24h sections
    section_tables_24h = {}
    for sec_key in SECTION_ORDER:
        sec_label = SECTION_LABELS.get(sec_key, sec_key) + '（24h）'
        base_label = SECTION_LABELS.get(sec_key, sec_key)
        if base_label not in section_tables_24h:
            section_tables_24h[base_label] = {'dfs': []}
        df = rows_by_section(summary_24h, [sec_key])
        if not df.empty:
            section_tables_24h[base_label]['dfs'].append(df)

    sections_24h_html = ''
    for sec_label, sec_data in section_tables_24h.items():
        if not sec_data['dfs']:
            continue
        combined = pd.concat(sec_data['dfs'], ignore_index=True)
        cols = ['Group', 'Asset', 'Level', 'Change Text', '% Change Text', 'High', 'Low', 'Obs']
        sections_24h_html += f'<h3>{sec_label}</h3>{html_table(combined, cols)}'

    # NY sections
    section_tables_ny = {}
    for sec_key in SECTION_ORDER:
        sec_label = SECTION_LABELS.get(sec_key, sec_key) + '（NY）'
        base_label = SECTION_LABELS.get(sec_key, sec_key)
        if base_label not in section_tables_ny:
            section_tables_ny[base_label] = {'dfs': []}
        df = rows_by_section(summary_ny, [sec_key])
        if not df.empty:
            section_tables_ny[base_label]['dfs'].append(df)

    sections_ny_html = ''
    for sec_label, sec_data in section_tables_ny.items():
        if not sec_data['dfs']:
            continue
        combined = pd.concat(sec_data['dfs'], ignore_index=True)
        cols = ['Group', 'Asset', 'Level', 'Change Text', '% Change Text', 'High', 'Low', 'Obs']
        sections_ny_html += f'<h3>{sec_label}</h3>{html_table(combined, cols)}'

    # Charts HTML
    charts_parts = []
    for fig in figs:
        charts_parts.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    charts_html = ''.join(charts_parts) if charts_parts else ''

    # Notes
    notes_html = ''
    if morning_notes:
        notes_html = '<ul>' + ''.join(f'<li>{n}</li>' for n in morning_notes) + '</ul>'

    # KPI cards
    cards_html = ''
    card_data = []
    card_data.append(('As-of', f'{asof_str}<br><span class="muted">Asia/Shanghai</span>'))
    card_data.append(('主窗口', f'{windows.main_start.strftime("%m-%d %H:%M")} → {windows.main_end.strftime("%m-%d %H:%M")}<br><span class="muted">上一中国收盘后至早会</span>'))
    if not summary_main.empty and 'Asset' in summary_main.columns:
        ust_10y = summary_main[summary_main['Asset'] == 'UST 10Y']
        if not ust_10y.empty:
            r = ust_10y.iloc[0]
            card_data.append(('10Y UST', f'{r["Level"]}（{r["Change Text"]}）'))
        dxy = summary_main[summary_main['Asset'] == 'DXY']
        if not dxy.empty:
            r = dxy.iloc[0]
            card_data.append(('DXY', f'{r["Level"]}（{r["Change Text"]}）'))
    fix = latest_fixing_info(daily_panel, windows.target_fixing_date)
    if fix['status'] != 'missing':
        card_data.append(('USD/CNY fixing', f'{fix["last"]:.4f}｜+{fix["chg_pips"]:.0f} pips<br><span class="muted">latest {fix["last_date"]} / target {fix["target_date"]}</span>'))
    for title, body in card_data:
        cards_html += f'<div class="card"><div class="card-title">{title}</div><div class="card-body">{body}</div></div>'

    # Main window label
    main_label = f'主窗口：{windows.main_start.strftime("%m-%d %H:%M")} → {windows.main_end.strftime("%m-%d %H:%M")} Asia/Shanghai'
    ny_label = f'纽约窗口：{windows.ny_start.strftime("%m-%d %H:%M")} → {windows.ny_end.strftime("%m-%d %H:%M")} Asia/Shanghai'

    # Trading hours table
    trading_hours_html = html_table(trading_hours) if trading_hours is not None and not trading_hours.empty else ''
    event_html = html_table(event_calendar) if event_calendar is not None and not event_calendar.empty else ''

    now_str = datetime.now(settings.REPORT_TZ).strftime('%Y-%m-%d %H:%M:%S')

    html_content = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>深圳早会看板 {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{ font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #ffffff; color: #0f172a; margin: 0; line-height: 1.6; -webkit-font-smoothing: antialiased; }}
.container {{ max-width: 1360px; margin: 0 auto; padding: 20px 28px 60px; }}
.nav-bar {{ position: sticky; top: 0; z-index: 100; background: rgba(255,255,255,.95); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 0 28px; display: flex; align-items: center; gap: 4px; overflow-x: auto; border-bottom: 1px solid #e2e8f0; }}
.nav-bar a {{ color: #64748b; text-decoration: none; font-size: 12.5px; font-weight: 500; padding: 12px 14px; white-space: nowrap; transition: color .2s, border-color .2s; border-bottom: 2px solid transparent; }}
.nav-bar a:hover {{ color: #0f172a; border-bottom-color: #2563eb; }}
.header {{ background: #ffffff; color: #0f172a; padding: 32px 0 24px; border-bottom: 1px solid #e2e8f0; margin-bottom: 4px; }}
.header h1 {{ margin: 0 0 6px 0; font-size: 26px; font-weight: 700; letter-spacing: -0.3px; color: #0f172a; }}
.subtitle {{ color: #64748b; font-size: 13px; line-height: 1.7; font-weight: 400; }}
.cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin: 18px 0 22px 0; }}
.card {{ background: #ffffff; border-radius: 8px; padding: 16px; border: 1px solid #e2e8f0; transition: border-color .2s ease; cursor: default; }}
.card:hover {{ border-color: #cbd5e1; }}
.card-title {{ font-size: 11px; color: #64748b; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
.card-body {{ font-size: 16px; font-weight: 600; line-height: 1.4; color: #0f172a; }}
.section {{ background: #ffffff; border-radius: 8px; padding: 22px 24px; margin: 14px 0; border: 1px solid #e2e8f0; }}
.section h2 {{ font-size: 16px; font-weight: 600; margin: 0 0 14px 0; padding-bottom: 10px; border-bottom: 1px solid #f1f5f9; color: #0f172a; display: flex; align-items: center; gap: 10px; }}
.section h2::before {{ content: ''; display: inline-block; width: 3px; height: 18px; background: #2563eb; border-radius: 2px; flex-shrink: 0; }}
.section h3 {{ font-size: 14px; margin: 18px 0 10px 0; color: #334155; font-weight: 600; }}
.clean-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
.clean-table thead {{ position: sticky; top: 0; z-index: 2; }}
.clean-table th {{ text-align: left; background: #f8fafc; color: #475569; padding: 10px 14px; border-bottom: 1px solid #e2e8f0; white-space: nowrap; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }}
.clean-table td {{ padding: 9px 14px; border-bottom: 1px solid #f1f5f9; white-space: nowrap; font-variant-numeric: tabular-nums; color: #1e293b; }}
.clean-table tbody tr {{ transition: background .12s ease; }}
.clean-table tbody tr:hover {{ background: #f8fafc; }}
.clean-table tbody tr:last-child td {{ border-bottom: none; }}
.chg-pos {{ color: #16a34a !important; font-weight: 500; }}
.chg-neg {{ color: #dc2626 !important; font-weight: 500; }}
.muted {{ color: #64748b; font-size: 12px; font-weight: 400; }}
.ai-grid {{ display: grid; grid-template-columns: 1fr; gap: 0; }}
.ai-card {{ background: #ffffff; border-left: 3px solid #2563eb; padding: 16px 20px; }}
.ai-card + .ai-card {{ border-top: 1px solid #f1f5f9; }}
.ai-card-title {{ font-size: 12px; font-weight: 600; color: #2563eb; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.3px; }}
.ai-card-body {{ font-size: 13px; line-height: 1.85; color: #1e293b; }}
.ai-pending {{ background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 28px 16px; text-align: center; color: #64748b; font-size: 14px; }}
.grade-bar {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; font-size: 13px; line-height: 2.2; display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; }}
details {{ margin-top: 12px; }}
summary {{ cursor: pointer; color: #2563eb; font-weight: 600; font-size: 13px; padding: 6px 0; transition: color .15s; }}
summary:hover {{ color: #1d4ed8; }}
ul {{ margin-top: 8px; line-height: 1.8; padding-left: 20px; }}
ul li {{ margin-bottom: 4px; }}
.collapsible {{ background: #ffffff; border-radius: 8px; margin: 14px 0; border: 1px solid #e2e8f0; overflow: hidden; }}
.collapsible-header {{ padding: 14px 24px; cursor: pointer; font-size: 15px; font-weight: 600; color: #0f172a; user-select: none; display: flex; align-items: center; gap: 10px; transition: background .15s ease; }}
.collapsible-header:hover {{ background: #f8fafc; }}
.collapsible-header::after {{ content: ''; display: inline-block; width: 7px; height: 7px; border-right: 2px solid #94a3b8; border-bottom: 2px solid #94a3b8; transform: rotate(-45deg); margin-left: auto; transition: transform .25s ease; flex-shrink: 0; }}
.collapsible-header.active::after {{ transform: rotate(45deg); }}
.collapsible-body {{ padding: 0 24px 20px 24px; display: none; }}
.collapsible-header.active + .collapsible-body {{ display: block; }}
.scroll-top {{ position: fixed; bottom: 28px; right: 28px; width: 40px; height: 40px; background: #0f172a; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(15,23,42,.15); opacity: 0; transform: translateY(12px); transition: opacity .25s, transform .25s; z-index: 99; }}
.scroll-top.visible {{ opacity: 1; transform: translateY(0); }}
.scroll-top:hover {{ background: #1e293b; }}
@media print {{ .nav-bar, .scroll-top {{ display: none !important; }} .collapsible-body {{ display: block !important; }} .container {{ padding: 0; }} .section, .collapsible, .card {{ box-shadow: none; border: 1px solid #ddd; break-inside: avoid; }} }}
@media (max-width: 1000px) {{ .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .container {{ padding: 12px 14px 48px; }} .header {{ padding: 22px 0; }} .header h1 {{ font-size: 22px; }} .nav-bar {{ padding: 0 12px; }} }}
@media (max-width: 600px) {{ .cards {{ grid-template-columns: 1fr; }} .header h1 {{ font-size: 19px; }} .clean-table {{ font-size: 11.5px; }} .clean-table th, .clean-table td {{ padding: 7px 8px; }} }}
</style>
</head>
<body>
<nav class="nav-bar">
    <a href="#summary">Summary</a>
    <a href="#ai">AI</a>
    <a href="#quality">Quality</a>
    <a href="#24h">24h</a>
    <a href="#ny">NY</a>
    <a href="#charts">Charts</a>
    <a href="#sessions">Sessions</a>
    <a href="#calendar">Calendar</a>
</nav>
<div class="container" id="top">
    <div class="header">
        <h1>LSEG 美债收益率 & 美元晨间看板</h1>
        <div class="subtitle">
            深圳早会版 v6 | 主窗口：上一中国交易日16:00 &rarr; 今日09:00 |
            {ny_label} |
            生成时间：{now_str}
        </div>
    </div>

    <div class="cards">{cards_html}</div>

    <div class="section" id="summary">
        <h2>一屏结论</h2>
        {notes_html}
    </div>

    <div class="section" id="ai">
        <h2>AI 深度解读</h2>
        {ai_html}
    </div>

    <div class="section" id="quality">
        <div class="grade-bar">{grade_html}</div>
        {main_sections_html}
    </div>

    <div class="collapsible" id="24h">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">▸ 滚动24小时概览</div>
        <div class="collapsible-body">{sections_24h_html}</div>
    </div>

    <div class="collapsible" id="ny">
        <div class="collapsible-header" onclick="this.classList.toggle('active')">▸ 纽约交易时段概览</div>
        <div class="collapsible-body">{sections_ny_html}</div>
    </div>

    <div class="section" id="charts">
        <h2>4. 图表</h2>
        {charts_html}
    </div>

    <div class="section" id="sessions">
        <h2>5. 交易时段对照</h2>
        {trading_hours_html}
    </div>

    <div class="section" id="calendar">
        <h2>6. 美国重要数据日历</h2>
        {event_html}
        <p class="muted">说明：FOMC、CPI、PCE、NFP、GDP、Retail Sales 等高重要性日期建议填入 config/settings.py 的 MANUAL_US_EVENTS；周度初请按周四 08:30 ET 自动生成。</p>
    </div>

    <div class="section">
        <h2>7. 数据质量 / 口径检查</h2>
        {quality_detail_html}
        {dq_log_html}
    </div>
</div>
<button class="scroll-top" id="scrollTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">&#8593;</button>
<script>
document.querySelectorAll('.collapsible-header').forEach(h => {{
    if (!h.classList.contains('bound')) {{
        h.classList.add('bound');
    }}
}});
var stb = document.getElementById('scrollTop');
if (stb) {{
    window.addEventListener('scroll', function() {{
        stb.classList.toggle('visible', window.scrollY > 400);
    }});
}}
document.querySelectorAll('.clean-table td').forEach(function(td) {{
    var t = td.textContent.trim();
    if (/^[+]\\d/.test(t) || /^\\+/.test(t)) {{
        td.classList.add('chg-pos');
    }} else if (/^[-]\\d/.test(t) || (/^-/.test(t) && /\\d/.test(t))) {{
        td.classList.add('chg-neg');
    }}
}});
</script>
</body>
</html>'''

    # Write files
    html_path = os.path.join(settings.OUTPUT_DIR, f'morning_dashboard_{timestamp}.html')
    csv_path = os.path.join(settings.OUTPUT_DIR, f'summary_{timestamp}.csv')
    log_path = os.path.join(settings.OUTPUT_DIR, f'ric_log_{timestamp}.csv')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    if summary_main is not None and not summary_main.empty:
        summary_main.to_csv(csv_path, index=False)

    if all_logs is not None and not all_logs.empty:
        all_logs.to_csv(log_path, index=False)

    return html_path, csv_path, log_path
