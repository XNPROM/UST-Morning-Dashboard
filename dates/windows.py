from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import settings

try:
    import pandas_market_calendars as mcal
except Exception:
    import warnings
    warnings.warn("pandas_market_calendars not installed; holiday-aware calendar unavailable, using Mon-Fri fallback")
    mcal = None


@dataclass
class ReportWindows:
    asof_dt: datetime
    asof_date: date
    prev_cn_day: date
    prev_us_day: date
    main_start: datetime
    main_end: datetime
    ny_start: datetime
    ny_end: datetime
    rolling24_start: datetime
    rolling24_end: datetime
    intraday_start: datetime
    intraday_end: datetime
    daily_start: datetime
    daily_end: datetime
    target_fixing_date: date


def _date_str(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def _override_date_set(xs: list[str]) -> set[date]:
    return set(pd.Timestamp(x).date() for x in xs)


CN_HOLIDAYS = _override_date_set(settings.CN_HOLIDAY_OVERRIDES)
CN_EXTRA_WORKDAYS = _override_date_set(settings.CN_EXTRA_WORKDAY_OVERRIDES)
US_HOLIDAYS = _override_date_set(settings.US_HOLIDAY_OVERRIDES)
US_EXTRA_WORKDAYS = _override_date_set(settings.US_EXTRA_WORKDAY_OVERRIDES)


def get_exchange_days(calendar_name: str, start_date, end_date) -> set[date]:
    start_date = pd.Timestamp(start_date).date()
    end_date = pd.Timestamp(end_date).date()
    if mcal is not None:
        try:
            cal = mcal.get_calendar(calendar_name)
            sched = cal.schedule(start_date=_date_str(start_date), end_date=_date_str(end_date))
            return set(pd.Timestamp(x).date() for x in sched.index)
        except Exception:
            pass
    return set(pd.date_range(start_date, end_date, freq="B").date)


def is_cn_market_day(d) -> bool:
    d = pd.Timestamp(d).date()
    if d in CN_EXTRA_WORKDAYS:
        return True
    if d in CN_HOLIDAYS:
        return False
    return d in get_exchange_days("XSHG", d - timedelta(days=7), d + timedelta(days=7))


def is_us_market_day(d) -> bool:
    d = pd.Timestamp(d).date()
    if d in US_EXTRA_WORKDAYS:
        return True
    if d in US_HOLIDAYS:
        return False
    return d in get_exchange_days("XNYS", d - timedelta(days=7), d + timedelta(days=7))


def prev_market_day(d, market: str = "CN", inclusive: bool = False) -> date:
    d = pd.Timestamp(d).date()
    check = is_cn_market_day if market.upper() == "CN" else is_us_market_day
    cur = d if inclusive else d - timedelta(days=1)
    for _ in range(30):
        if check(cur):
            return cur
        cur -= timedelta(days=1)
    raise RuntimeError(f"Cannot find previous {market} market day near {d}")


def compute_report_windows(now: datetime | None = None) -> ReportWindows:
    tz = settings.REPORT_TZ
    ny_tz = settings.NY_TZ

    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    now = now.astimezone(tz)

    anchor = now.replace(
        hour=settings.REPORT_AS_OF_HOUR,
        minute=settings.REPORT_AS_OF_MINUTE,
        second=0, microsecond=0,
    )
    if now < anchor:
        anchor -= timedelta(days=1)

    asof_dt = anchor
    asof_date = asof_dt.date()

    # If asof_date falls on a non-CN-market day (weekend/holiday), roll back
    if not is_cn_market_day(asof_date):
        asof_date = prev_market_day(asof_date, "CN", inclusive=False)
        asof_dt = datetime.combine(asof_date, dt_time(settings.REPORT_AS_OF_HOUR, settings.REPORT_AS_OF_MINUTE), tzinfo=tz)

    prev_cn_day = prev_market_day(asof_date, "CN", inclusive=False)
    main_start = datetime.combine(prev_cn_day, dt_time(settings.CN_MARKET_CLOSE_HOUR, 0), tzinfo=tz)
    main_end = asof_dt

    rolling24_start = asof_dt - timedelta(hours=24)
    rolling24_end = asof_dt

    asof_ny_date = asof_dt.astimezone(ny_tz).date()
    prev_us_day = prev_market_day(asof_ny_date, "US", inclusive=True)
    ny_close_candidate = datetime.combine(prev_us_day, dt_time(17, 0), tzinfo=ny_tz)
    if ny_close_candidate > asof_dt.astimezone(ny_tz):
        prev_us_day = prev_market_day(prev_us_day, "US", inclusive=False)

    ny_start = datetime.combine(prev_us_day, dt_time(8, 0), tzinfo=ny_tz).astimezone(tz)
    ny_end = datetime.combine(prev_us_day, dt_time(17, 0), tzinfo=ny_tz).astimezone(tz)

    intraday_start = asof_dt - timedelta(hours=settings.INTRADAY_LOOKBACK_HOURS)
    intraday_end = asof_dt
    daily_start = asof_dt - timedelta(days=settings.LONG_LOOKBACK_DAYS)
    daily_end = asof_dt

    fixing_release_dt = asof_dt.replace(
        hour=settings.RMB_FIXING_RELEASE_HOUR,
        minute=settings.RMB_FIXING_RELEASE_MINUTE,
        second=0, microsecond=0,
    )
    if asof_dt >= fixing_release_dt and is_cn_market_day(asof_date):
        target_fixing_date = asof_date
    else:
        target_fixing_date = prev_market_day(asof_date, "CN", inclusive=False)

    return ReportWindows(
        asof_dt=asof_dt,
        asof_date=asof_date,
        prev_cn_day=prev_cn_day,
        prev_us_day=prev_us_day,
        main_start=main_start,
        main_end=main_end,
        ny_start=ny_start,
        ny_end=ny_end,
        rolling24_start=rolling24_start,
        rolling24_end=rolling24_end,
        intraday_start=intraday_start,
        intraday_end=intraday_end,
        daily_start=daily_start,
        daily_end=daily_end,
        target_fixing_date=target_fixing_date,
    )
