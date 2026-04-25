from __future__ import annotations

import numpy as np
import pandas as pd

from config.assets import (
    ORDER_BY_NAME, UNIT_BY_NAME, GROUP_BY_NAME, SECTION_BY_NAME,
)


def get_unit(asset: str) -> str:
    return UNIT_BY_NAME.get(asset, "index")


def get_group(asset: str) -> str:
    return GROUP_BY_NAME.get(asset, "Other")


def get_section(asset: str) -> str:
    return SECTION_BY_NAME.get(asset, "Other")


def get_order(asset: str) -> int:
    return ORDER_BY_NAME.get(asset, 9999)


def change_display(first: float, last: float, unit: str):
    chg = last - first
    pct = chg / first if pd.notna(first) and first != 0 else np.nan

    if unit in ("yield_pct", "bei_pct"):
        return chg, chg * 100, "bp", np.nan
    if unit == "spread_bp":
        return chg, chg, "bp", np.nan
    if unit == "fx_jpy":
        return chg, chg * 100, "pips", pct
    if unit in ("fx", "fixing_fx", "fx_spread"):
        return chg, chg * 10000, "pips", pct if unit == "fx" else np.nan
    if unit in ("index", "futures_price", "commodity"):
        return chg, chg, "pts", pct
    return chg, chg, "pts", pct


def format_level(x: float, unit: str) -> str:
    if pd.isna(x):
        return ""
    if unit in ("yield_pct", "bei_pct"):
        return f"{x:.4f}%"
    if unit == "spread_bp":
        return f"{x:.2f}bp"
    if unit in ("fx", "fixing_fx"):
        return f"{x:.4f}"
    if unit == "fx_jpy":
        return f"{x:.3f}"
    if unit == "fx_spread":
        return f"{x*10000:.1f}pips"
    if unit in ("futures_price", "commodity", "index"):
        return f"{x:.4f}"
    return f"{x:.4f}"


def format_change(x: float, unit: str) -> str:
    if pd.isna(x):
        return ""
    sign = "+" if x > 0 else ""
    if unit in ("bp", "pips"):
        return f"{sign}{x:.2f}{unit}"
    if unit == "pts":
        return f"{sign}{x:.4f}"
    return f"{sign}{x:.4f}"


def summarize_panel(panel: pd.DataFrame, window_name: str) -> pd.DataFrame:
    rows = []
    if panel.empty:
        return pd.DataFrame()

    for col in sorted(panel.columns, key=get_order):
        s = panel[col].dropna()
        if len(s) < 2:
            continue
        unit = get_unit(col)
        first, last = float(s.iloc[0]), float(s.iloc[-1])
        raw_chg, chg_disp, chg_unit, pct = change_display(first, last, unit)

        rows.append({
            "Window": window_name,
            "Section": get_section(col),
            "Group": get_group(col),
            "Asset": col,
            "First Time": s.index[0].strftime("%Y-%m-%d %H:%M"),
            "Last Time": s.index[-1].strftime("%Y-%m-%d %H:%M"),
            "First": first,
            "Last": last,
            "Level": format_level(last, unit),
            "Change": raw_chg,
            "Change Display": chg_disp,
            "Change Text": format_change(chg_disp, chg_unit),
            "Change Unit": chg_unit,
            "% Change": pct,
            "% Change Text": "" if pd.isna(pct) else f"{pct:+.2%}",
            "High": float(s.max()),
            "Low": float(s.min()),
            "Obs": int(s.notna().sum()),
            "Order": get_order(col),
        })

    return pd.DataFrame(rows).sort_values(["Order"]).reset_index(drop=True)


def rows_by_section(summary: pd.DataFrame, sections: list[str]) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary[summary["Section"].isin(sections)].copy()


def lookup(summary: pd.DataFrame, asset: str):
    if summary.empty or asset not in set(summary["Asset"]):
        return None
    return summary.loc[summary["Asset"].eq(asset)].iloc[0]


def chg(summary: pd.DataFrame, asset: str) -> str:
    r = lookup(summary, asset)
    if r is None:
        return "n/a"
    return f"{r['Level']}（{r['Change Text']}）"


def latest_fixing_info(daily_panel: pd.DataFrame, target_fixing_date) -> dict:
    if "USD/CNY fixing" not in daily_panel.columns:
        return {"status": "missing", "detail": "USD/CNY fixing not available"}
    s = daily_panel["USD/CNY fixing"].dropna()
    if s.empty:
        return {"status": "missing", "detail": "USD/CNY fixing empty"}
    last_date = s.index[-1].date()
    prev = s.iloc[-2] if len(s) >= 2 else np.nan
    last = s.iloc[-1]
    chg_pips = (last - prev) * 10000 if pd.notna(prev) else np.nan
    stale = last_date != target_fixing_date
    return {
        "status": "stale" if stale else "ok",
        "last_date": last_date,
        "target_date": target_fixing_date,
        "last": float(last),
        "chg_pips": float(chg_pips) if pd.notna(chg_pips) else np.nan,
        "detail": f"latest={last_date}, target={target_fixing_date}, level={last:.4f}",
    }
