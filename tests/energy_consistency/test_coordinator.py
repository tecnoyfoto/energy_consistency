"""Regression tests for Recorder units and complete local days."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from custom_components.energy_consistency.local_sources import LocalDayReading
from tests.support.source_loader import load_methods


def local_day(rows):
    calls = []

    async def executor(*args):
        calls.append(args)
        return {"sensor.local": rows}

    dt = SimpleNamespace(DEFAULT_TIME_ZONE=timezone.utc, as_utc=lambda value: value)
    ns = load_methods(
        "coordinator.py",
        {"_async_local_day", "_energy_to_kwh"},
        {
            "datetime": datetime,
            "time": __import__("datetime").time,
            "timedelta": __import__("datetime").timedelta,
            "dt_util": dt,
            "get_instance": lambda hass: SimpleNamespace(
                async_add_executor_job=executor
            ),
            "statistics_during_period": object(),
            "LocalDayReading": LocalDayReading,
            "math": __import__("math"),
            "_LOGGER": __import__("logging").getLogger(__name__),
        },
    )
    # A live sensor in Wh must not reinterpret historical kWh from Recorder.
    hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity: SimpleNamespace(attributes={"unit_of_measurement": "Wh"})
        )
    )
    result = asyncio.run(
        ns["_async_local_day"](
            SimpleNamespace(hass=hass), "sensor.local", "primary", date(2026, 10, 23)
        )
    )
    return result, calls


def test_recorder_requests_kwh_independently_of_live_sensor_unit():
    result, calls = local_day([{"change": 0.5}] * 24)
    assert result.kwh == 12
    assert result.coverage_percent == 100
    assert calls[0][-2] == {"energy": "kWh"}


@pytest.mark.parametrize(
    "changes",
    [
        [0.5] * 23,
        [0.5] * 25,
        [0.5] * 23 + [None],
        [0.5] * 23 + [float("nan")],
        [0.5] * 23 + [-0.5],
    ],
)
def test_incomplete_or_invalid_recorder_day_is_rejected(changes):
    result, _ = local_day([{"change": change} for change in changes])
    assert not result.complete
    assert result.error in {"insufficient_local_coverage", "invalid_local_value"}


def test_optional_modern_history_failure_does_not_disable_sensor_fallback():
    from datetime import time, timedelta
    from unittest.mock import AsyncMock, Mock

    from custom_components.energy_consistency import const
    from custom_components.energy_consistency.edata_adapter import EDataAdapterState

    ns = {key: getattr(const, key) for key in dir(const) if key.isupper()}
    ns.update(
        {
            "datetime": datetime,
            "time": time,
            "timedelta": timedelta,
            "EDataAdapterState": EDataAdapterState,
            "async_resolve_edata_daily_rows": AsyncMock(
                side_effect=ValueError("changed optional API")
            ),
            "er": SimpleNamespace(
                async_get=lambda hass: SimpleNamespace(
                    async_get=lambda entity: SimpleNamespace(config_entry_id="supply")
                )
            ),
            "_LOGGER": Mock(),
        }
    )
    load_methods("coordinator.py", {"_async_backfill_edata_days"}, ns)
    hass = SimpleNamespace(
        data={"edata": {}},
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry: SimpleNamespace(
                domain="edata", data={"scups": "demo"}
            )
        ),
    )
    coordinator = SimpleNamespace(
        hass=hass,
        official_energy_entity="sensor.official",
        option=lambda key, default: default,
    )
    assert (
        asyncio.run(ns["_async_backfill_edata_days"](coordinator, date(2026, 10, 25)))
        is EDataAdapterState.HISTORY_UNAVAILABLE
    )
    ns["_LOGGER"].warning.assert_called_once()


def test_threshold_reclassification_does_not_mark_old_measurements_as_recomputed():
    from custom_components.energy_consistency.const import DAY_INCOMPLETE
    from custom_components.energy_consistency.engine import (
        classify_day,
        should_recalculate_day,
    )
    from custom_components.energy_consistency.models import DailyComparison

    record = DailyComparison(
        date="2026-10-23",
        official_kwh=10,
        local_kwh=10,
        difference_kwh=0,
        difference_percent=0,
        coverage_percent=100,
        status="ok",
        reason="within_tolerance",
        official_hours=24,
        expected_official_hours=24,
        algorithm_version=3,
    )
    ns = {"classify_day": classify_day, "DAY_INCOMPLETE": DAY_INCOMPLETE}
    load_methods("coordinator.py", {"_reclassify_records"}, ns)
    coordinator = SimpleNamespace(
        records=[record],
        _comparison_thresholds=lambda: {
            "min_coverage_percent": 100,
            "green_abs_kwh": 0.5,
            "green_percent": 5,
            "critical_abs_kwh": 2,
            "critical_percent": 15,
        },
    )
    ns["_reclassify_records"](coordinator)
    assert coordinator.records[0].algorithm_version == 3
    assert should_recalculate_day(coordinator.records[0], 10)
