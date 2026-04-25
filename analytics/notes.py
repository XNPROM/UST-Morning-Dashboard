from __future__ import annotations

from analytics.summary import lookup, chg


def build_morning_notes(summary: pd.DataFrame) -> list[str]:
    notes = []

    r2 = lookup(summary, "UST 2Y")
    r10 = lookup(summary, "UST 10Y")
    if r2 is not None and r10 is not None:
        notes.append(
            f"美债：2Y {chg(summary, 'UST 2Y')}，10Y {chg(summary, 'UST 10Y')}；"
            f"曲线2s10s {chg(summary, 'UST 2s10s spread')}。"
        )

    beis = [x for x in ["BEI 5Y", "BEI 10Y", "BEI 30Y"] if lookup(summary, x) is not None]
    if beis:
        notes.append(
            "通胀预期："
            + "，".join([f"{x.replace('BEI ', '')} {chg(summary, x)}" for x in beis])
            + "；BEI口径为名义收益率减TIPS真实收益率。"
        )

    if lookup(summary, "DXY") is not None:
        rmb_bits = []
        for x in ["USDCNY", "USDCNH", "CNH-CNY spread"]:
            if lookup(summary, x) is not None:
                rmb_bits.append(f"{x} {chg(summary, x)}")
        notes.append(
            f"美元：DXY {chg(summary, 'DXY')}；"
            + ("人民币：" + "，".join(rmb_bits) + "。" if rmb_bits else "")
        )

    bits = []
    for x in ["TY 10Y Treasury Fut", "Brent crude", "WTI crude", "Gold", "Copper"]:
        if lookup(summary, x) is not None:
            bits.append(f"{x} {chg(summary, x)}")
    if bits:
        notes.append("联动资产：" + "，".join(bits) + "。")

    return notes
