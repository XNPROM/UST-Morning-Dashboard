# Source Generated with Decompyle++
# File: windows.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import settings
import pandas_market_calendars as mcal

@dataclass
class ReportWindows:
    asof_dt: datetime
    main_start: datetime
    main_end: datetime
    rolling_24h_start: datetime
    daily_start: datetime
    daily_end: datetime
    ny_start: datetime
    ny_end: datetime
    target_fixing_date: date
    history_start: date  # ~2 years back for daily/weekly/monthly panels


def _get_prev_trading_date(asof_dt):
    """Get the previous trading date using the NYSE calendar (US markets)."""
    try:
        us_cal = mcal.get_calendar('NYSE')
        asof_date = asof_dt.date()
        schedule = us_cal.schedule(start_date=asof_date - timedelta(days=10), end_date=asof_date)
        if schedule.empty:
            return asof_date - timedelta(days=1)
        dates = pd.to_datetime(schedule.index).date
        if asof_date in dates:
            idx = dates.tolist().index(asof_date)
            if idx > 0:
                return dates[idx - 1]
        # Return last trading date before asof
        prev_dates = [d for d in dates if d < asof_date]
        if prev_dates:
            return prev_dates[-1]
        return asof_date - timedelta(days=1)
    except Exception:
        return asof_date - timedelta(days=1)


def compute_report_windows(asof_dt = None):
    """Compute all time windows for the report."""
    if asof_dt is None:
        asof_dt = datetime.now(settings.REPORT_TZ)
    asof_dt = asof_dt.replace(tzinfo=settings.REPORT_TZ) if asof_dt.tzinfo is None else asof_dt
    # Main window: previous China trading day 16:00 to asof_dt 09:00
    prev_trade = _get_prev_trading_date(asof_dt)
    main_start = datetime(prev_trade.year, prev_trade.month, prev_trade.day, 16, 0, tzinfo=settings.REPORT_TZ)
    main_end = asof_dt.replace(hour=9, minute=0, second=0, microsecond=0)
    # Rolling 24h window
    rolling_24h_start = main_end - timedelta(hours=24)
    # Daily window: full previous trading day
    daily_start = datetime(prev_trade.year, prev_trade.month, prev_trade.day, 0, 0, tzinfo=settings.REPORT_TZ)
    daily_end = datetime(prev_trade.year, prev_trade.month, prev_trade.day, 23, 59, 59, tzinfo=settings.REPORT_TZ)
    # NY session window (08:00-17:00 ET previous day)
    ny_start_et = datetime(prev_trade.year, prev_trade.month, prev_trade.day, 8, 0, tzinfo=settings.NY_TZ)
    ny_end_et = datetime(prev_trade.year, prev_trade.month, prev_trade.day, 17, 0, tzinfo=settings.NY_TZ)
    ny_start = ny_start_et.astimezone(settings.REPORT_TZ)
    ny_end = ny_end_et.astimezone(settings.REPORT_TZ)
    # Target fixing date is the previous trading date
    target_fixing_date = prev_trade
    # History start for daily/weekly/monthly panels (~2 years)
    history_start = asof_dt.date() - timedelta(days=730)
    return ReportWindows(
        asof_dt=asof_dt,
        main_start=main_start,
        main_end=main_end,
        rolling_24h_start=rolling_24h_start,
        daily_start=daily_start,
        daily_end=daily_end,
        ny_start=ny_start,
        ny_end=ny_end,
        target_fixing_date=target_fixing_date,
        history_start=history_start,
    )
