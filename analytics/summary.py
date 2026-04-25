# Source Generated with Decompyle++
# File: summary.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import numpy as np
import pandas as pd
from config.assets import ORDER_BY_NAME, UNIT_BY_NAME, GROUP_BY_NAME, SECTION_BY_NAME

def get_unit(asset = None):
    return UNIT_BY_NAME.get(asset, 'index')


def get_group(asset = None):
    return GROUP_BY_NAME.get(asset, 'Other')


def get_section(asset = None):
    return SECTION_BY_NAME.get(asset, 'Other')


def get_order(asset = None):
    return ORDER_BY_NAME.get(asset, 9999)


def change_display(first = None, last = None, unit = None):
    chg = last - first
    pct = chg / first if pd.notna(first) and first != 0 else np.nan
    if unit in ('yield_pct', 'bei_pct'):
        return (chg, chg * 100, 'bp', np.nan)
    if unit == 'spread_bp':
        return (chg, chg, 'bp', np.nan)
    if unit == 'fx_jpy':
        return (chg, chg * 100, 'pips', pct)
    if unit in ('fx', 'fixing_fx', 'fx_spread'):
        return (chg, chg * 10000, 'pips', pct if unit == 'fx' else np.nan)
    if unit in ('index', 'futures_price', 'commodity'):
        return (chg, chg, 'pts', pct)
    return (chg, chg, 'pts', pct)


def format_level(x = None, unit = None):
    if pd.isna(x):
        return ''
    if unit in ('yield_pct', 'bei_pct'):
        return f'{x:.4f}%'
    if unit == 'spread_bp':
        return f'{x:.2f}bp'
    if unit in ('fx', 'fixing_fx'):
        return f'{x:.4f}'
    if unit == 'fx_jpy':
        return f'{x:.3f}'
    if unit == 'fx_spread':
        return f'{x * 10000:.1f}pips'
    if unit in ('futures_price', 'commodity', 'index'):
        return f'{x:.4f}'
    return f'{x:.4f}'


def format_change(x = None, unit = None):
    if pd.isna(x):
        return ''
    sign = '+' if x > 0 else ''
    if unit in ('bp', 'pips'):
        return f'{sign}{x:.2f}{unit}'
    if unit == 'pts':
        return f'{sign}{x:.4f}'
    return f'{sign}{x:.4f}'


def summarize_panel(panel = None, window_name = None):
    rows = []
    if panel is None or panel.empty:
        return pd.DataFrame()
    for col in panel.columns:
        s = panel[col].dropna()
        if s.empty:
            continue
        unit = get_unit(col)
        first = float(s.iloc[0])
        last = float(s.iloc[-1])
        high = float(s.max())
        low = float(s.min())
        obs = len(s)
        change_raw, change_display_val, change_unit, pct = change_display(first, last, unit)
        rows.append({
            'Section': get_section(col),
            'Group': get_group(col),
            'Asset': col,
            'Level': format_level(last, unit),
            'Change': change_raw,
            'Change Display': change_display_val,
            'Change Unit': change_unit,
            'Change Text': format_change(change_display_val, change_unit),
            '% Change': pct,
            '% Change Text': f'{pct:+.2f}%' if pd.notna(pct) else '',
            'High': high,
            'Low': low,
            'Obs': obs,
            'Order': get_order(col),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('Order').reset_index(drop=True)
    return df


def rows_by_section(summary = None, sections = None):
    if summary.empty:
        return summary
    return summary[summary['Section'].isin(sections)].copy()


def lookup(summary = None, asset = None):
    if summary.empty or asset not in set(summary['Asset']):
        return None
    return summary.loc[summary['Asset'].eq(asset)].iloc[0]


def chg(summary = None, asset = None):
    r = lookup(summary, asset)
    if r is None:
        return np.nan
    return r.get('Change', np.nan)


def latest_fixing_info(daily_panel = None, target_fixing_date = None):
    if 'USD/CNY fixing' not in daily_panel.columns:
        return {
            'status': 'missing',
            'detail': 'USD/CNY fixing not available'
        }
    s = daily_panel['USD/CNY fixing'].dropna()
    if s.empty:
        return {
            'status': 'missing',
            'detail': 'USD/CNY fixing empty'
        }
    last_date = s.index[-1].date()
    prev = s.iloc[-2] if len(s) >= 2 else np.nan
    last = s.iloc[-1]
    chg_pips = (last - prev) * 10000 if pd.notna(prev) else np.nan
    stale = last_date != target_fixing_date
    return {
        'status': 'stale' if stale else 'ok',
        'last_date': last_date,
        'target_date': target_fixing_date,
        'last': float(last),
        'chg_pips': float(chg_pips) if pd.notna(chg_pips) else np.nan,
        'detail': f'latest={last_date}, target={target_fixing_date}, level={last:.4f}'
    }
