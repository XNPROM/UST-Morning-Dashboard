# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

UST Morning Dashboard — 每日深圳早 9 点复盘美债、美元、人民币与相关市场表现的晨间看板。数据来源为 LSEG Data Platform，输出物包括 HTML 报告、CSV 摘要、AI 解读上下文文件与人工补写后的 AI 解读 JSON。

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
2. 阅读 `reports/ai_context_YYYYMMDD_HHMM.txt`
3. 生成 AI 解读，保存为 `reports/ai_interpretation_YYYYMMDD_HHMM.json`
4. 再次运行 `python run_dashboard.py`

## 架构

`run_dashboard.py` 是唯一入口，按顺序调用以下模块：

| 步骤 | 模块 | 职责 |
|------|------|------|
| 1 | `dates/windows.py` | 计算报告时间窗口，返回 `ReportWindows` |
| 2 | `auth/lseg_session.py` | 从 `.env` 读取 LSEG 凭据，管理 session（最多重试 3 次） |
| 3 | `data/fetch.py` | 按 RIC 与 field 回退顺序拉取数据 |
| 4 | `data/derived.py` | 计算衍生指标（利差、BEI、CNH-CNY 价差、Fixing Gap） |
| 5 | `data/validation.py` | 交叉校验、异常检测（3-sigma）、合理性判断 |
| 6 | `analytics/summary.py` | 生成摘要表 |
| 7 | `analytics/quality.py` | 质量检查与分区 A/B/C 评级；HIGH 级问题阻断推送 |
| 8 | `analytics/notes.py` | 生成一屏结论 |
| 9 | `analytics/ai_interpreter.py` | 保存上下文文件或读取已有 AI 解读 JSON |
| 10 | `analytics/calendar.py` | 交易时段表与经济事件日历 |
| 11 | `charts/plotly_charts.py` | Plotly 图表生成 |
| 12 | `report/html_report.py` | 输出自包含 HTML（内嵌 CSS、CDN Plotly）与 CSV |
| 13 | `push/push_report.py` | Git add/commit/push 报告文件 |

配置核心：`config/settings.py`（Settings dataclass、全局常量）、`config/assets.py`（AssetConfig、22 项基础资产 + 9 项衍生指标、RIC 定义、FIELD_SETS_BY_UNIT 回退映射）。

## 关键约束

- `config/assets.py` 中的 `ASSETS` 与 `FIELD_SETS_BY_UNIT` 是数据拉取核心，RIC 回退顺序保持不变
- `data/fetch.py` 中的 `looks_valid()` 与 `_series_from_history()` 校验逻辑保持不变
- 所有时间统一使用 `Asia/Shanghai`，`ensure_dt_index()` 时区处理逻辑保持不变
- AI 解读采用人工补写方式，不调用外部大模型接口
- `load_dotenv()` 仅在 `run_dashboard.py` 调用一次
- LSEG session 必须在 `try/finally` 中关闭
- 日志 DataFrame 合并仅在 `run_dashboard.py` 内执行一次
- HIGH 级质量问题阻断 AI 解读加载与 GitHub 推送
- 涉及网页、页面样式、信息层次、交互与视觉设计的任务时，默认遵循已安装的 `ui-ux-pro-max` skill 规则；技能目录为 `C:\Users\prime\.codex\skills\ui-ux-pro-max`

## 凭据

`.env` 文件包含：`LSEG_APP_KEY`、`LSEG_LDP_LOGIN`、`LSEG_LDP_PASSWORD`、`ZHIPU_API_KEY`（可选）

## Windows 定时任务

`run_dashboard_9am.bat` 供 Windows Task Scheduler 每日 09:00 调用，日志写入 `logs/dashboard.log`。

## GitHub Actions

- `.github/workflows/ci.yml`：push/PR 时运行测试
- `.github/workflows/dashboard.yml`：工作日 01:05 UTC 自动生成报告

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
