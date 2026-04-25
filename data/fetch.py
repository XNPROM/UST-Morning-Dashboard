from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from config.assets import (
    AssetConfig, FIELD_SETS_BY_UNIT, YIELD_FIELD_HINTS, PRICE_FIELD_HINTS,
)


def to_lseg_time(dt: datetime) -> str:
    return dt.astimezone(settings.REPORT_TZ).isoformat(timespec="seconds")


def ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    if getattr(out.index, "tz", None) is None:
        out.index = out.index.tz_localize(
            settings.REPORT_TZ, nonexistent="shift_forward", ambiguous="NaT"
        )
    else:
        out.index = out.index.tz_convert(settings.REPORT_TZ)
    return out.sort_index()


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [
            "|".join([str(x) for x in tup if str(x) != ""]) for tup in out.columns
        ]
    else:
        out.columns = [str(c) for c in out.columns]
    return out


def _series_from_history(
    df: pd.DataFrame, requested_fields, unit: str
) -> tuple[pd.Series, str]:
    if df is None or len(df) == 0:
        return pd.Series(dtype=float), ""

    df = ensure_dt_index(_flatten_columns(df))
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(how="all")
    if df.empty:
        return pd.Series(dtype=float), ""

    upper_cols = {c.upper(): c for c in df.columns}
    # For yield-type assets, prioritize yield-specific bid/ask over generic BID/ASK
    if unit in ("yield_pct", "bei_pct"):
        bid_ask_order = [
            ("B_YLD_1", "A_YLD_1"),
            ("ISMA_B_YLD", "ISMA_A_YLD"),
            ("BID", "ASK"),
        ]
    else:
        bid_ask_order = [
            ("BID", "ASK"),
            ("B_YLD_1", "A_YLD_1"),
            ("ISMA_B_YLD", "ISMA_A_YLD"),
        ]
    for bid_name, ask_name in bid_ask_order:
        b = upper_cols.get(bid_name)
        a = upper_cols.get(ask_name)
        if b and a:
            s = df[[b, a]].mean(axis=1)
            return s.dropna(), f"mid({b},{a})"

    if requested_fields:
        for f in requested_fields:
            for c in df.columns:
                if f.upper() in c.upper():
                    return df[c].dropna(), c

    hints = YIELD_FIELD_HINTS if unit == "yield_pct" else PRICE_FIELD_HINTS
    for h in hints:
        for c in df.columns:
            if h in c.upper():
                return df[c].dropna(), c

    c = df.columns[0]
    return df[c].dropna(), c


def looks_valid(s: pd.Series, unit: str) -> tuple[bool, str]:
    if s is None or s.dropna().empty:
        return False, "empty"
    x = s.dropna()
    med = float(x.median())

    if unit == "yield_pct":
        if med > 20:
            return False, f"yield looks like price/index: median={med:.4f}"
        if med < -5:
            return False, f"yield too low: median={med:.4f}"
    if unit == "fixing_fx":
        if not (4 <= med <= 10):
            return False, f"fixing level suspicious: median={med:.4f}"
    if unit == "fx":
        if med <= 0:
            return False, f"fx level non-positive: median={med:.4f}"
    if unit == "fx_jpy":
        if med <= 0:
            return False, f"fx level non-positive: median={med:.4f}"
    if unit == "commodity":
        if med <= 0:
            return False, f"commodity level non-positive: median={med:.4f}"
        if med > 100000:
            return False, f"commodity level implausibly high: median={med:.2f}"
    if unit == "futures_price":
        if med <= 0:
            return False, f"futures level non-positive: median={med:.4f}"
    if unit == "index":
        if med <= 0:
            return False, f"index level non-positive: median={med:.4f}"
    return True, ""


def fetch_one(asset: AssetConfig, start: datetime, end: datetime, interval: str):
    import lseg.data as ld

    log_rows = []
    unit = asset.unit
    field_sets = FIELD_SETS_BY_UNIT.get(unit, [None])

    for ric in asset.rics:
        for fields in field_sets:
            try:
                kwargs = {
                    "universe": [ric],
                    "start": to_lseg_time(start),
                    "end": to_lseg_time(end),
                    "interval": interval,
                }
                if fields is not None:
                    kwargs["fields"] = fields

                raw = ld.get_history(**kwargs)
                s, field_used = _series_from_history(raw, fields, unit)
                ok, reason = looks_valid(s, unit)

                if ok:
                    return s.rename(asset.name), {
                        "key": asset.key,
                        "section": asset.section,
                        "group": asset.group,
                        "name": asset.name,
                        "unit": asset.unit,
                        "ric": ric,
                        "field": field_used or str(fields),
                        "rows": int(s.notna().sum()),
                        "status": "ok",
                        "error": "",
                    }

                log_rows.append({
                    "key": asset.key,
                    "section": asset.section,
                    "group": asset.group,
                    "name": asset.name,
                    "unit": asset.unit,
                    "ric": ric,
                    "field": str(fields),
                    "rows": int(s.notna().sum()) if s is not None else 0,
                    "status": "invalid",
                    "error": reason,
                })

            except Exception as e:
                log_rows.append({
                    "key": asset.key,
                    "section": asset.section,
                    "group": asset.group,
                    "name": asset.name,
                    "unit": asset.unit,
                    "ric": ric,
                    "field": str(fields),
                    "rows": 0,
                    "status": "failed",
                    "error": str(e)[:300],
                })

    err = log_rows[-1] if log_rows else {
        "key": asset.key, "section": asset.section, "group": asset.group,
        "name": asset.name, "unit": asset.unit,
        "ric": "", "field": "", "rows": 0, "status": "failed", "error": "no attempt",
    }
    return None, err


def download_panel(
    assets: list[AssetConfig], start: datetime, end: datetime, interval: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    series_list = []
    logs = []
    for asset in sorted(assets, key=lambda x: x.order):
        s, log = fetch_one(asset, start, end, interval)
        logs.append(log)
        if s is not None and len(s.dropna()) > 0:
            series_list.append(s)

    panel = pd.concat(series_list, axis=1).sort_index() if series_list else pd.DataFrame()
    log_df = pd.DataFrame(logs) if logs else pd.DataFrame()
    return panel, log_df
