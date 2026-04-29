# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

UST Morning Dashboard -- 每日深圳早 9 点复盘美债、美元、人民币与相关市场表现的晨间看板。数据来源为 LSEG Data Platform，AI 解读部分整合 Report Watch 外资研报库（`D:\Report Watch`）。输出物包括 HTML 报告、CSV 摘要与 AI 解读 JSON。

## 常用命令

```bash
pip install -r requirements.txt            # 安装依赖
python run_dashboard.py                    # 完整运行：拉数据+生成报告+推送
python run_dashboard.py --no-push          # 运行但不推送到 GitHub
python run_dashboard.py --date 2026-04-24 --no-push  # 指定业务日期调试
python run_dashboard.py --fail-on-blocking-quality    # CI 模式：阻断性质量问题返回非零退出码
python -m unittest discover -s tests -v   # 运行测试
```

## 每日执行顺序

1. `python run_dashboard.py --no-push`
2. 阅读 `reports/ai_context_YYYYMMDD_HHMM.txt`（内含外资研报摘要）
3. 基于上下文生成 AI 解读，保存为 `reports/ai_interpretation_YYYYMMDD_HHMM.json`（五段式：核心结论 / 市场表现 / 原因分析 / 后续观察 / 错误检查）
4. 再次运行 `python run_dashboard.py`（自动推送当次生成的报告文件）

## 架构

`run_dashboard.py` 是唯一入口，按顺序调用以下模块：

| 步骤 | 模块 | 职责 |
|------|------|------|
| 1 | `dates/windows.py` | 计算报告时间窗口，返回 `ReportWindows`（含 `history_start` 2 年日线窗口） |
| 2 | `auth/lseg_session.py` | 从 `.env` 读取 LSEG 凭据，管理 session（最多重试 3 次） |
| 3 | `data/fetch.py` | 按 RIC 与 field 回退顺序拉取 intraday + daily 数据 |
| 4 | `data/derived.py` | 计算衍生指标（利差、BEI、CNH-CNY 价差、Fixing Gap） |
| 5 | `data/validation.py` | 交叉校验、异常检测（3-sigma）、合理性判断 |
| 6 | `analytics/summary.py` | 生成摘要表；`summarize_daily_change()` 是收盘变动核心 |
| 7 | `analytics/quality.py` | 质量检查；HIGH 级问题阻断推送与 AI 解读 |
| 8 | `analytics/notes.py` | 生成一屏结论（基于 `summary_daily` 收盘口径） |
| 9 | `analytics/ai_interpreter.py` | 读取 Report Watch 研报 + 保存上下文 / 读取已有 AI 解读 JSON |
| 10 | `analytics/calendar.py` | 交易时段表与经济事件日历 |
| 11 | `charts/plotly_charts.py` | Plotly 图表生成（5 主题分区：Rates / Futures / FX / Commodities / Long-term） |
| 12 | `report/html_report.py` | 输出自包含 HTML（CSS 双列网格、CDN Plotly）与 CSV |
| 13 | `push/push_report.py` | 仅 `git add -f` 当次生成的文件，commit 并 push |

配置核心：`config/settings.py`（Settings dataclass、全局常量）、`config/assets.py`（AssetConfig、22 项基础资产 + 9 项衍生指标、RIC 定义、FIELD_SETS_BY_UNIT 回退映射）。

## 外部依赖：Report Watch

`analytics/ai_interpreter.py` 中的 `get_recent_macro_reports()` 从 `D:\Report Watch\.state\report_watch.sqlite3` 读取近 3 天外资研报 AI 摘要（Barclays / Goldman / UBS / Citi / HSBC / Nomura），按宏观关键词过滤后注入 AI 上下文的"近期外资研报摘要"板块。如果 Report Watch 数据库不存在，该功能静默降级为"（无外资研报数据）"，不会报错。

## 数据频率说明

- TIPS 系列（`US5YTIP=RR` 等）freq 设为 `'both'`，日线拉取使用 `B_YLD_1`/`A_YLD_1`（`MID_YLD_1` 日线 TIPS 历史过少，被 `fetch_one` 稀疏跳过逻辑自动跳过）
- 日线面板通过 `interval='daily'` 拉取 2 年历史，所有摘要、变动、图表均统一收盘口径
- `ffill limit=12` 覆盖 Globex 1 小时结算休市（12 x 5min bars）
- `data/fetch.py` 中 `fetch_one` 对日线请求有稀疏数据跳过：若返回行数远低于日期跨度，自动尝试下一个 field set

## 报告产物与 Git 策略

`reports/` 目录在 `.gitignore` 中被排除。`push_report.py` 使用 `git add -f` 仅推送当次运行产生的文件（按时间戳匹配），防止历史产物在 Git 中堆积。本地 `reports/` 下的旧文件由 `cleanup_old_reports()` 按 `CLEANUP_DAYS`（默认 90 天）自动清理。

## AI 解读 JSON 格式

五段式结构，键名：`conclusion` / `performance` / `causes` / `watchlist` / `corrections`。`causes` 段要求引用 Report Watch 中的实际研报并标注来源。兼容旧版三段式（`changes` / `reasons` / `synthesis`），`html_report.py` 自动回退渲染。`_fingerprint` 字段用于检测摘要数据变化后跳过过时的解读缓存。

## 关键约束

- `config/assets.py` 中的 `ASSETS` 与 `FIELD_SETS_BY_UNIT` 是数据拉取核心，RIC 回退顺序保持不变
- `data/fetch.py` 中的 `looks_valid()`、`_series_from_history()` 与稀疏跳过逻辑保持不变
- 所有时间统一使用 `Asia/Shanghai`，`ensure_dt_index()` 时区处理逻辑保持不变
- AI 解读采用人工补写方式，不调用外部大模型接口
- `load_dotenv()` 仅在 `run_dashboard.py` 调用一次
- LSEG session 必须在 `try/finally` 中关闭
- 日志 DataFrame 合并仅在 `run_dashboard.py` 内执行一次
- HIGH 级质量问题阻断 AI 解读加载与 GitHub 推送

## 凭据

`.env` 文件包含：`LSEG_APP_KEY`、`LSEG_LDP_LOGIN`、`LSEG_LDP_PASSWORD`

## Windows 定时任务

`run_dashboard_9am.bat` 供 Windows Task Scheduler 每日 09:00 调用，日志写入 `logs/dashboard.log`。

## 回复规范

默认语言使用简体中文。代码标识符、CLI 命令、日志和错误消息保留原始语言。

### 风格

使用规范的现代书面中文，语感接近技术文档编写者之间的同行讨论。句式结构完整，论述平实克制，信息密度高。回复第一句话进入正文，篇幅根据问题复杂度自然伸缩。

### 禁忌

- 禁止在代码和文档中使用 Emoji
- 未获得明确许可前，禁止创建文档
- 禁止使用互联网黑话及排比句式（禁用词汇包括但不限于：`结论` `口径` `稳` `坑` `抓手` `路径` `落地` `定性` `倒逼` `复现` `粒度` `收敛` `聚焦` `赋能` `拉齐` `对齐` `打通` `闭环` `沉淀` `透出` `链路` `心智` `触达` `迭代`）
- 避免使用"你""我""他"等人称代词
- 使用正向表达，避免反转句式
- 回复以陈述直接结尾，避免反问或追问
