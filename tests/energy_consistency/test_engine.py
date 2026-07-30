"""Tests for Energy Consistency comparison rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).parents[2]
CUSTOM_COMPONENTS = ROOT / "custom_components"
COMPONENT = CUSTOM_COMPONENTS / "energy_consistency"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(CUSTOM_COMPONENTS)]
sys.modules.setdefault("custom_components", custom_components)

package = types.ModuleType("custom_components.energy_consistency")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components.energy_consistency", package)

from custom_components.energy_consistency.const import (  # noqa: E402
    DAY_CRITICAL,
    DAY_INCOMPLETE,
    DAY_OK,
    DAY_WARNING,
    STATUS_CRITICAL,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_WARNING,
)
from custom_components.energy_consistency.engine import (  # noqa: E402
    aggregate_status,
    cached_result_is_fresh,
    classify_day,
    expected_hours_for_day,
    official_day_is_complete,
    should_recalculate_day,
)


def compare(
    official: float,
    local: float | None,
    coverage: float = 100,
    day: str = "2026-07-17",
):
    """Create a comparison using the proposed defaults."""
    return classify_day(
        date=day,
        official_kwh=official,
        local_kwh=local,
        coverage_percent=coverage,
        min_coverage_percent=98,
        green_abs_kwh=0.5,
        green_percent=5,
        critical_abs_kwh=2,
        critical_percent=15,
        official_hours=24,
        expected_official_hours=24,
    )


def test_real_world_match_is_green() -> None:
    record = compare(11.41, 11.42)
    assert record.status == DAY_OK
    assert record.difference_kwh == pytest.approx(0.01)
    assert record.difference_percent == pytest.approx(0.09)


def test_difference_keeps_its_direction() -> None:
    record = compare(10, 9)
    assert record.difference_kwh == pytest.approx(-1)
    assert record.difference_percent == pytest.approx(-10)


def test_low_coverage_is_incomplete_not_anomaly() -> None:
    record = compare(11.41, 8.0, coverage=80)
    assert record.status == DAY_INCOMPLETE
    assert record.difference_kwh is None


def test_large_difference_requires_absolute_and_relative_thresholds() -> None:
    assert compare(100, 106).status == DAY_WARNING
    assert compare(10, 13).status == DAY_CRITICAL
    assert compare(0, 3).status == DAY_CRITICAL


def test_single_bad_day_does_not_raise_general_warning() -> None:
    records = [compare(10, 10) for _ in range(6)] + [compare(10, 13)]
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_OK


def test_two_anomalies_in_last_three_raise_warning() -> None:
    records = [
        compare(10, 10, day=f"2026-07-{day:02d}") for day in range(21, 25)
    ]
    records += [
        compare(10, 11, day="2026-07-25"),
        compare(10, 10, day="2026-07-26"),
        compare(10, 11, day="2026-07-27"),
    ]
    assert records[-1].status == DAY_WARNING
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_WARNING


def test_three_consecutive_critical_days_are_required_for_red() -> None:
    records = [
        compare(10, 10, day=f"2026-07-{day:02d}") for day in range(21, 25)
    ] + [
        compare(10, 13, day=f"2026-07-{day:02d}") for day in range(25, 28)
    ]
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_CRITICAL


def test_missing_calendar_day_breaks_anomaly_streak() -> None:
    records = [
        compare(10, 10, day=f"2026-07-{day:02d}") for day in range(18, 23)
    ]
    records += [
        compare(10, 13, day="2026-07-23"),
        compare(10, 13, day="2026-07-25"),
    ]
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_OK


def test_old_anomalies_are_not_treated_as_this_week() -> None:
    records = [
        compare(10, 13, day=f"2026-06-{day:02d}") for day in range(1, 6)
    ] + [
        compare(10, 10, day="2026-07-27"),
        compare(10, 10, day="2026-07-28"),
    ]
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_OK


def test_learning_blocks_alerts_until_enough_valid_days() -> None:
    records = [compare(10, 13) for _ in range(3)]
    status, _ = aggregate_status(records, learning_days=7)
    assert status == STATUS_LEARNING


def test_verified_day_is_not_recalculated_after_restart() -> None:
    record = compare(11.41, 11.42)
    assert should_recalculate_day(record, official_kwh=11.41) is False


def test_day_is_recalculated_if_official_value_is_corrected() -> None:
    record = compare(11.41, 11.42)
    assert should_recalculate_day(record, official_kwh=11.5) is True


def test_legacy_day_without_hour_proof_is_recalculated() -> None:
    record = compare(11.41, 11.42)
    record.official_hours = None
    assert should_recalculate_day(record, official_kwh=11.41) is True


def test_cached_result_respects_official_delay_limit() -> None:
    today = date(2026, 7, 29)
    assert cached_result_is_fresh("2026-07-27", today, max_delay_days=4)
    assert not cached_result_is_fresh("2026-07-24", today, max_delay_days=4)


def test_official_day_must_contain_every_hour() -> None:
    assert official_day_is_complete(24.0, 24)
    assert not official_day_is_complete(20.0, 24)
    assert not official_day_is_complete(48.0, 24)
    assert not official_day_is_complete(None, 24)


def test_zero_official_energy_does_not_report_a_false_zero_percent() -> None:
    record = compare(0, 1)
    assert record.difference_percent is None


def test_invalid_numeric_values_are_rejected_or_incomplete() -> None:
    with pytest.raises(ValueError):
        compare(float("nan"), 1)
    with pytest.raises(ValueError):
        compare(-1, 1)
    assert compare(1, float("inf")).status == DAY_INCOMPLETE


def test_expected_hours_follow_dst_calendar_days() -> None:
    class Madrid2026(tzinfo):
        def utcoffset(self, value: datetime | None) -> timedelta:
            if value is not None and date(2026, 3, 30) <= value.date() <= date(2026, 10, 25):
                return timedelta(hours=2)
            return timedelta(hours=1)

        def dst(self, value: datetime | None) -> timedelta:
            return self.utcoffset(value) - timedelta(hours=1)

    madrid = Madrid2026()
    assert expected_hours_for_day(date(2026, 2, 1), madrid) == 24
    assert expected_hours_for_day(date(2026, 3, 29), madrid) == 23
    assert expected_hours_for_day(date(2026, 10, 25), madrid) == 25
