# Source Generated with Decompyle++
# File: validation.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import pandas as pd

def cross_validate(intraday_panel = None, daily_panel = None, summary_main = None):
    issues = []
    if intraday_panel is None or daily_panel is None or summary_main is None:
        return issues
    if intraday_panel.empty or daily_panel.empty or summary_main.empty:
        return issues
    # Cross-validate intraday vs daily last values for common assets
    common_cols = set(intraday_panel.columns) & set(daily_panel.columns)
    for col in common_cols:
        i_last = intraday_panel[col].dropna().iloc[-1] if not intraday_panel[col].dropna().empty else None
        d_last = daily_panel[col].dropna().iloc[-1] if not daily_panel[col].dropna().empty else None
        if i_last is not None and d_last is not None:
            diff = abs(float(i_last) - float(d_last))
            unit = _guess_unit(col)
            threshold = _get_mismatch_threshold(unit)
            if diff > threshold:
                issues.append({
                    'Severity': 'MEDIUM',
                    'Asset': col,
                    'Issue': '5min与daily最后值偏差较大',
                    'Detail': f'intraday_last={float(i_last):.4f}, daily_last={float(d_last):.4f}, diff={diff:.4f}, threshold={threshold:.4f}'
                })
    # Cross-validate direction: UST yield vs Treasury futures should move opposite
    if 'UST 10Y' in summary_main['Asset'].values and 'TY 10Y Treasury Fut' in summary_main['Asset'].values:
        ust_chg = _get_change(summary_main, 'UST 10Y')
        fut_chg = _get_change(summary_main, 'TY 10Y Treasury Fut')
        if ust_chg is not None and fut_chg is not None:
            if (ust_chg > 0 and fut_chg > 0) or (ust_chg < 0 and fut_chg < 0):
                issues.append({
                    'Severity': 'HIGH',
                    'Asset': 'UST 10Y vs TY 10Y Treasury Fut',
                    'Issue': '方向不一致：收益率与期货应反向变动',
                    'Detail': f'UST 10Y change={ust_chg:.4f}, TY Fut change={fut_chg:.4f}'
                })
    return issues


def _guess_unit(col):
    yield_cols = ('UST', 'TIPS', 'BEI')
    if any(c in col for c in yield_cols):
        if 'spread' in col.lower():
            return 'spread_bp'
        return 'yield_pct'
    fx_cols = ('USDCNY', 'USDCNH', 'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'DXY', 'CNH-CNY')
    if any(c in col for c in fx_cols):
        if 'spread' in col.lower():
            return 'fx_spread'
        if 'JPY' in col:
            return 'fx_jpy'
        return 'fx'
    fut_cols = ('Treasury Fut', 'TU', 'FV', 'TY', 'US ')
    if any(c in col for c in fut_cols):
        return 'futures_price'
    return 'commodity'


def _get_mismatch_threshold(unit):
    thresholds = {
        'yield_pct': 0.05,
        'spread_bp': 2.0,
        'fx': 0.002,
        'fx_jpy': 0.3,
        'fx_spread': 5.0,
        'futures_price': 0.5,
        'commodity': 1.0,
    }
    return thresholds.get(unit, 1.0)


def _get_change(summary, asset):
    rows = summary[summary['Asset'] == asset]
    if rows.empty:
        return None
    chg_val = rows.iloc[0].get('Change', None)
    if chg_val is not None:
        try:
            return float(chg_val)
        except (ValueError, TypeError):
            return None
    return None


def detect_anomalies(panel = None):
    issues = []
    if panel is None or panel.empty:
        return issues
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
                    issues.append({
                        'Severity': 'LOW',
                        'Asset': col,
                        'Issue': f'检测到 {len(jumps)} 个 3σ 以上跳变点',
                        'Detail': f'max_jump={float(jumps.abs().max()):.4f}, 3σ={3 * std:.4f}'
                    })
        zero_run = (s == 0).astype(int)
        max_zero_run = zero_run.groupby((zero_run != zero_run.shift()).cumsum()).sum().max()
        if max_zero_run > 10:
            issues.append({
                'Severity': 'MEDIUM',
                'Asset': col,
                'Issue': f'连续零值点数 {max_zero_run}',
                'Detail': '可能存在数据源异常'
            })
    return issues


def sanity_check(panel = None):
    issues = []
    if panel is None or panel.empty:
        return issues
    ranges = {
        'UST 2Y': (0, 6),
        'UST 5Y': (0, 6.5),
        'UST 10Y': (0, 6.5),
        'UST 30Y': (0, 7),
        'TIPS real 5Y': (-2, 4),
        'TIPS real 10Y': (-2, 4),
        'TIPS real 30Y': (-1, 4.5),
        'BEI 5Y': (-1, 6),
        'BEI 10Y': (-1, 6),
        'BEI 30Y': (-1, 6),
        'DXY': (75, 130),
        'UST 2s10s spread': (-200, 350)
    }
    for name, (lo, hi) in ranges.items():
        if name in panel.columns:
            s = panel[name].dropna()
            if len(s) == 0:
                continue
            med = float(s.median())
            if med < lo or med > hi:
                issues.append({
                    'Severity': 'HIGH',
                    'Asset': name,
                    'Issue': f'中位数 {med:.4f} 超出合理区间 [{lo}, {hi}]',
                    'Detail': f'median={med:.4f}'
                })
    return issues
