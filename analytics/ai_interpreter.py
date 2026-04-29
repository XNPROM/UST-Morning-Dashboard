# Source Generated with Decompyle++
# File: ai_interpreter.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import json
import hashlib
import os
import sqlite3
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from config.settings import settings
from analytics.summary import format_level, get_unit, get_order
from dates.windows import ReportWindows

REPORT_WATCH_DB = r'D:\Report Watch\.state\report_watch.sqlite3'

# Keywords to filter macro/rates/FX relevant reports from Report Watch
_MACRO_KEYWORDS = [
    'rates', 'treasury', 'yield', 'FOMC', 'inflation', 'PCE', 'CPI',
    'FX', 'DXY', 'CNY', 'CNH', 'JPY', 'USD', 'EUR',
    'oil', 'gold', 'commodit', 'crude', 'Brent',
    'macro', 'GDP', 'Fed', 'BoJ', 'ECB', 'BoE',
    'morning', 'conviction', 'fixed income',
    'trade', 'tariff', 'Hormuz', 'geopolit',
    'strategy', 'rates strategy', 'open',
]
SYSTEM_PROMPT = (
    '你是深圳某券商固定收益研究团队的晨报分析师。你只基于提供的数据进行分析，不编造任何数字。'
    '如果数据不足以支持明确判断，应当明确说明数据仍需继续观察。\n\n'
    '严格规则：\n'
    '- 引用任何数字时，必须与提供的数据完全一致，不得四舍五入或近似（如数据写3.57bp就不能写成3.6bp）\n'
    '- 不得声称某个资产"突破"了某个点位，除非数据中的实际Level或High确实越过了该点位\n'
    '- 不得推测数据中未出现的极值（如数据中USDJPY最高159.84，不能说"触及160"）\n'
    '- 对每个关键判断，在括号中标注数据来源值，如"10Y收益率高于4.30%（4.3325%）"\n'
    '- 原因分析部分只能引用"近期外资研报摘要"中提供的研报观点，必须标注来源（如"据Barclays《US in Focus》"），不得编造来源\n\n'
    '写作要求：\n'
    '- 使用规范书面中文，句子完整，避免口语化表达、夸张语气和交易台行话\n'
    '- 每段先写观察到的变化，再解释背后的分项结构，最后写仍需继续观察的事项\n'
    '- 文字应当克制、清晰，减少机械重复，不使用项目符号\n'
    '- 如果历史参照不足，明确写出"近阶段可比样本有限"\n\n'
    '你的分析风格：简洁、审慎、逻辑清晰。用中文撰写。'
)


def _fmt_change(chg = None, unit = None):
    """Format a change value with the correct unit and scale."""
    if unit in ('yield_pct', 'bei_pct'):
        return f'{chg * 100:.1f}bp'
    if unit == 'spread_bp':
        return f'{chg:.1f}bp'
    if unit == 'fx_jpy':
        return f'{chg * 100:.1f}pips'
    if unit in ('fx', 'fixing_fx'):
        return f'{chg * 10000:.1f}pips'
    if unit == 'fx_spread':
        return f'{chg * 10000:.1f}pips'
    return f'{chg:.2f}pts'


def _build_daily_stats_text(daily_panel = None):
    if daily_panel is None or daily_panel.empty:
        return '（无日频数据）'
    lines = []
    tail = daily_panel.tail(60)
    for col in sorted(tail.columns, key=get_order):
        s = tail[col].dropna()
        if len(s) < 5:
            continue
        unit = get_unit(col)
        last = float(s.iloc[-1])
        chg_5d = float(s.iloc[-1]) - float(s.iloc[-5]) if len(s) >= 5 else np.nan
        chg_20d = float(s.iloc[-1]) - float(s.iloc[-20]) if len(s) >= 20 else np.nan
        pctile = float(s.rank(pct=True).iloc[-1]) * 100
        parts = [f'{col}: 当前{format_level(last, unit)}']
        if pd.notna(chg_5d):
            parts.append(f'5d变化{_fmt_change(chg_5d, unit)}')
        if pd.notna(chg_20d):
            parts.append(f'20d变化{_fmt_change(chg_20d, unit)}')
        parts.append(f'60d百分位{pctile:.0f}%')
        lines.append('，'.join(parts))
    return '\n'.join(lines)


def _build_summary_text(summary = None):
    if summary is None or summary.empty:
        return '（无摘要数据）'
    lines = []
    for _, r in summary.sort_values('Order').iterrows():
        lines.append(f'{r["Asset"]}: {r["Level"]}（{r["Change Text"]}）')
    return '\n'.join(lines)


def _build_quality_text(quality_df = None):
    if quality_df is None or quality_df.empty:
        return '数据质量：无异常'
    if quality_df.iloc[0].get('Severity') == 'OK':
        return '数据质量：无异常'
    lines = []
    for _, r in quality_df.iterrows():
        lines.append(f'[{r["Severity"]}] {r["Asset"]}: {r["Issue"]} -- {r["Detail"]}')
    return '\n'.join(lines)


def get_recent_macro_reports(asof_dt=None, lookback_days=3, max_reports=15):
    """Read recent macro-relevant report summaries from Report Watch SQLite DB.

    Returns a list of dicts: {bank, title, published_at, summary}
    """
    if not os.path.exists(REPORT_WATCH_DB):
        return []
    if asof_dt is None:
        asof_dt = datetime.now()
    cutoff = (asof_dt - timedelta(days=lookback_days)).strftime('%Y-%m-%dT00:00:00')
    try:
        conn = sqlite3.connect(REPORT_WATCH_DB)
        cur = conn.cursor()
        # Build keyword filter on title + section_name
        kw_clauses = []
        kw_params = []
        for kw in _MACRO_KEYWORDS:
            kw_clauses.append('(title LIKE ? COLLATE NOCASE OR section_name LIKE ? COLLATE NOCASE)')
            kw_params.extend([f'%{kw}%', f'%{kw}%'])
        where_kw = ' OR '.join(kw_clauses)
        sql = (
            'SELECT source_bank, title, published_at, extra_json '
            'FROM items '
            'WHERE published_at >= ? '
            "AND extra_json LIKE '%ai_summary%' "
            f'AND ({where_kw}) '
            'ORDER BY published_at DESC '
            f'LIMIT {max_reports * 3}'  # fetch more, deduplicate later
        )
        cur.execute(sql, [cutoff] + kw_params)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        print(f'[ReportWatch] Error reading DB: {e}')
        return []

    # Parse and deduplicate
    seen_titles = set()
    results = []
    for bank, title, pub_at, extra_json_str in rows:
        # Skip duplicates by normalized title
        norm_title = title.strip().lower()
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        try:
            ej = json.loads(extra_json_str) if extra_json_str else {}
        except json.JSONDecodeError:
            continue
        ai_summary = ej.get('ai_summary', '')
        if not ai_summary or len(ai_summary) < 50:
            continue
        # Extract just the key takeaways section (核心观点) for brevity
        summary_text = _extract_key_section(ai_summary)
        results.append({
            'bank': bank.capitalize(),
            'title': title,
            'published_at': pub_at[:19],
            'summary': summary_text,
        })
        if len(results) >= max_reports:
            break
    return results


def _extract_key_section(full_summary):
    """Extract the most useful sections from the AI summary for context injection.

    Keeps: 核心观点/Key Takeaways + 关键数据/Key Data (truncated).
    Drops: 投资建议, 风险提示, 报告主体 boilerplate.
    """
    lines = full_summary.split('\n')
    keep = []
    in_section = False
    skip_sections = {'投资建议', '风险提示', '报告主体'}
    for line in lines:
        stripped = line.strip()
        # Detect section headers (## ...)
        if stripped.startswith('## '):
            header = stripped.lstrip('# ').split('/')[0].strip()
            if any(sk in header for sk in skip_sections):
                in_section = False
                continue
            in_section = True
            keep.append(stripped)
            continue
        if in_section:
            keep.append(line)
    text = '\n'.join(keep).strip()
    # Truncate to ~800 chars per report to keep context manageable
    if len(text) > 800:
        text = text[:800] + '...'
    return text


def _build_bank_research_text(reports):
    """Format bank research summaries for injection into AI context."""
    if not reports:
        return '（无外资研报数据）'
    lines = []
    for r in reports:
        lines.append(f'### {r["bank"]} — {r["title"]}')
        lines.append(f'发布时间：{r["published_at"]}')
        lines.append(r['summary'])
        lines.append('')
    return '\n'.join(lines)


def build_context(summary_daily, summary_main=None, summary_24h=None, daily_panel=None, quality_df=None, windows=None):
    """Build the full prompt context for AI interpretation."""
    asof_str = windows.asof_dt.strftime('%Y-%m-%d %H:%M %Z')
    main_window_str = f'{windows.main_start.strftime("%m-%d %H:%M")} -> {windows.main_end.strftime("%m-%d %H:%M")}'
    # Fetch bank research from Report Watch
    bank_reports = get_recent_macro_reports(asof_dt=windows.asof_dt, lookback_days=3)
    bank_research_text = _build_bank_research_text(bank_reports)
    return f'## 报告时间\n\
锚定时间：{asof_str}\n\
主窗口：{main_window_str}\n\
\n## 今日收盘变动（前日收盘→当日收盘，与公开行情口径一致）\n\
{_build_summary_text(summary_daily)}\n\
\n## 主窗口内变动（{main_window_str}，仅反映亚洲时段窄幅波动）\n\
{_build_summary_text(summary_main)}\n\
\n## 滚动24小时概览\n\
{_build_summary_text(summary_24h)}\n\
\n## 近60天走势摘要\n\
{_build_daily_stats_text(daily_panel)}\n\
\n## 数据质量检查\n\
{_build_quality_text(quality_df)}\n\
\n## 近期外资研报摘要（Report Watch）\n\
{bank_research_text}\n\
\n---\n\
\n请按照以下五个部分撰写晨会复盘，文字以分析为主，减少机械复述。\n\
**重要：变动方向必须以"今日收盘变动"（前日收盘→当日收盘）为准，这是与公开行情一致的口径。"主窗口内变动"仅反映亚洲时段窄幅波动，不能作为全日叙事依据。**\n\
所有数字必须与上文完全一致：\n\
\n### 一、核心结论\n\
用2-3句话概括隔夜最核心的变化和驱动逻辑。\n\
\n### 二、市场表现\n\
分利率、汇率、商品三个子板块详述变动，拆分名义/实际/通胀预期贡献。\n\
\n### 三、原因分析\n\
结合上方"近期外资研报摘要"中的观点说明变动背后的驱动因素。每个判断必须标注来源研报（如"据Barclays《US in Focus》"）。没有研报支持的观点不要写。\n\
\n### 四、后续观察\n\
列出2-3个值得关注的价位、事件或信号，说明为什么重要以及后续看什么。\n\
\n### 五、错误检查\n\
指出数据质量问题、样本不足或推断不确定的地方。'


def save_context(context = None, timestamp = None):
    """Save context to file for Claude Code to read and interpret."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f'ai_context_{timestamp}.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(context)
    return path


def _summary_fingerprint(summary_main):
    """Create a short hash of summary data to detect stale interpretations."""
    if summary_main is None or summary_main.empty:
        return ''
    key_cols = ['Asset', 'Level', 'Change Text']
    cols = [c for c in key_cols if c in summary_main.columns]
    raw = summary_main[cols].to_csv(index=False)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_interpretation(date_str=None, fingerprint=None):
    """Load pre-generated interpretation from JSON file. Matches by date prefix (YYYYMMDD).
    If fingerprint is provided, checks that the saved fingerprint matches."""
    if not os.path.exists(settings.OUTPUT_DIR):
        return None
    for fname in sorted(os.listdir(settings.OUTPUT_DIR), reverse=True):
        if fname.startswith('ai_interpretation_') and fname.endswith('.json'):
            if date_str and fname.startswith('ai_interpretation_' + date_str[:8]):
                path = os.path.join(settings.OUTPUT_DIR, fname)
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # If fingerprint checking is enabled and the file has a fingerprint, verify it
                if fingerprint and isinstance(data, dict):
                    saved_fp = data.get('_fingerprint', '')
                    if saved_fp and saved_fp != fingerprint:
                        print(f'[AI] Interpretation fingerprint mismatch (saved={saved_fp}, current={fingerprint}), treating as stale.')
                        continue
                return data
    return None


def save_interpretation(interpretation = None, timestamp = None):
    """Save interpretation to JSON file."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f'ai_interpretation_{timestamp}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(interpretation, f, ensure_ascii=False, indent=2)
    return path


def interpret_market(summary_daily, summary_main=None, summary_24h=None, daily_panel=None, quality_df=None, windows=None, timestamp=None):
    """Try to load pre-generated interpretation. If not found or stale, save context for later."""
    if timestamp:
        fp = _summary_fingerprint(summary_daily)
        result = load_interpretation(timestamp, fingerprint=fp)
        if result:
            return result
        context = build_context(summary_daily, summary_main, summary_24h, daily_panel, quality_df, windows)
        if timestamp:
            ctx_path = save_context(context, timestamp)
            print(f'[AI] Context saved to {ctx_path}')
            print(f'[AI] Run: claude "read {ctx_path} and generate interpretation"')
            print(f'[AI] Then save to: {os.path.join(settings.OUTPUT_DIR, f"ai_interpretation_{timestamp}.json")}')
        else:
            print('[AI] No timestamp provided, skipping interpretation.')
    return None
