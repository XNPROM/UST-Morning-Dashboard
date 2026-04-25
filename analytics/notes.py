from __future__ import annotations

from analytics.summary import lookup, chg


def build_morning_notes(summary: pd.DataFrame) -> list[str]:
    notes = []
    asset_labels = {
        "UST 2s10s spread": "2s10s 利差",
        "USDCNY": "在岸人民币",
        "USDCNH": "离岸人民币",
        "CNH-CNY spread": "离在岸价差",
        "TY 10Y Treasury Fut": "TY 十年期美债期货",
        "Brent crude": "布伦特原油",
        "WTI crude": "WTI 原油",
        "Gold": "黄金",
        "Copper": "铜",
    }

    def label(asset: str) -> str:
        return asset_labels.get(asset, asset)

    r2 = lookup(summary, "UST 2Y")
    r10 = lookup(summary, "UST 10Y")
    if r2 is not None and r10 is not None:
        sentence = f"美债方面，2Y {chg(summary, 'UST 2Y')}，10Y {chg(summary, 'UST 10Y')}"
        if lookup(summary, "UST 2s10s spread") is not None:
            sentence += f"，{label('UST 2s10s spread')} {chg(summary, 'UST 2s10s spread')}"
        notes.append(sentence + "。")

    beis = [x for x in ["BEI 5Y", "BEI 10Y", "BEI 30Y"] if lookup(summary, x) is not None]
    if beis:
        notes.append(
            "通胀补偿方面，"
            + "，".join([f"{x.replace('BEI ', '')} {chg(summary, x)}" for x in beis])
            + "。BEI 按名义收益率减去 TIPS 真实收益率计算。"
        )

    if lookup(summary, "DXY") is not None:
        rmb_bits = []
        for x in ["USDCNY", "USDCNH", "CNH-CNY spread"]:
            if lookup(summary, x) is not None:
                rmb_bits.append(f"{label(x)} {chg(summary, x)}")
        sentence = f"美元与人民币方面，DXY {chg(summary, 'DXY')}。"
        if rmb_bits:
            sentence += "人民币相关指标包括" + "，".join(rmb_bits) + "。"
        notes.append(sentence)

    bits = []
    for x in ["TY 10Y Treasury Fut", "Brent crude", "WTI crude", "Gold", "Copper"]:
        if lookup(summary, x) is not None:
            bits.append(f"{label(x)} {chg(summary, x)}")
    if bits:
        notes.append("联动资产方面，" + "，".join(bits) + "。")

    return notes
