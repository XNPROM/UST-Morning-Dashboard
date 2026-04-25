from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


@dataclass
class AssetConfig:
    key: str
    section: str
    group: str
    name: str
    rics: list[str]
    unit: Literal["yield_pct", "index", "fx", "fx_jpy", "futures_price", "commodity", "fixing_fx"]
    freq: Literal["both", "intraday", "daily"] = "both"
    order: int = 9999


ASSETS: list[AssetConfig] = [
    # A. 美债名义收益率
    AssetConfig("ust2y",  "A. Rates", "Nominal UST", "UST 2Y",  ["US2YT=RR", "US2YT=X"],   "yield_pct", "both", 10),
    AssetConfig("ust5y",  "A. Rates", "Nominal UST", "UST 5Y",  ["US5YT=RR", "US5YT=X"],   "yield_pct", "both", 20),
    AssetConfig("ust10y", "A. Rates", "Nominal UST", "UST 10Y", ["US10YT=RR", "US10YT=X"], "yield_pct", "both", 30),
    AssetConfig("ust30y", "A. Rates", "Nominal UST", "UST 30Y", ["US30YT=RR", "US30YT=X"], "yield_pct", "both", 40),

    # B. TIPS真实利率
    AssetConfig("tips5y",  "B. Real & Inflation", "Real Yield / TIPS", "TIPS real 5Y",  ["US5YTIP=RR", "US5YTIPS=RR"],   "yield_pct", "both", 110),
    AssetConfig("tips10y", "B. Real & Inflation", "Real Yield / TIPS", "TIPS real 10Y", ["US10YTIP=RR", "US10YTIPS=RR"], "yield_pct", "both", 120),
    AssetConfig("tips30y", "B. Real & Inflation", "Real Yield / TIPS", "TIPS real 30Y", ["US30YTIP=RR", "US30YTIPS=RR"], "yield_pct", "both", 130),

    # C. 美债期货
    AssetConfig("tu", "C. Treasury Futures", "Treasury Futures", "TU 2Y Treasury Fut",  ["TUc1"], "futures_price", "both", 210),
    AssetConfig("fv", "C. Treasury Futures", "Treasury Futures", "FV 5Y Treasury Fut",  ["FVc1"], "futures_price", "both", 220),
    AssetConfig("ty", "C. Treasury Futures", "Treasury Futures", "TY 10Y Treasury Fut", ["TYc1"], "futures_price", "both", 230),
    AssetConfig("us", "C. Treasury Futures", "Treasury Futures", "US 30Y Treasury Fut", ["USc1"], "futures_price", "both", 240),
    # WN Ultra Bond Fut removed — RIC not available on current LSEG subscription

    # D. 美元与G10
    AssetConfig("dxy",    "D. USD & FX", "USD", "DXY",    [".DXY"], "index", "both", 310),
    AssetConfig("eurusd", "D. USD & FX", "FX",  "EURUSD", ["EUR="], "fx",    "both", 320),
    AssetConfig("usdjpy", "D. USD & FX", "FX",  "USDJPY", ["JPY="], "fx_jpy", "both", 330),
    AssetConfig("gbpusd", "D. USD & FX", "FX",  "GBPUSD", ["GBP="], "fx",    "both", 340),
    AssetConfig("audusd", "D. USD & FX", "FX",  "AUDUSD", ["AUD="], "fx",    "both", 350),

    # E. 人民币
    AssetConfig("usdcny", "E. RMB", "RMB", "USDCNY", ["CNY="], "fx", "both", 410),
    AssetConfig("usdcnh", "E. RMB", "RMB", "USDCNH", ["CNH="], "fx", "both", 420),
    AssetConfig("cnyfix", "E. RMB", "RMB", "USD/CNY fixing", ["CNY=PBOC", "CNYPBOC=CFXS", "CNYFIX=CFXS", "USDCNYFIX=CFXS", "CNY=SAEC"], "fixing_fx", "daily", 430),

    # F. 商品
    AssetConfig("brent",  "F. Commodities", "Commodities", "Brent crude", ["LCOc1"], "commodity", "both", 510),
    AssetConfig("wti",    "F. Commodities", "Commodities", "WTI crude",   ["CLc1"],  "commodity", "both", 520),
    AssetConfig("gold",   "F. Commodities", "Commodities", "Gold",        ["XAU=", "GCc1"],  "commodity", "both", 530),  # XAU= spot (24h), GCc1 futures (COMEX hours only)
    AssetConfig("copper", "F. Commodities", "Commodities", "Copper",      ["HGc1"],  "commodity", "both", 540),
]


@dataclass
class DerivedConfig:
    name: str
    section: str
    group: str
    unit: str
    order: int


DERIVED_METRICS: list[DerivedConfig] = [
    DerivedConfig("UST 2s10s spread", "A. Rates", "Curve", "spread_bp", 60),
    DerivedConfig("UST 5s10s spread", "A. Rates", "Curve", "spread_bp", 70),
    DerivedConfig("UST 5s30s spread", "A. Rates", "Curve", "spread_bp", 80),
    DerivedConfig("BEI 5Y",  "B. Real & Inflation", "Breakeven Inflation", "bei_pct", 150),
    DerivedConfig("BEI 10Y", "B. Real & Inflation", "Breakeven Inflation", "bei_pct", 160),
    DerivedConfig("BEI 30Y", "B. Real & Inflation", "Breakeven Inflation", "bei_pct", 170),
    DerivedConfig("CNH-CNY spread", "E. RMB", "RMB", "fx_spread", 440),
    DerivedConfig("USDCNY - fixing", "E. RMB", "RMB", "fx_spread", 450),
    DerivedConfig("USDCNH - fixing", "E. RMB", "RMB", "fx_spread", 460),
]


FIELD_SETS_BY_UNIT: dict[str, list[list[str] | None]] = {
    "yield_pct": [
        ["MID_YLD_1"],
        ["YLDTOMAT"],
        ["B_YLD_1", "A_YLD_1"],
        ["B_YLD_1"],
        ["A_YLD_1"],
        ["ISMA_B_YLD", "ISMA_A_YLD"],
        ["OPEN_YLD"],
        None,
    ],
    "index": [["TRDPRC_1"], ["MID_PRICE"], ["BID", "ASK"], ["BID"], ["ASK"], None],
    "fx": [["MID_PRICE"], ["BID", "ASK"], ["TRDPRC_1"], ["BID"], ["ASK"], None],
    "fx_jpy": [["MID_PRICE"], ["BID", "ASK"], ["TRDPRC_1"], ["BID"], ["ASK"], None],
    "futures_price": [["TRDPRC_1"], ["MID_PRICE"], ["SETTLE"], ["BID", "ASK"], None],
    "commodity": [["TRDPRC_1"], ["MID_PRICE"], ["SETTLE"], ["BID", "ASK"], None],
    "fixing_fx": [["TRDPRC_1"], ["MID_PRICE"], ["BID", "ASK"], ["BID"], ["ASK"], None],
}

YIELD_FIELD_HINTS = ("YLD", "YIELD", "YLDTOMAT")
PRICE_FIELD_HINTS = ("TRDPRC", "MID_PRICE", "SETTLE", "BID", "ASK", "VALUE")


def _build_lookup_dicts() -> tuple[dict, dict, dict, dict]:
    order = {}
    unit = {}
    group = {}
    section = {}
    for a in ASSETS:
        order[a.name] = a.order
        unit[a.name] = a.unit
        group[a.name] = a.group
        section[a.name] = a.section
    for d in DERIVED_METRICS:
        order[d.name] = d.order
        unit[d.name] = d.unit
        group[d.name] = d.group
        section[d.name] = d.section
    return order, unit, group, section


ORDER_BY_NAME, UNIT_BY_NAME, GROUP_BY_NAME, SECTION_BY_NAME = _build_lookup_dicts()


def wanted_assets(freq: str) -> list[AssetConfig]:
    if freq == "intraday":
        return [a for a in ASSETS if a.freq in ("both", "intraday")]
    if freq == "daily":
        return [a for a in ASSETS if a.freq in ("both", "daily")]
    return list(ASSETS)
