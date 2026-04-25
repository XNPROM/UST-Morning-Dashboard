from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta

import pandas as pd

from config.settings import settings


def build_trading_hours() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "模块": "美债期货 / WTI / 黄金 / 铜",
            "主要市场": "CME/CBOT/NYMEX/COMEX Globex",
            "美东时间": "Sun-Fri 18:00-17:00，17:00-18:00日度休市",
            "深圳时间": "夏令约06:00-次日05:00；冬令约07:00-次日06:00",
            "早会意义": "9点已覆盖上一纽约交易段，并包含亚洲早盘早段。",
        },
        {
            "模块": "Brent",
            "主要市场": "ICE Futures Europe",
            "美东时间": "约Sun-Fri 20:00-18:00，具体以ICE为准",
            "深圳时间": "夏令约08:00-次日06:00；冬令约09:00-次日07:00",
            "早会意义": "9点附近刚进入/刚过Brent新交易日早段。",
        },
        {
            "模块": "FX / CNH",
            "主要市场": "OTC FX",
            "美东时间": "Sun 17:00-Fri 17:00近24小时",
            "深圳时间": "周一早至周六清晨近24小时",
            "早会意义": "CNH适合观察隔夜美元与亚洲早盘联动。",
        },
        {
            "模块": "CNY即期",
            "主要市场": "CFETS",
            "美东时间": "约前一日21:30-15:00（夏令）",
            "深圳时间": "09:30-次日03:00",
            "早会意义": "9点尚未开盘，主看上一交易日收盘和CNH预期。",
        },
        {
            "模块": "人民币中间价",
            "主要市场": "PBOC/CFETS",
            "美东时间": "约前一日21:15/20:15",
            "深圳时间": "通常09:15左右",
            "早会意义": "9点跑一般是上一交易日中间价；9:20后重跑可看当日。",
        },
    ])


def build_event_calendar(windows) -> pd.DataFrame:
    manual_events = settings.MANUAL_US_EVENTS
    ny_tz = settings.NY_TZ
    tz = settings.REPORT_TZ
    asof = windows.asof_dt
    horizon_days = 14

    rows = []
    for e in manual_events:
        try:
            t_et = pd.Timestamp(e["Time_ET"], tz=ny_tz)
        except Exception:
            continue
        t_sh = t_et.tz_convert(tz)
        if asof - timedelta(days=1) <= t_sh.to_pydatetime() <= asof + timedelta(days=horizon_days):
            rows.append({
                "Event": e["Event"],
                "Time ET": t_et.strftime("%Y-%m-%d %H:%M"),
                "深圳时间": t_sh.strftime("%Y-%m-%d %H:%M"),
                "Importance": e.get("Importance", ""),
            })

    start = asof.astimezone(ny_tz).date() - timedelta(days=1)
    for d in pd.date_range(start, periods=horizon_days + 3, freq="D").date:
        if pd.Timestamp(d).weekday() == 3:
            t_et = datetime.combine(d, dt_time(8, 30), tzinfo=ny_tz)
            t_sh = t_et.astimezone(tz)
            rows.append({
                "Event": "Initial Jobless Claims",
                "Time ET": t_et.strftime("%Y-%m-%d %H:%M"),
                "深圳时间": t_sh.strftime("%Y-%m-%d %H:%M"),
                "Importance": "Medium",
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["Event", "Time ET", "深圳时间", "Importance"])
    return out.drop_duplicates().sort_values("深圳时间").reset_index(drop=True)
