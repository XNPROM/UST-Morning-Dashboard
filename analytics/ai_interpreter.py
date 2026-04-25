# Source Generated with Decompyle++
# File: ai_interpreter.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import json
import os
from datetime import datetime
import numpy as np
import pandas as pd
from config.settings import settings
from analytics.summary import format_level, get_unit, get_order
from dates.windows import ReportWindows
SYSTEM_PROMPT = '你是深圳某券商固定收益研究团队的晨报分析师。你只基于提供的数据进行分析，不编造任何数字。如果数据不足以支持明确判断，应当明确说明数据仍需继续观察。\n\n严格规则：\n- 引用任何数字时，必须与提供的数据完全一致，不得四舍五入或近似（如数据写3.57bp就不能写成3.6bp）\n- 不得声称某个资产"突破"了某个点位，除非数据中的实际Level或High确实越过了该点位\
n- 不得推测数据中未出现的极值（如数据中USDJPY最高159.84，不能说"触及160"）\
n- 对每个关键判断，在括号中标注数据来源值，如"10Y收益率高于4.30%（4.3325%）"\
\n\n写作要求：\n- 使用规范书面中文，句子完整，避免口语化表达、夸张语气和交易台行话\
n- 每段先写观察到的变化，再解释背后的分项结构，最后写仍需继续观察的事项\
n- 文字应当克制、清晰，减少机械重复，不使用项目符号\
n- 如果历史参照不足，明确写出"近阶段可比样本有限"\
\n\n你的分析风格：简洁、审慎、逻辑清晰。用中文撰写。'


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


def build_context(summary_main, summary_24h = None, daily_panel = None, quality_df = None, windows = None):
    """Build the full prompt context for AI interpretation."""
    asof_str = windows.asof_dt.strftime('%Y-%m-%d %H:%M %Z')
    main_window_str = f'{windows.main_start.strftime("%m-%d %H:%M")} -> {windows.main_end.strftime("%m-%d %H:%M")}'
    return f'## 报告时间\
n锚定时间：{asof_str}\
n主窗口：{main_window_str}\
\n\n## 今日数据概览（主窗口）\
\n{_build_summary_text(summary_main)}\
\n\n## 滚动24小时概览\
\n{_build_summary_text(summary_24h)}\
\n\n## 近60天走势摘要\
\n{_build_daily_stats_text(daily_panel)}\
\n\n## 数据质量检查\
\n{_build_quality_text(quality_df)}\
\n\n---\
\n\n请围绕以下四个方面分别撰写 120-220 字。文字应以分析为主，减少机械复述，所有数字都必须与上文完全一致：\
\n\n### 1. 变化归因\
n说明收益率与相关资产变化的主要来源：\
\n- 实际利率 vs 通胀预期的贡献拆分（用 TIPS 和 BEI 数据）\
\n- 市场偏好变化（用曲线形态、商品、汇率联动推断）\
\n- 主要驱动因素排序\
\n\n### 2. 关键价位与观察信号\
n写出当前最值得留意的价位、斜率和联动指标：\
\n- 收益率相对整数位或近期高低点的位置\
\n- 曲线形态变化\
\n- 汇率与商品的同步变化\
\n\n### 3. 近阶段历史参照\
n在近60天数据中寻找相近的结构组合：\
\n- 当前曲线斜率与 BEI 组合相对近期历史的位置\
\n- 可以参照的相近样本\
\n- 样本有限时，明确说明比较边界\
\n\n### 4. 短线观察\
n今日可继续观察：\
\n- 未来一至三个交易日的方向判断及依据\
\n- 人民币中间价与离在岸价差\
\n- 仍需继续核对或跟踪的事项'


def save_context(context = None, timestamp = None):
    """Save context to file for Claude Code to read and interpret."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f'ai_context_{timestamp}.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(context)
    return path


def load_interpretation(date_str = None):
    """Load pre-generated interpretation from JSON file. Matches by date prefix (YYYYMMDD)."""
    if not os.path.exists(settings.OUTPUT_DIR):
        return None
    for fname in os.listdir(settings.OUTPUT_DIR):
        if fname.startswith('ai_interpretation_') and fname.endswith('.json'):
            if date_str and fname.startswith('ai_interpretation_' + date_str[:8]):
                path = os.path.join(settings.OUTPUT_DIR, fname)
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
    return None


def save_interpretation(interpretation = None, timestamp = None):
    """Save interpretation to JSON file."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f'ai_interpretation_{timestamp}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(interpretation, f, ensure_ascii=False, indent=2)
    return path


def interpret_market(summary_main, summary_24h = None, daily_panel = None, quality_df = None, windows = None, timestamp = None):
    """Try to load pre-generated interpretation. If not found, save context for later."""
    if timestamp:
        result = load_interpretation(timestamp)
        if result:
            return result
        context = build_context(summary_main, summary_24h, daily_panel, quality_df, windows)
        if timestamp:
            ctx_path = save_context(context, timestamp)
            print(f'[AI] Context saved to {ctx_path}')
            print(f'[AI] Run: claude "read {ctx_path} and generate interpretation"')
            print(f'[AI] Then save to: {os.path.join(settings.OUTPUT_DIR, f"ai_interpretation_{timestamp}.json")}')
        else:
            print('[AI] No timestamp provided, skipping interpretation.')
    return None
