# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UST Morning Dashboard — 每日深圳早9点复盘美债/汇率市场的晨间看板。从 LSEG Data Platform 拉取数据，生成 HTML 报告，AI 辅助解读，推送 GitHub。

## Commands

```bash
# 完整运行（拉数据+生成报告+推送）
python run_dashboard.py

# 运行但不推送
python run_dashboard.py --no-push

# 指定日期运行（调试用，anchor 到该日 09:00 CST）
python run_dashboard.py --date 2026-04-24

# 安装依赖
pip install -r requirements.txt
```

## Workflow

每天早会的完整流程：
1. `python run_dashboard.py --no-push` → 拉数据、生成报告、保存 AI 上下文文件
2. Claude Code 读取 `reports/ai_context_YYYYMMDD*.txt`，生成四维解读（归因/信号/类比/前瞻）
3. 将解读保存到 `reports/ai_interpretation_YYYYMMDD.json`
4. `python run_dashboard.py` → 报告带 AI 解读 + 自动推 GitHub

## Architecture

`run_dashboard.py` 是唯一入口，按顺序调用 15 步：

1. `dates/windows.py` — `ReportWindows` dataclass，anchor 到 09:00 CST，自动回退到最近 CN 交易日
2. `auth/lseg_session.py` — `.env` 读 LSEG 凭据，platform 模式（非 desktop），3 次重试
3. `data/fetch.py` — RIC x Field-Set 笛卡尔积回退（详见下文）
4. `data/derived.py` — 9 个衍生指标（2s10s/5s10s/5s30s 利差、BEI 5Y/10Y/30Y、CNH-CNY、CNY/CNH 偏离中间价）
5. `data/validation.py` — 三层校验：cross_validate / detect_anomalies / sanity_check
6. `analytics/summary.py` — unit-aware 格式化（详见下文）
7. `analytics/quality.py` — 按 section 评 A/B/C 级
8. `analytics/notes.py` — 一屏结论文字
9. `analytics/ai_interpreter.py` — 两阶段：保存上下文 / 按日期加载已有解读 JSON
10. `analytics/calendar.py` — 交易时段表、经济数据日历
11. `charts/plotly_charts.py` — Plotly 图表（主面板 ~10 图 + 24h/NY 各 2 图）
12. `report/html_report.py` — HTML + CSV，含 AI 解读区块、折叠区、质量评级
13. `push/push_report.py` — `git push origin HEAD`，失败不致命
14. 清理 >14 天旧报告
15. Push（`--no-push` 时跳过）

## Key Design Decisions

### RIC x Field-Set 笛卡尔积回退

`config/assets.py` 中每个 `AssetConfig.rics` 是有序回退链（如 `cnyfix` 有 5 个 RIC），`FIELD_SETS_BY_UNIT` 按 unit 定义有序 field-set 列表（如 `yield_pct` 有 8 级）。`data/fetch.py` 的 `fetch_one()` 遍历所有组合，每次用 `looks_valid()` 验证中位数合理性。最坏情况一个 asset 调 16 次 LSEG API。**不要修改 RIC 回退顺序或删减 field-set 级别**。

### Unit-Aware 格式化

`unit` 字符串贯穿整个格式化链：`FIELD_SETS_BY_UNIT` → `looks_valid()` → `change_display()` → `format_level()` → 验证阈值。添加新 unit 类型需同时改这五处。现有 unit 及格式：
- `yield_pct` / `bei_pct`: level `4.3325%`, change `+12.50bp`（raw × 100）
- `spread_bp`: level `25.00bp`, change `+3.20bp`（raw 即 bp）
- `fx` / `fixing_fx`: level `7.2450`, change `+15.0pips`（raw × 10000）
- `fx_jpy`: change raw × 100
- `fx_spread`: level `150.0pips`, change raw × 10000
- `futures_price` / `commodity` / `index`: change `+1.2500pts`（raw）

### 时区纪律

所有时间统一 `Asia/Shanghai`，`ensure_dt_index` 处理 DST（`nonexistent="shift_forward"`, `ambiguous="NaT"`）。**tz_localize/tz_convert 逻辑不可修改**。

### 解耦 AI 解读

Dashboard 不调 LLM API。`ai_interpreter.py` 要么加载已有 JSON，要么保存 context txt 等人工用 Claude Code 生成。解读 JSON 4 key: `attribution`, `key_levels`, `historical_analogy`, `outlook`。文件按日期前缀匹配，同一天取最新。

### 交易日历

`dates/windows.py` 用 `pandas_market_calendars`（XSHG/XNYS），支持 `CN_EXTRA_WORKDAYS`（调休补班）和 `CN_HOLIDAY_OVERRIDES`。`prev_market_day()` 最多回搜 30 天。库不可用时退化为 Mon-Fri。

### 其他约束

- `load_dotenv()` 只在 `run_dashboard.py` 调一次
- LSEG session 必须在 `try/finally` 中关闭，`session = None` 初始化防 UnboundLocalError
- 日志 DataFrame 合并只做一次，传入 `generate_html_report` 复用
- `_series_from_history()` 对 yield 优先取 bid/ask mid，对非 yield 优先取 BID/ASK
- `_flatten_columns()` 处理 LSEG SDK 返回 MultiIndex 和 flat column 两种情况
- 多处 `try/except` 兼容不同 LSEG SDK 版本（`signon_control`、`set_default()`）

## Credentials

`.env` 文件（gitignored）包含：
- `LSEG_APP_KEY`, `LSEG_LDP_LOGIN`, `LSEG_LDP_PASSWORD` — LSEG 数据平台

## Windows Scheduling

`run_dashboard_9am.bat` 激活 `D:\9amust\venv`，日志追加到 `logs\dashboard.log`。供 Task Scheduler 每天 09:00 调用。
