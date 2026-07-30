"""Pure comparison rules for Energy Consistency."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
from datetime import tzinfo
import math

from .const import (
    DAY_CRITICAL,
    DAY_INCOMPLETE,
    DAY_OK,
    DAY_WARNING,
    STATUS_CRITICAL,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_WARNING,
)
from .models import COMPARISON_ALGORITHM_VERSION, DailyComparison


def should_recalculate_day(
    comparison: DailyComparison | None, official_kwh: float
) -> bool:
    """Return whether a day needs fresh Recorder statistics."""
    return (
        comparison is None
        or comparison.status == DAY_INCOMPLETE
        or comparison.algorithm_version < COMPARISON_ALGORITHM_VERSION
        or comparison.official_hours is None
        or comparison.expected_official_hours is None
        or abs(comparison.official_kwh - official_kwh) > 0.001
    )


def cached_result_is_fresh(
    comparison_date: str, today: date, max_delay_days: int
) -> bool:
    """Return whether a verified result is recent enough to reuse."""
    try:
        compared_day = date.fromisoformat(comparison_date)
    except ValueError:
        return False
    return max((today - compared_day).days, 0) <= max_delay_days


def expected_hours_for_day(day: date, zone: tzinfo) -> int:
    """Return the duration of a local calendar day, including DST changes."""
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return round(
        (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
        / 3600
    )


def official_day_is_complete(hours: float | None, expected_hours: int) -> bool:
    """Return whether an official daily aggregate contains every expected hour."""
    return (
        hours is not None
        and math.isfinite(hours)
        and abs(hours - expected_hours) <= 0.01
    )


def classify_day(
    *,
    date: str,
    official_kwh: float,
    local_kwh: float | None,
    coverage_percent: float,
    min_coverage_percent: float,
    green_abs_kwh: float,
    green_percent: float,
    critical_abs_kwh: float,
    critical_percent: float,
    official_hours: float | None = None,
    expected_official_hours: int | None = None,
) -> DailyComparison:
    """Classify one day using combined absolute and relative tolerances."""
    if not math.isfinite(official_kwh) or official_kwh < 0:
        raise ValueError("Official energy must be a finite non-negative number")

    local_is_valid = (
        local_kwh is not None and math.isfinite(local_kwh) and local_kwh >= 0
    )
    coverage_is_valid = math.isfinite(coverage_percent) and 0 <= coverage_percent <= 100
    if not local_is_valid or not coverage_is_valid or coverage_percent < min_coverage_percent:
        return DailyComparison(
            date=date,
            official_kwh=round(official_kwh, 3),
            local_kwh=None if local_kwh is None else round(local_kwh, 3),
            difference_kwh=None,
            difference_percent=None,
            coverage_percent=(
                round(coverage_percent, 1) if coverage_is_valid else 0.0
            ),
            status=DAY_INCOMPLETE,
            reason=(
                "invalid_local_value"
                if local_kwh is not None and not local_is_valid
                else "insufficient_local_coverage"
            ),
            official_hours=official_hours,
            expected_official_hours=expected_official_hours,
            green_abs_kwh=green_abs_kwh,
            green_percent=green_percent,
            critical_abs_kwh=critical_abs_kwh,
            critical_percent=critical_percent,
            min_coverage_percent=min_coverage_percent,
        )

    assert local_kwh is not None
    difference = local_kwh - official_kwh
    absolute_difference = abs(difference)
    if official_kwh > 0:
        signed_relative_difference: float | None = difference / official_kwh * 100
        relative_difference = abs(signed_relative_difference)
    elif absolute_difference == 0:
        signed_relative_difference = 0.0
        relative_difference = 0.0
    else:
        signed_relative_difference = None
        relative_difference = math.inf
    green_limit = max(green_abs_kwh, official_kwh * green_percent / 100)

    if absolute_difference <= green_limit:
        status = DAY_OK
        reason = "within_tolerance"
    elif (
        absolute_difference > critical_abs_kwh
        and (official_kwh <= 0 or relative_difference > critical_percent)
    ):
        status = DAY_CRITICAL
        reason = "large_difference"
    else:
        status = DAY_WARNING
        reason = "difference_outside_tolerance"

    return DailyComparison(
        date=date,
        official_kwh=round(official_kwh, 3),
        local_kwh=round(local_kwh, 3),
        difference_kwh=round(difference, 3),
        difference_percent=(
            round(signed_relative_difference, 2)
            if signed_relative_difference is not None
            else None
        ),
        coverage_percent=round(coverage_percent, 1),
        status=status,
        reason=reason,
        official_hours=official_hours,
        expected_official_hours=expected_official_hours,
        green_abs_kwh=green_abs_kwh,
        green_percent=green_percent,
        critical_abs_kwh=critical_abs_kwh,
        critical_percent=critical_percent,
        min_coverage_percent=min_coverage_percent,
    )


def aggregate_status(
    records: Sequence[DailyComparison], learning_days: int
) -> tuple[str, str]:
    """Calculate a deliberately conservative overall status."""
    dated_records: list[tuple[date, DailyComparison]] = []
    for record in records:
        if record.status == DAY_INCOMPLETE:
            continue
        try:
            dated_records.append((date.fromisoformat(record.date), record))
        except ValueError:
            continue
    dated_records.sort(key=lambda item: item[0])
    valid = [record for _, record in dated_records]
    if len(valid) < learning_days:
        return STATUS_LEARNING, "collecting_valid_days"

    latest_day = dated_records[-1][0]
    by_day = {day: record for day, record in dated_records}
    recent = [
        record
        for day, record in dated_records
        if latest_day - timedelta(days=6) <= day <= latest_day
    ]
    last_three = [
        by_day[day]
        for offset in (2, 1, 0)
        if (day := latest_day - timedelta(days=offset)) in by_day
    ]
    consecutive_critical = (
        len(last_three) == 3
        and all(record.status == DAY_CRITICAL for record in last_three)
    )
    critical_in_week = sum(record.status == DAY_CRITICAL for record in recent)
    anomalous_last_three = (
        sum(record.status in (DAY_WARNING, DAY_CRITICAL) for record in last_three)
        if len(last_three) == 3
        else 0
    )

    if consecutive_critical or critical_in_week >= 5:
        return STATUS_CRITICAL, "persistent_large_difference"
    if anomalous_last_three >= 2:
        return STATUS_WARNING, "repeated_difference"
    return STATUS_OK, "recent_days_within_tolerance"
