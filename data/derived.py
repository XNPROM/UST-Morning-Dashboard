# Source Generated with Decompyle++
# File: derived.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from datetime import datetime
import numpy as np
import pandas as pd
from config.settings import settings

def add_derived(panel = None):
    """Compute derived metrics: spreads, BEI, CNH-CNY spread, fixing gaps."""
    if panel is None or panel.empty:
        return panel
    out = panel.copy()
    # Yield curve spreads (10Y - 2Y, etc.)
    if 'UST 10Y' in out.columns and 'UST 2Y' in out.columns:
        out['UST 2s10s spread'] = (out['UST 10Y'] - out['UST 2Y']) * 100
    if 'UST 10Y' in out.columns and 'UST 5Y' in out.columns:
        out['UST 5s10s spread'] = (out['UST 10Y'] - out['UST 5Y']) * 100
    if 'UST 30Y' in out.columns and 'UST 5Y' in out.columns:
        out['UST 5s30s spread'] = (out['UST 30Y'] - out['UST 5Y']) * 100
    # Breakeven inflation (BEI = nominal yield - TIPS real yield)
    if 'UST 5Y' in out.columns and 'TIPS real 5Y' in out.columns:
        out['BEI 5Y'] = out['UST 5Y'] - out['TIPS real 5Y']
    if 'UST 10Y' in out.columns and 'TIPS real 10Y' in out.columns:
        out['BEI 10Y'] = out['UST 10Y'] - out['TIPS real 10Y']
    if 'UST 30Y' in out.columns and 'TIPS real 30Y' in out.columns:
        out['BEI 30Y'] = out['UST 30Y'] - out['TIPS real 30Y']
    # CNH-CNY spread
    if 'USDCNH' in out.columns and 'USDCNY' in out.columns:
        out['CNH-CNY spread'] = out['USDCNH'] - out['USDCNY']
    # Fixing gaps
    if 'USDCNY' in out.columns and 'USD/CNY fixing' in out.columns:
        out['USDCNY - fixing'] = out['USDCNY'] - out['USD/CNY fixing']
    if 'USDCNH' in out.columns and 'USD/CNY fixing' in out.columns:
        out['USDCNH - fixing'] = out['USDCNH'] - out['USD/CNY fixing']
    return out


def clean_panel(panel, freq_minutes=5):
    """Clean intraday panel: forward-fill small gaps and remove outlier spikes.

    1. Forward-fill NaN gaps of up to 3 bars (15 min for 5-min data) so that
       minor timestamp misalignments between assets don't leave holes.
    2. Detect single-bar outlier spikes using a rolling-median filter and
       replace them with NaN, then forward-fill once to close the hole.
    3. Does NOT fill across large gaps (different trading sessions).
    """
    if panel is None or panel.empty:
        return panel
    out = panel.copy()

    # --- Step 1: forward-fill small gaps ---
    out = out.ffill(limit=12)

    # --- Step 2: rolling-median spike removal ---
    window = 13  # ~1 hour for 5-min bars
    for col in out.columns:
        s = out[col]
        n_valid = s.count()
        if n_valid < 20:
            continue
        w = min(window, n_valid // 2)
        if w < 5:
            continue
        med = s.rolling(window=w, center=True, min_periods=5).median()
        std = s.rolling(window=w, center=True, min_periods=5).std()
        # Avoid zero / tiny std (flat series)
        std = std.clip(lower=1e-8)
        deviation = (s - med).abs()
        is_spike = deviation > (4 * std)
        # Don't flag edges (first/last 3 bars) – they lack rolling context
        is_spike.iloc[:3] = False
        is_spike.iloc[-3:] = False
        if is_spike.any():
            out.loc[is_spike, col] = np.nan
            out[col] = out[col].ffill(limit=1)

    return out


def slice_window(panel = None, start = None, end = None):
    if panel is None or panel.empty:
        return panel.copy()
    tz = settings.REPORT_TZ
    return panel.loc[(panel.index >= start.astimezone(tz)) & (panel.index <= end.astimezone(tz))].copy()


def resample_panel(daily_panel, rule='W-FRI'):
    """Resample a daily panel to weekly/monthly frequency using last valid value.

    Parameters
    ----------
    daily_panel : DataFrame with DatetimeIndex (daily bars)
    rule : str – pandas offset alias, e.g. 'W-FRI' for weekly (Friday close),
           'ME' for month-end, 'YE' for year-end.

    Returns
    -------
    DataFrame resampled to the given frequency (last observation carried forward).
    """
    if daily_panel is None or daily_panel.empty:
        return daily_panel
    return daily_panel.resample(rule).last().dropna(how='all')
