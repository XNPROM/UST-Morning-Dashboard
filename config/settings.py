# Source Generated with Decompyle++
# File: settings.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import time as dt_time
from zoneinfo import ZoneInfo

@dataclass
class Settings:
    REPORT_TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo('Asia/Shanghai'))
    NY_TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo('America/New_York'))
    OUTPUT_DIR: str = field(default_factory=lambda: os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports'))
    PLOTLY_TEMPLATE: str = 'simple_white'
    MANUAL_US_EVENTS: list[dict] = field(default_factory=list)
    MAX_RETRY: int = 3
    CLEANUP_DAYS: int = 90
    BLOCKING_SEVERITIES: list[str] = field(default_factory=lambda: ['HIGH'])

settings = Settings()
