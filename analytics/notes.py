# Source Generated with Decompyle++
# File: notes.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from analytics.summary import lookup

def build_morning_notes(summary = None):
    """Build a list of one-line morning notes from the summary."""
    notes = []
    if summary is None or summary.empty:
        return notes
    # UST yields note
    ust_2y = lookup(summary, 'UST 2Y')
    ust_10y = lookup(summary, 'UST 10Y')
    if ust_2y is not None and ust_10y is not None:
        notes.append(f'美债：2Y {ust_2y["Level"]}（{ust_2y["Change Text"]}），10Y {ust_10y["Level"]}（{ust_10y["Change Text"]}）；曲线2s10s {_get_spread_text(summary)}。')
    # BEI note
    bei_5y = lookup(summary, 'BEI 5Y')
    bei_10y = lookup(summary, 'BEI 10Y')
    bei_30y = lookup(summary, 'BEI 30Y')
    if bei_5y is not None or bei_10y is not None:
        parts = []
        for b in [bei_5y, bei_10y, bei_30y]:
            if b is not None:
                parts.append(f'{b["Asset"]} {b["Level"]}（{b["Change Text"]}）')
        notes.append(f'通胀预期：{"，".join(parts)}；BEI口径为名义收益率减TIPS真实收益率。')
    # DXY / FX note
    dxy = lookup(summary, 'DXY')
    usdcny = lookup(summary, 'USDCNY')
    usdcnh = lookup(summary, 'USDCNH')
    cnh_cny = lookup(summary, 'CNH-CNY spread')
    if dxy is not None or usdcny is not None:
        dxy_text = f'DXY {dxy["Level"]}（{dxy["Change Text"]}）' if dxy is not None else ''
        cny_text = f'人民币：USDCNY {usdcny["Level"]}（{usdcny["Change Text"]}）' if usdcny is not None else ''
        cnh_text = f'USDCNH {usdcnh["Level"]}（{usdcnh["Change Text"]}）' if usdcnh is not None else ''
        spread_text = f'CNH-CNY spread {cnh_cny["Level"]}（{cnh_cny["Change Text"]}）' if cnh_cny is not None else ''
        parts = [p for p in [dxy_text, cny_text, cnh_text, spread_text] if p]
        notes.append(f'美元：{"；".join(parts)}。')
    # Commodities note
    brent = lookup(summary, 'Brent crude')
    wti = lookup(summary, 'WTI crude')
    gold = lookup(summary, 'Gold')
    ty = lookup(summary, 'TY 10Y Treasury Fut')
    if ty is not None or brent is not None or gold is not None:
        parts = []
        if ty is not None:
            parts.append(f'{ty["Asset"]} {ty["Level"]}（{ty["Change Text"]}）')
        if brent is not None:
            parts.append(f'{brent["Asset"]} {brent["Level"]}（{brent["Change Text"]}）')
        if wti is not None:
            parts.append(f'{wti["Asset"]} {wti["Level"]}（{wti["Change Text"]}）')
        if gold is not None:
            parts.append(f'{gold["Asset"]} {gold["Level"]}（{gold["Change Text"]}）')
        notes.append(f'联动资产：{"，".join(parts)}。')
    return notes


def _get_spread_text(summary):
    spread_2s10s = lookup(summary, 'UST 2s10s spread')
    if spread_2s10s is not None:
        return f'{spread_2s10s["Level"]}（{spread_2s10s["Change Text"]}）'
    ust_2y = lookup(summary, 'UST 2Y')
    ust_10y = lookup(summary, 'UST 10Y')
    if ust_2y is not None and ust_10y is not None:
        try:
            spread = float(ust_10y['Change Display']) - float(ust_2y['Change Display'])
            return f'{spread:.2f}bp'
        except (ValueError, TypeError, KeyError):
            pass
    return 'N/A'
