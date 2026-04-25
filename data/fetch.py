# Source Generated with Decompyle++
# File: fetch.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from datetime import datetime
import numpy as np
import pandas as pd
from config.settings import settings
from config.assets import AssetConfig, FIELD_SETS_BY_UNIT, YIELD_FIELD_HINTS, PRICE_FIELD_HINTS

def to_lseg_time(dt = None):
    return dt.astimezone(settings.REPORT_TZ).isoformat(timespec='seconds')


def ensure_dt_index(df = None):
    out = df.copy()
    out.index = pd.to_datetime(out.index, errors='coerce')
    out = out[~out.index.isna()]
    out.index = out.index.tz_localize(settings.REPORT_TZ) if out.index.tzinfo is None else out.index.tz_convert(settings.REPORT_TZ)
    out = out[~out.index.duplicated(keep='last')]
    out = out.sort_index()
    return out


def _flatten_columns(df = None):
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = ['_'.join(str(c) for c in col if c) for col in out.columns]
    return out


def _series_from_history(df = None, requested_fields = None, unit = None):
    """Extract the best series from LSEG history response."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    out = _flatten_columns(df)
    # Try to find yield/price columns
    if requested_fields:
        for fields in requested_fields:
            if fields is None:
                continue
            for f in fields:
                for col in out.columns:
                    if f.upper() in str(col).upper():
                        s = pd.to_numeric(out[col], errors='coerce').dropna()
                        if not s.empty:
                            return s
    # Fallback: use first numeric column
    for col in out.columns:
        s = pd.to_numeric(out[col], errors='coerce').dropna()
        if not s.empty:
            return s
    return pd.Series(dtype=float)


def looks_valid(s = None, unit = None):
    """Check if a series looks like valid data for the given unit type."""
    if s is None or s.empty:
        return False
    med = s.median()
    if pd.isna(med):
        return False
    if unit in ('yield_pct', 'bei_pct'):
        return 0 < med < 15  # yield in percent, not price
    if unit == 'fx_jpy':
        return 50 < med < 300
    if unit in ('fx', 'fixing_fx'):
        return 0.1 < med < 200
    if unit == 'fx_spread':
        return abs(med) < 0.1  # CNH-CNY spread should be small
    if unit == 'spread_bp':
        return -300 < med < 500
    if unit in ('index', 'futures_price', 'commodity'):
        return 1 < med < 100000
    return True


def fetch_one(asset = None, start = None, end = None, interval = '5min', session = None):
    """Fetch data for a single asset. Returns (series, log_row)."""
    ld = None
    try:
        import lseg.data
        ld = lseg.data
    except ImportError:
        log_row = {'name': asset.name, 'unit': asset.unit, 'status': 'error', 'error': 'lseg.data not available'}
        return pd.Series(dtype=float), pd.DataFrame([log_row])
    log_rows = []
    unit = asset.unit
    field_sets = FIELD_SETS_BY_UNIT.get(unit, [None])
    for fields in field_sets:
        if fields is None:
            break
        try:
            response = ld.get_history(
                universe=asset.rics,
                fields=fields,
                start=to_lseg_time(start),
                end=to_lseg_time(end),
                interval=interval,
            )
            if response is None or response.empty:
                continue
            s = _series_from_history(response, [fields], unit)
            s = ensure_dt_index(s.to_frame()).iloc[:, 0] if not s.empty else pd.Series(dtype=float)
            if looks_valid(s, unit):
                log_rows.append({'name': asset.name, 'unit': unit, 'status': 'ok', 'error': '', 'fields': ','.join(fields) if fields else '', 'obs': len(s)})
                return s, pd.DataFrame(log_rows)
        except Exception as e:
            log_rows.append({'name': asset.name, 'unit': unit, 'status': 'error', 'error': str(e)[:180], 'fields': ','.join(fields) if fields else '', 'obs': 0})
            continue
    log_rows.append({'name': asset.name, 'unit': unit, 'status': 'error', 'error': 'No valid data from any field set', 'fields': '', 'obs': 0})
    return pd.Series(dtype=float), pd.DataFrame(log_rows)


def download_panel(assets = None, start = None, end = None, interval = '5min', session = None):
    """Download data for multiple assets and return (panel, logs)."""
    series_list = []
    logs = []
    for asset in assets:
        s, asset_logs = fetch_one(asset, start, end, interval, session=session)
        logs.append(asset_logs)
        if not s.empty:
            series_list.append(s.rename(asset.name))
    panel = pd.DataFrame(series_list).T if series_list else pd.DataFrame()
    if not panel.empty:
        panel = panel.sort_index()
    all_logs = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame()
    return panel, all_logs
