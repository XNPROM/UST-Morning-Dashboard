from __future__ import annotations

import pandas as pd

from config.assets import SECTION_BY_NAME
from analytics.summary import latest_fixing_info


def data_quality_checks(
    intraday_log: pd.DataFrame,
    daily_log: pd.DataFrame,
    main_panel: pd.DataFrame,
    daily_panel: pd.DataFrame,
    target_fixing_date,
    validation_issues: list[dict] | None = None,
) -> pd.DataFrame:
    issues = []

    # RIC fetch failures
    all_logs = pd.concat([intraday_log.assign(freq="5min"), daily_log.assign(freq="daily")], ignore_index=True)
    for _, r in all_logs.iterrows():
        if r["status"] != "ok":
            issues.append({
                "Severity": "HIGH" if r["unit"] in ("yield_pct", "fx", "fx_jpy", "fixing_fx") else "MEDIUM",
                "Asset": r["name"],
                "Issue": f"{r['freq']} 拉取失败/无效",
                "Detail": str(r["error"])[:180],
            })

    # Yield sanity: looks like price?
    for col in ["UST 2Y", "UST 5Y", "UST 10Y", "UST 30Y", "TIPS real 5Y", "TIPS real 10Y", "TIPS real 30Y"]:
        if col in main_panel.columns:
            med = main_panel[col].dropna().median()
            if pd.notna(med) and med > 20:
                issues.append({"Severity": "HIGH", "Asset": col, "Issue": "收益率看起来像价格", "Detail": f"median={med:.4f}"})

    # CNH-CNY comparable samples
    if "CNH-CNY spread" in main_panel.columns:
        obs = int(main_panel["CNH-CNY spread"].notna().sum())
        if obs < 80:
            issues.append({
                "Severity": "MEDIUM",
                "Asset": "CNH-CNY spread",
                "Issue": "CNY/CNH可比样本偏少",
                "Detail": f"obs={obs}; CNY在岸交易时段较短，spread只在共同时间戳比较。",
            })

    # Fixing info
    fix = latest_fixing_info(daily_panel, target_fixing_date)
    if fix["status"] == "missing":
        issues.append({"Severity": "MEDIUM", "Asset": "USD/CNY fixing", "Issue": "中间价缺失", "Detail": fix["detail"]})
    elif fix["status"] == "stale":
        issues.append({
            "Severity": "LOW",
            "Asset": "USD/CNY fixing",
            "Issue": "中间价日期非目标日期",
            "Detail": fix["detail"] + "；9:15前运行通常显示上一交易日中间价。",
        })

    # Merge validation issues (includes BEI sanity from validation.sanity_check)
    if validation_issues:
        issues.extend(validation_issues)

    if not issues:
        return pd.DataFrame([{
            "Severity": "OK",
            "Asset": "ALL",
            "Issue": "No major issue",
            "Detail": "核心字段口径和数据完整性未发现重大异常。",
        }])

    return pd.DataFrame(issues)


def compute_quality_grade(quality_df: pd.DataFrame, sections: list[str] | None = None) -> dict[str, str]:
    """Compute A/B/C grade per section based on quality issues, filtered per section."""
    grade_map = {}
    all_sections = set(SECTION_BY_NAME.values())
    if sections:
        all_sections = set(sections)

    # Build reverse lookup: asset -> section
    ASSET_SECTION = {name: sec for name, sec in SECTION_BY_NAME.items()}
    KNOWN_ASSETS = sorted(ASSET_SECTION.keys(), key=len, reverse=True)

    def sections_for_issue(asset: str) -> set[str]:
        if asset == "ALL":
            return set(all_sections)
        if asset in ASSET_SECTION:
            return {ASSET_SECTION[asset]}
        return {ASSET_SECTION[name] for name in KNOWN_ASSETS if name in asset}

    for sec in all_sections:
        if quality_df.empty:
            grade_map[sec] = "A"
            continue

        sec_issues = quality_df[
            quality_df["Severity"].isin(["HIGH", "MEDIUM"])
            & quality_df["Asset"].astype(str).map(lambda asset: sec in sections_for_issue(asset))
        ]
        high_count = len(sec_issues[sec_issues["Severity"] == "HIGH"])
        medium_count = len(sec_issues[sec_issues["Severity"] == "MEDIUM"])

        if high_count > 0:
            grade_map[sec] = "C"
        elif medium_count > 2:
            grade_map[sec] = "C"
        elif medium_count > 0:
            grade_map[sec] = "B"
        else:
            grade_map[sec] = "A"

    return grade_map
