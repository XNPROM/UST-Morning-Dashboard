from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from analytics.summary import format_level, get_unit, get_order
from dates.windows import ReportWindows


SYSTEM_PROMPT = """你是深圳某券商固定收益研究团队的晨报分析师。你只基于提供的数据进行分析，不编造任何数字。如果数据不足以得出结论，明确说明。

严格规则：
- 引用任何数字时，必须与提供的数据完全一致，不得四舍五入或近似（如数据写3.57bp就不能写成3.6bp）
- 不得声称某个资产"突破"了某个点位，除非数据中的实际Level或High确实越过了该点位
- 不得推测数据中未出现的极值（如数据中USDJPY最高159.84，不能说"触及160"）
- 对每个关键判断，在括号中标注数据来源值，如"10Y收益率突破4.30%（4.3325%）"

你的分析风格：简洁、有观点、逻辑清晰。用中文撰写。"""


def _fmt_change(chg: float, unit: str) -> str:
    """Format a change value with the correct unit and scale."""
    if unit in ("yield_pct", "bei_pct"):
        return f"{chg * 100:.1f}bp"
    if unit == "spread_bp":
        return f"{chg:.1f}bp"
    if unit == "fx_jpy":
        return f"{chg * 100:.1f}pips"
    if unit in ("fx", "fixing_fx"):
        return f"{chg * 10000:.1f}pips"
    if unit == "fx_spread":
        return f"{chg * 10000:.1f}pips"
    return f"{chg:.2f}pts"


def _build_daily_stats_text(daily_panel: pd.DataFrame) -> str:
    if daily_panel.empty:
        return "（无日频数据）"

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
        pctile = float((s.rank(pct=True).iloc[-1])) * 100

        parts = [f"{col}: 当前{format_level(last, unit)}"]
        if pd.notna(chg_5d):
            parts.append(f"5d变化{_fmt_change(chg_5d, unit)}")
        if pd.notna(chg_20d):
            parts.append(f"20d变化{_fmt_change(chg_20d, unit)}")
        parts.append(f"60d百分位{pctile:.0f}%")
        lines.append("，".join(parts))

    return "\n".join(lines)


def _build_summary_text(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "（无摘要数据）"

    lines = []
    for _, r in summary.sort_values("Order").iterrows():
        lines.append(
            f"{r['Asset']}: {r['Level']}（{r['Change Text']}）"
        )
    return "\n".join(lines)


def _build_quality_text(quality_df: pd.DataFrame) -> str:
    if quality_df.empty:
        return "数据质量：无异常"
    if quality_df.iloc[0].get("Severity") == "OK":
        return "数据质量：无异常"
    lines = []
    for _, r in quality_df.iterrows():
        lines.append(f"[{r['Severity']}] {r['Asset']}: {r['Issue']} — {r['Detail']}")
    return "\n".join(lines)


def build_context(
    summary_main: pd.DataFrame,
    summary_24h: pd.DataFrame,
    daily_panel: pd.DataFrame,
    quality_df: pd.DataFrame,
    windows: ReportWindows,
) -> str:
    """Build the full prompt context for AI interpretation."""
    asof_str = windows.asof_dt.strftime("%Y-%m-%d %H:%M %Z")
    main_window_str = f"{windows.main_start.strftime('%m-%d %H:%M')} → {windows.main_end.strftime('%m-%d %H:%M')}"

    return f"""## 报告时间
锚定时间：{asof_str}
主窗口：{main_window_str}

## 今日数据概览（主窗口）
{_build_summary_text(summary_main)}

## 滚动24小时概览
{_build_summary_text(summary_24h)}

## 近60天走势摘要
{_build_daily_stats_text(daily_panel)}

## 数据质量检查
{_build_quality_text(quality_df)}

---

请从以下四个维度分析，每个维度 150-250 字，直接给出分析结论，不要重复数据：

### 1. 驱动因素归因
分析收益率变动的驱动来源：
- 实际利率 vs 通胀预期的贡献拆分（用 TIPS 和 BEI 数据）
- 风险偏好变化（用曲线形态、商品、汇率联动推断）
- 主要驱动因素排序

### 2. 关键点位与信号
识别需要关注的技术/结构信号：
- 收益率是否突破关键整数位或历史极值
- 曲线形态变化（倒挂、走陡、转折信号）
- 汇率关键位突破或回踩

### 3. 历史情景类比
在近60天数据中寻找类似形态：
- 当前曲线斜率/BEI 组合与近期历史对比
- 类似波动幅度和方向的历史案例
- 类似案例后的后续走势参考

### 4. 前瞻观点
今日需关注：
- 短期（1-3日）方向判断及置信度
- 人民币中间价预期（基于CNH和市场情绪）
- 需要关注的风险点"""


def save_context(context: str, timestamp: str) -> str:
    """Save context to file for Claude Code to read and interpret."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f"ai_context_{timestamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SYSTEM_PROMPT + "\n\n" + context)
    return path


def load_interpretation(date_str: str) -> dict[str, str] | None:
    """Load pre-generated interpretation from JSON file. Matches by date prefix (YYYYMMDD)."""
    # Try exact match first
    path = os.path.join(settings.OUTPUT_DIR, f"ai_interpretation_{date_str}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Try matching by date prefix (YYYYMMDD) — find latest file for the same day
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    candidates = sorted([
        fname for fname in os.listdir(settings.OUTPUT_DIR)
        if fname.startswith(f"ai_interpretation_{date_str[:8]}") and fname.endswith(".json")
    ], reverse=True)  # reverse sort = latest first
    for fname in candidates:
        try:
            with open(os.path.join(settings.OUTPUT_DIR, fname), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue

    return None


def save_interpretation(interpretation: dict[str, str], timestamp: str) -> str:
    """Save interpretation to JSON file."""
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, f"ai_interpretation_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(interpretation, f, ensure_ascii=False, indent=2)
    return path


def interpret_market(
    summary_main: pd.DataFrame,
    summary_24h: pd.DataFrame,
    daily_panel: pd.DataFrame,
    quality_df: pd.DataFrame,
    windows: ReportWindows,
    timestamp: str = "",
) -> dict[str, str] | None:
    """Try to load pre-generated interpretation. If not found, save context for later."""
    # First check if interpretation already exists
    if timestamp:
        result = load_interpretation(timestamp)
        if result:
            return result

    # No interpretation yet — save context for Claude Code to process
    context = build_context(summary_main, summary_24h, daily_panel, quality_df, windows)
    if timestamp:
        ctx_path = save_context(context, timestamp)
        print(f"[AI] Context saved to {ctx_path}")
        print(f"[AI] Run: claude \"read {ctx_path} and generate interpretation\"")
        print(f"[AI] Then save to: {os.path.join(settings.OUTPUT_DIR, f'ai_interpretation_{timestamp}.json')}")
    else:
        print("[AI] No timestamp provided, skipping interpretation.")

    return None
