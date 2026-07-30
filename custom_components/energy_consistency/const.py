"""Constants for Energy Consistency."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "energy_consistency"
PLATFORMS = ["sensor"]
FRONTEND_VERSION = "0.7.2"

CONF_OFFICIAL_ENERGY_ENTITY = "official_energy_entity"
CONF_OFFICIAL_DATE_ENTITY = "official_date_entity"
CONF_LOCAL_ENERGY_ENTITY = "local_energy_entity"
CONF_NAME = "name"

CONF_GREEN_ABS_KWH = "green_abs_kwh"
CONF_GREEN_PERCENT = "green_percent"
CONF_CRITICAL_ABS_KWH = "critical_abs_kwh"
CONF_CRITICAL_PERCENT = "critical_percent"
CONF_LEARNING_DAYS = "learning_days"
CONF_FROZEN_HOURS = "frozen_hours"
CONF_MAX_OFFICIAL_DELAY_DAYS = "max_official_delay_days"
CONF_MIN_COVERAGE_PERCENT = "min_coverage_percent"

DEFAULT_NAME = "Energy Consistency"
DEFAULT_GREEN_ABS_KWH = 0.5
DEFAULT_GREEN_PERCENT = 5.0
DEFAULT_CRITICAL_ABS_KWH = 2.0
DEFAULT_CRITICAL_PERCENT = 15.0
DEFAULT_LEARNING_DAYS = 7
DEFAULT_FROZEN_HOURS = 5.0
DEFAULT_MAX_OFFICIAL_DELAY_DAYS = 7
DEFAULT_MIN_COVERAGE_PERCENT = 100.0

STATUS_OK = "ok"
STATUS_LEARNING = "learning"
STATUS_WAITING = "waiting"
STATUS_DATA_ISSUE = "data_issue"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"
STATUS_OPTIONS = [
    STATUS_OK,
    STATUS_LEARNING,
    STATUS_WAITING,
    STATUS_DATA_ISSUE,
    STATUS_WARNING,
    STATUS_CRITICAL,
]

DAY_OK = "ok"
DAY_WARNING = "warning"
DAY_CRITICAL = "critical"
DAY_INCOMPLETE = "incomplete"

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}."
REFRESH_INTERVAL = timedelta(minutes=15)
SOURCE_STARTUP_GRACE = timedelta(minutes=30)
BACKFILL_LOOKBACK_DAYS = 14
MAX_RECORDS = 730
