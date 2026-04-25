# UST Morning Dashboard

每日深圳早 9 点复盘美债、美元、人民币与大宗商品的晨间看板。

项目会从 LSEG Data Platform 拉取行情，生成 HTML 报告、CSV 摘要和质量检查结果；AI 解读采用“先保存上下文，再人工补 JSON，再重跑”的两阶段流程。

## Local Setup

1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

2. 复制环境变量模板并填入 LSEG 凭据

```bash
copy .env.example .env
```

3. 按需运行

```bash
# 拉数据、生成报告，但不推送
python run_dashboard.py --no-push

# 生成报告并尝试 git push 最新 HTML
python run_dashboard.py

# 回补指定业务日
python run_dashboard.py --date 2026-04-23 --no-push
```

## Daily Workflow

1. 先跑 `python run_dashboard.py --no-push`
2. 打开 `reports/ai_context_YYYYMMDD_HHMM.txt`
3. 生成人工 AI 解读，保存为 `reports/ai_interpretation_YYYYMMDD_HHMM.json`
4. 再跑 `python run_dashboard.py`

同一天支持多次重跑，工件文件名前缀会跟业务日期走，而不是跟运行当天走。

## Quality Gate

- 报告始终会先生成出来，方便排查。
- 如果存在阻断级质量问题，默认会阻止自动 `git push`。
- CI/定时任务里可以加 `--fail-on-blocking-quality`，让任务直接失败。
- 如需强制发布，可显式传 `--allow-blocking-quality`。

## GitHub Actions

仓库内置两个 workflow：

- `CI`：在 push / pull request 时运行单测
- `Dashboard`：支持工作日定时跑和手动回补

### Required Secrets

在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中配置：

- `LSEG_APP_KEY`
- `LSEG_LDP_LOGIN`
- `LSEG_LDP_PASSWORD`

### Dashboard Workflow Behavior

- 工作日北京时间约 09:05 自动运行
- 也可以手动触发，支持传入 `report_date`
- 会上传 HTML / CSV / 日志 / AI context 等产物
- 当 `push_report=true` 且质量闸门通过时，会把最新 HTML 推回仓库

## Windows Scheduler

本地 Windows 定时任务可调用：

```bat
run_dashboard_9am.bat
```

默认日志写入 `logs/dashboard.log`。

## Repository Notes

- `run_dashboard.py` 是唯一入口
- `config/assets.py` 中的 RIC 回退顺序不要随意调整
- 所有时间统一使用 `Asia/Shanghai`
- LSEG session 必须始终在 `finally` 中关闭
