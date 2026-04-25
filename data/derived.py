from __future__ import annotations

from datetime import datetime

import pandas as pd

from config.settings import settings


def add_derived(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()

    def add(name, s):
        if s is not None:
            s = s.dropna()
            if len(s) >= 2:
                out[name] = s

    if {"UST 10Y", "UST 2Y"}.issubset(out.columns):
        add("UST 2s10s spread", (out["UST 10Y"] - out["UST 2Y"]) * 100)
    if {"UST 10Y", "UST 5Y"}.issubset(out.columns):
        add("UST 5s10s spread", (out["UST 10Y"] - out["UST 5Y"]) * 100)
    if {"UST 30Y", "UST 5Y"}.issubset(out.columns):
        add("UST 5s30s spread", (out["UST 30Y"] - out["UST 5Y"]) * 100)

    if {"UST 5Y", "TIPS real 5Y"}.issubset(out.columns):
        add("BEI 5Y", out["UST 5Y"] - out["TIPS real 5Y"])
    if {"UST 10Y", "TIPS real 10Y"}.issubset(out.columns):
        add("BEI 10Y", out["UST 10Y"] - out["TIPS real 10Y"])
    if {"UST 30Y", "TIPS real 30Y"}.issubset(out.columns):
        add("BEI 30Y", out["UST 30Y"] - out["TIPS real 30Y"])

    if {"USDCNH", "USDCNY"}.issubset(out.columns):
        add("CNH-CNY spread", out["USDCNH"] - out["USDCNY"])

    if {"USDCNY", "USD/CNY fixing"}.issubset(out.columns):
        add("USDCNY - fixing", out["USDCNY"] - out["USD/CNY fixing"])
    if {"USDCNH", "USD/CNY fixing"}.issubset(out.columns):
        add("USDCNH - fixing", out["USDCNH"] - out["USD/CNY fixing"])

    return out


def slice_window(panel: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    if panel.empty:
        return panel.copy()
    tz = settings.REPORT_TZ
    return panel.loc[
        (panel.index >= start.astimezone(tz)) & (panel.index <= end.astimezone(tz))
    ].copy()
