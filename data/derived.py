# Source Generated with Decompyle++
# File: derived.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from datetime import datetime
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


def slice_window(panel = None, start = None, end = None):
    if panel is None or panel.empty:
        return panel.copy()
    tz = settings.REPORT_TZ
    return panel.loc[(panel.index >= start.astimezone(tz)) & (panel.index <= end.astimezone(tz))].copy()
