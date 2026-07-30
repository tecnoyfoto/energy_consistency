"""Data models for Energy Consistency."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date as date_type
import math
from typing import Any


_VALID_DAY_STATUSES = {"ok", "warning", "critical", "incomplete"}
_VALID_DAY_REASONS = {
    "within_tolerance",
    "difference_outside_tolerance",
    "large_difference",
    "insufficient_local_coverage",
    "invalid_local_value",
}
COMPARISON_ALGORITHM_VERSION = 2


@dataclass(slots=True)
class DailyComparison:
    """Comparison between official and local energy for one calendar day."""

    date: str
    official_kwh: float
    local_kwh: float | None
    difference_kwh: float | None
    difference_percent: float | None
    coverage_percent: float
    status: str
    reason: str
    official_hours: float | None = None
    expected_official_hours: int | None = None
    green_abs_kwh: float | None = None
    green_percent: float | None = None
    critical_abs_kwh: float | None = None
    critical_percent: float | None = None
    min_coverage_percent: float | None = None
    algorithm_version: int = COMPARISON_ALGORITHM_VERSION

    def as_dict(self) -> dict[str, Any]:
        """Serialize the comparison."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DailyComparison:
        """Deserialize and validate a stored comparison.

        Storage belongs to the user and may outlive several integration versions.
        Validate each field so one truncated or manually edited record cannot inject
        non-finite values into sensors or report paths.
        """

        def required_number(key: str, *, non_negative: bool = False) -> float:
            number = float(value[key])
            if not math.isfinite(number) or (non_negative and number < 0):
                raise ValueError(f"Invalid {key}")
            return number

        def optional_number(key: str, *, non_negative: bool = False) -> float | None:
            raw = value.get(key)
            if raw is None:
                return None
            number = float(raw)
            if not math.isfinite(number) or (non_negative and number < 0):
                raise ValueError(f"Invalid {key}")
            return number

        date_value = str(value["date"])
        date_type.fromisoformat(date_value)
        status = str(value["status"])
        if status not in _VALID_DAY_STATUSES:
            raise ValueError("Invalid comparison status")
        reason = str(value["reason"])
        if reason not in _VALID_DAY_REASONS:
            raise ValueError("Invalid comparison reason")
        coverage = required_number("coverage_percent", non_negative=True)
        if coverage > 100.0:
            raise ValueError("Invalid coverage_percent")

        expected_hours_raw = value.get("expected_official_hours")
        expected_hours = (
            int(expected_hours_raw) if expected_hours_raw is not None else None
        )
        if expected_hours is not None and expected_hours <= 0:
            raise ValueError("Invalid expected_official_hours")

        algorithm_version = int(value.get("algorithm_version", 1))
        if algorithm_version <= 0:
            raise ValueError("Invalid algorithm_version")

        return cls(
            date=date_value,
            official_kwh=required_number("official_kwh", non_negative=True),
            local_kwh=optional_number("local_kwh", non_negative=True),
            difference_kwh=optional_number("difference_kwh"),
            difference_percent=optional_number("difference_percent"),
            coverage_percent=coverage,
            status=status,
            reason=reason,
            official_hours=optional_number("official_hours", non_negative=True),
            expected_official_hours=expected_hours,
            green_abs_kwh=optional_number("green_abs_kwh", non_negative=True),
            green_percent=optional_number("green_percent", non_negative=True),
            critical_abs_kwh=optional_number(
                "critical_abs_kwh", non_negative=True
            ),
            critical_percent=optional_number(
                "critical_percent", non_negative=True
            ),
            min_coverage_percent=optional_number(
                "min_coverage_percent", non_negative=True
            ),
            algorithm_version=algorithm_version,
        )


@dataclass(slots=True)
class CoordinatorSnapshot:
    """Current values exposed by entities."""

    status: str
    reason: str
    official_kwh: float | None = None
    local_kwh: float | None = None
    difference_kwh: float | None = None
    difference_percent: float | None = None
    coverage_percent: float | None = None
    comparison_date: str | None = None
    official_delay_days: int | None = None
    official_hours: float | None = None
    expected_official_hours: int | None = None
    pending_official_hours: float | None = None
    pending_expected_official_hours: int | None = None
    valid_days: int = 0
    warning_days: int = 0
    critical_days: int = 0
    using_cached_result: bool = False
    pending_sources: tuple[str, ...] = ()
