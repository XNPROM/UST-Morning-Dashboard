from __future__ import annotations

import pandas as pd


def cross_validate(
    intraday_panel: pd.DataFrame,
    daily_panel: pd.DataFrame,
    summary_main: pd.DataFrame,
) -> list[dict]:
    issues = []
    summary_assets = set(summary_main["Asset"].values) if "Asset" in summary_main.columns else set()

    # Yield up and futures price up at the same time is usually suspicious.
    yield_future_pairs = [
        ("UST 2Y", "TU 2Y Treasury Fut"),
        ("UST 5Y", "FV 5Y Treasury Fut"),
        ("UST 10Y", "TY 10Y Treasury Fut"),
        ("UST 30Y", "US 30Y Treasury Fut"),
    ]
    for yield_name, fut_name in yield_future_pairs:
        if yield_name in summary_assets and fut_name in summary_assets:
            y_chg = summary_main.loc[summary_main["Asset"] == yield_name, "Change"].values
            f_chg = summary_main.loc[summary_main["Asset"] == fut_name, "Change"].values
            if len(y_chg) > 0 and len(f_chg) > 0:
                y_val = float(y_chg[0])
                f_val = float(f_chg[0])
                if y_val * f_val > 0:
                    issues.append(
                        {
                            "Severity": "MEDIUM",
                            "Asset": f"{yield_name} vs {fut_name}",
                            "Issue": "收益率与期货同向变动，方向可能矛盾",
                            "Detail": f"yield change={y_val:.4f}, futures change={f_val:.4f}",
                        }
                    )

    # BEI should match nominal minus real yield.
    for tenor in ["5Y", "10Y", "30Y"]:
        nom_name = f"UST {tenor}"
        tips_name = f"TIPS real {tenor}"
        bei_name = f"BEI {tenor}"
        if all(col in intraday_panel.columns for col in [nom_name, tips_name, bei_name]):
            computed_bei = intraday_panel[nom_name] - intraday_panel[tips_name]
            diff = (intraday_panel[bei_name] - computed_bei).dropna().abs()
            if len(diff) > 0 and diff.max() > 0.05:
                issues.append(
                    {
                        "Severity": "HIGH",
                        "Asset": bei_name,
                        "Issue": "BEI 派生值与 Nominal-TIPS 差异过大",
                        "Detail": f"max_diff={diff.max():.4f}%, 可能是 TIPS 与 UST 时间戳未对齐",
                    }
                )

    if "CNH-CNY spread" in intraday_panel.columns:
        spread = intraday_panel["CNH-CNY spread"].dropna()
        if len(spread) > 0:
            median_spread = float(spread.median())
            spread_pips = abs(median_spread) * 10000
            if spread_pips > 1000:
                issues.append(
                    {
                        "Severity": "HIGH",
                        "Asset": "CNH-CNY spread",
                        "Issue": "CNH-CNY 价差过大，可能存在数据异常",
                        "Detail": f"median_spread={median_spread * 10000:.1f}pips",
                    }
                )
            elif spread_pips > 200:
                issues.append(
                    {
                        "Severity": "LOW",
                        "Asset": "CNH-CNY spread",
                        "Issue": f"CNH-CNY 价差偏宽（{median_spread * 10000:.1f}pips），需关注市场压力",
                        "Detail": f"median_spread={median_spread * 10000:.1f}pips (正常约 -50~200pips)",
                    }
                )

    if "DXY" in intraday_panel.columns and "EURUSD" in intraday_panel.columns:
        dxy_s = intraday_panel["DXY"].dropna()
        eurusd_s = intraday_panel["EURUSD"].dropna()
        aligned = pd.concat([dxy_s, eurusd_s], axis=1, join="inner").dropna()
        if len(aligned) >= 20:
            dxy_chg = aligned["DXY"].pct_change().dropna()
            eurusd_chg = aligned["EURUSD"].pct_change().dropna()
            corr = dxy_chg.tail(20).corr(eurusd_chg.tail(20))
            if pd.notna(corr) and corr > 0.3:
                issues.append(
                    {
                        "Severity": "LOW",
                        "Asset": "DXY vs EURUSD",
                        "Issue": "DXY 与 EURUSD 正相关异常（通常应为负相关）",
                        "Detail": f"corr={corr:.2f}, aligned_obs={len(aligned)}",
                    }
                )

    # Do not compare intraday and daily absolute levels directly.
    # The daily series is a business-date bucket, not a session-aligned timestamp,
    # so normal overnight moves would be mislabeled as data errors.
    return issues


def detect_anomalies(panel: pd.DataFrame) -> list[dict]:
    issues = []

    for col in panel.columns:
        s = panel[col].dropna()
        if len(s) < 20:
            continue

        ret = s.diff().dropna()
        if len(ret) > 10:
            std = float(ret.std())
            if std > 0:
                jumps = ret[ret.abs() > 3 * std]
                if len(jumps) > 0:
                    issues.append(
                        {
                            "Severity": "LOW",
                            "Asset": col,
                            "Issue": f"检测到 {len(jumps)} 个 3σ 以上跳变点",
                            "Detail": f"max_jump={float(jumps.abs().max()):.4f}, 3σ={3 * std:.4f}",
                        }
                    )

        zero_run = (s == 0).astype(int)
        max_zero_run = zero_run.groupby((zero_run != zero_run.shift()).cumsum()).sum().max()
        if max_zero_run > 10:
            issues.append(
                {
                    "Severity": "MEDIUM",
                    "Asset": col,
                    "Issue": f"连续零值点数 {max_zero_run}",
                    "Detail": "可能存在数据源异常",
                }
            )

    return issues


def sanity_check(panel: pd.DataFrame) -> list[dict]:
    issues = []
    ranges = {
        "UST 2Y": (0.0, 6.0),
        "UST 5Y": (0.0, 6.5),
        "UST 10Y": (0.0, 6.5),
        "UST 30Y": (0.0, 7.0),
        "TIPS real 5Y": (-2.0, 4.0),
        "TIPS real 10Y": (-2.0, 4.0),
        "TIPS real 30Y": (-1.0, 4.5),
        "BEI 5Y": (-1.0, 6.0),
        "BEI 10Y": (-1.0, 6.0),
        "BEI 30Y": (-1.0, 6.0),
        "DXY": (75, 130),
        "UST 2s10s spread": (-200, 350),
    }

    for name, (lo, hi) in ranges.items():
        if name in panel.columns:
            s = panel[name].dropna()
            if len(s) == 0:
                continue
            med = float(s.median())
            if med < lo or med > hi:
                issues.append(
                    {
                        "Severity": "HIGH",
                        "Asset": name,
                        "Issue": f"中位数 {med:.4f} 超出合理区间 [{lo}, {hi}]",
                        "Detail": f"median={med:.4f}",
                    }
                )

    return issues
