from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time as dt_time
from zoneinfo import ZoneInfo


@dataclass
class Settings:
    REPORT_TZ = ZoneInfo("Asia/Shanghai")
    NY_TZ = ZoneInfo("America/New_York")

    REPORT_AS_OF_HOUR: int = 9
    REPORT_AS_OF_MINUTE: int = 0
    CN_MARKET_CLOSE_HOUR: int = 16

    INTRADAY_LOOKBACK_HOURS: int = 72
    INTRADAY_INTERVAL: str = "5min"
    LONG_LOOKBACK_DAYS: int = 400
    LONG_INTERVAL: str = "daily"

    RMB_FIXING_RELEASE_HOUR: int = 9
    RMB_FIXING_RELEASE_MINUTE: int = 15

    PLOTLY_TEMPLATE: str = "plotly_white"

    CN_HOLIDAY_OVERRIDES: list[str] = field(default_factory=list)
    CN_EXTRA_WORKDAY_OVERRIDES: list[str] = field(default_factory=list)
    US_HOLIDAY_OVERRIDES: list[str] = field(default_factory=list)
    US_EXTRA_WORKDAY_OVERRIDES: list[str] = field(default_factory=list)

    MANUAL_US_EVENTS: list[dict] = field(default_factory=list)

    @property
    def PROJECT_ROOT(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @property
    def OUTPUT_DIR(self) -> str:
        return os.environ.get("OUTPUT_DIR", os.path.join(self.PROJECT_ROOT, "reports"))

    @property
    def LOG_DIR(self) -> str:
        return os.environ.get("LOG_DIR", os.path.join(self.PROJECT_ROOT, "logs"))


settings = Settings()
