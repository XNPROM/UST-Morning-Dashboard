# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

UST Morning Dashboard — 每日深圳早9点复盘美债/汇率市场的晨间看板。从 LSEG Data Platform 拉取数据，生成 HTML 报告，AI 辅助解读，推送 GitHub。

## Commands

```bash
# 完整运行（拉数据+生成报告+推送）
python run_dashboard.py

# 运行但不推送
python run_dashboard.py --no-push

# 安装依赖
pip install -r requirements.txt
```

## Workflow

每天早会的完整流程：
1. `python run_dashboard.py --no-push` → 拉数据、生成报告、保存 AI 上下文文件
2. Codex 读取 `reports/ai_context_YYYYMMDD*.txt`，生成四维解读（归因/信号/类比/前瞻）
3. 将解读保存到 `reports/ai_interpretation_YYYYMMDD.json`
4. `python run_dashboard.py` → 报告带 AI 解读 + 自动推 GitHub

## Architecture

`run_dashboard.py` 是唯一入口，按顺序调用：

1. `dates/windows.py` — 计算报告时间窗口，返回 `ReportWindows` dataclass
2. `auth/lseg_session.py` — 从 `.env` 读 LSEG 凭据，开/关 session
3. `data/fetch.py` — 用 RIC/field 回退链拉取 LSEG 数据
4. `data/derived.py` — 计算衍生指标（曲线利差、BEI、CNH-CNY 价差等）
5. `data/validation.py` — 交叉校验、异常检测、合理性判断
6. `analytics/summary.py` — 生成摘要表（level/change/bp/pips 格式化）
7. `analytics/quality.py` — 数据质量检查 + A/B/C 评级（按 section 分）
8. `analytics/notes.py` — 一屏结论文字
9. `analytics/ai_interpreter.py` — 两阶段：保存上下文 / 按日期加载已有解读 JSON
10. `analytics/calendar.py` — 交易时段表、经济数据日历
11. `charts/plotly_charts.py` — Plotly 图表（含滚动24h图表）
12. `report/html_report.py` — 生成 HTML + CSV（含 AI 解读区块、24h折叠区、质量评级）
13. `push/push_report.py` — git push HTML 报告到 GitHub

## Key Design Decisions

- `config/assets.py` 中 `ASSETS` 列表和 `FIELD_SETS_BY_UNIT` 是数据拉取的核心，RIC 回退顺序不能改
- `data/fetch.py` 的 `looks_valid()` 和 `_series_from_history()` 验证逻辑必须保留
- 时区处理：所有时间统一为 `Asia/Shanghai`，`ensure_dt_index` 的 tz_localize/tz_convert 逻辑不可修改
- AI 解读由 Codex 手动生成，不需要外部 API。解读文件按日期前缀匹配，同一天取最新
- LSEG session 必须在 `try/finally` 中关闭（`session = None` 初始化防止 UnboundLocalError）
- `load_dotenv()` 只在 `run_dashboard.py` 调用一次
- 日志 DataFrame 合并只做一次（在 `run_dashboard.py` 中），传入 `generate_html_report` 复用

## Credentials

`.env` 文件（gitignored）包含：
- `LSEG_APP_KEY`, `LSEG_LDP_LOGIN`, `LSEG_LDP_PASSWORD` — LSEG 数据平台

## Windows Scheduling

`run_dashboard_9am.bat` 供 Windows Task Scheduler 每天 09:00 调用，日志写入 `logs/dashboard.log`。
