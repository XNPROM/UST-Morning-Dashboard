# Source Generated with Decompyle++
# File: quality.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import pandas as pd
from config.assets import SECTION_BY_NAME
from analytics.summary import latest_fixing_info

def find_blocking_quality_issues(quality_df = None, blocking_severities = None):
    if blocking_severities is None:
        blocking_severities = ['HIGH']
    if quality_df is None or quality_df.empty or 'Severity' not in quality_df.columns:
        return pd.DataFrame(columns=getattr(quality_df, 'columns', []))
    return quality_df[quality_df['Severity'].isin(blocking_severities)].copy()


def data_quality_checks(intraday_log, daily_log = None, main_panel = None, daily_panel = None, target_fixing_date = None, validation_issues = None):
    issues = []
    all_logs = pd.concat([
        intraday_log.assign(freq='5min'),
        daily_log.assign(freq='daily')], ignore_index=True)
    # Assets that eventually succeeded (any 'ok' row for the same name+freq)
    # should not have their intermediate retry errors reported.
    succeeded = set()
    for _, r in all_logs.iterrows():
        if r['status'] == 'ok':
            succeeded.add((r['name'], r['freq']))
    for _, r in all_logs.iterrows():
        if r['status'] != 'ok' and (r['name'], r['freq']) not in succeeded:
            # Only report the final summary error per asset+freq, skip
            # intermediate field-set retry errors (which are logged for
            # the ric_log CSV but should not inflate the quality report).
            if r.get('error', '') != 'No valid data from any field set':
                continue
            issues.append({
                'Severity': 'HIGH' if r['unit'] in ('yield_pct', 'fx', 'fx_jpy', 'fixing_fx') else 'MEDIUM',
                'Asset': r['name'],
                'Issue': f'{r["freq"]} 拉取失败/无效',
                'Detail': str(r.get('error', ''))[:180]
            })
    for col in ('UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y', 'TIPS real 5Y', 'TIPS real 10Y', 'TIPS real 30Y'):
        if col in main_panel.columns:
            med = main_panel[col].dropna().median()
            if pd.notna(med) and med > 20:
                issues.append({
                    'Severity': 'HIGH',
                    'Asset': col,
                    'Issue': '收益率看起来像价格',
                    'Detail': f'median={med:.4f}'
                })
    if 'CNH-CNY spread' in main_panel.columns:
        obs = int(main_panel['CNH-CNY spread'].notna().sum())
        if obs < 80:
            issues.append({
                'Severity': 'MEDIUM',
                'Asset': 'CNH-CNY spread',
                'Issue': 'CNY/CNH可比样本偏少',
                'Detail': f'obs={obs}; CNY在岸交易时段较短，spread只在共同时间戳比较。'
            })
    fix = latest_fixing_info(daily_panel, target_fixing_date)
    if fix['status'] == 'missing':
        issues.append({
            'Severity': 'MEDIUM',
            'Asset': 'USD/CNY fixing',
            'Issue': '中间价缺失',
            'Detail': fix['detail']
        })
    elif fix['status'] == 'stale':
        issues.append({
            'Severity': 'LOW',
            'Asset': 'USD/CNY fixing',
            'Issue': '中间价日期非目标日期',
            'Detail': fix['detail'] + '；9:15前运行通常显示上一交易日中间价。'
        })
    if validation_issues:
        issues.extend(validation_issues)
    if not issues:
        return pd.DataFrame([{
            'Severity': 'OK',
            'Asset': 'ALL',
            'Issue': 'No major issue',
            'Detail': '核心字段口径和数据完整性未发现重大异常。'
        }])
    return pd.DataFrame(issues)


def compute_quality_grade(quality_df = None, sections = None):
    """Compute A/B/C grade per section based on quality issues, filtered per section."""
    all_sections = ['A. Rates', 'B. Real & Inflation', 'C. Treasury Futures', 'D. USD & FX', 'E. RMB', 'F. Commodities']
    if sections is None:
        sections = all_sections
    grades = {s: 'A' for s in sections}
    if quality_df is None or quality_df.empty:
        return grades
    for _, r in quality_df.iterrows():
        severity = r.get('Severity', '')
        asset = r.get('Asset', '')
        if severity == 'OK':
            continue
        # Determine which sections this issue affects
        implicated = _find_implicated_sections(asset)
        if not implicated:
            continue
        for sec in implicated:
            if sec not in grades:
                continue
            current = grades[sec]
            if severity == 'HIGH':
                grades[sec] = 'C'
            elif severity == 'MEDIUM' and current == 'A':
                grades[sec] = 'B'
            elif severity == 'MEDIUM' and current == 'C':
                pass  # keep C
    return grades


def _find_implicated_sections(asset):
    """Find which sections an asset issue affects."""
    from config.assets import SECTION_BY_NAME
    if asset in SECTION_BY_NAME:
        return [SECTION_BY_NAME[asset]]
    # Cross-asset issues affect multiple sections
    if 'vs' in asset:
        parts = asset.split(' vs ')
        sections = set()
        for p in parts:
            p = p.strip()
            # Try to match against known assets
            for name, sec in SECTION_BY_NAME.items():
                if p.lower() in name.lower() or name.lower() in p.lower():
                    sections.add(sec)
        return list(sections) if sections else None
    return None
