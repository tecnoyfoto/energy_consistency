"""Data models for Energy Consistency."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date as date_type
from typing import Any

_VALID_DAY_STATUSES = {"ok", "warning", "critical", "incomplete"}
_VALID_DAY_REASONS = {
    "within_tolerance",
    "difference_outside_tolerance",
    "large_difference",
    "insufficient_local_coverage",
    "invalid_local_value",
    "local_sensor_may_be_frozen",
    "local_sources_disagree",
}
COMPARISON_ALGORITHM_VERSION = 3


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
    local_source_entity: str | None = None
    local_source_name: str | None = None
    local_source_role: str | None = None
    local_selection_reason: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    primary_local_kwh: float | None = None
    backup_local_kwh: float | None = None
    primary_coverage_percent: float | None = None
    backup_coverage_percent: float | None = None
    primary_zero_streak_hours: int | None = None
    backup_zero_streak_hours: int | None = None
    primary_local_name: str | None = None
    backup_local_name: str | None = None
    primary_local_enabled: bool = True
    backup_local_enabled: bool | None = None
    primary_calibration_factor: float = 1.0
    backup_calibration_factor: float | None = None
    primary_adjusted_kwh: float | None = None
    backup_adjusted_kwh: float | None = None
    local_sources_disagree: bool = False
    local_sources_difference_kwh: float | None = None
    local_sources_difference_percent: float | None = None
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

        def optional_percentage(key: str) -> float | None:
            number = optional_number(key, non_negative=True)
            if number is not None and number > 100.0:
                raise ValueError(f"Invalid {key}")
            return number

        def optional_non_negative_int(key: str) -> int | None:
            raw = value.get(key)
            if raw is None:
                return None
            number = int(raw)
            if number < 0:
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
            critical_abs_kwh=optional_number("critical_abs_kwh", non_negative=True),
            critical_percent=optional_number("critical_percent", non_negative=True),
            min_coverage_percent=optional_number(
                "min_coverage_percent", non_negative=True
            ),
            local_source_entity=(
                str(value["local_source_entity"])
                if value.get("local_source_entity")
                else None
            ),
            local_source_name=(
                str(value["local_source_name"])
                if value.get("local_source_name")
                else None
            ),
            local_source_role=_optional_source_role(value.get("local_source_role")),
            local_selection_reason=(
                str(value["local_selection_reason"])
                if value.get("local_selection_reason")
                else None
            ),
            fallback_used=bool(value.get("fallback_used", False)),
            fallback_reason=(
                str(value["fallback_reason"]) if value.get("fallback_reason") else None
            ),
            primary_local_kwh=optional_number("primary_local_kwh", non_negative=True),
            backup_local_kwh=optional_number("backup_local_kwh", non_negative=True),
            primary_coverage_percent=optional_percentage("primary_coverage_percent"),
            backup_coverage_percent=optional_percentage("backup_coverage_percent"),
            primary_zero_streak_hours=optional_non_negative_int(
                "primary_zero_streak_hours"
            ),
            backup_zero_streak_hours=optional_non_negative_int(
                "backup_zero_streak_hours"
            ),
            primary_local_name=(
                str(value["primary_local_name"])
                if value.get("primary_local_name")
                else None
            ),
            backup_local_name=(
                str(value["backup_local_name"])
                if value.get("backup_local_name")
                else None
            ),
            primary_local_enabled=bool(value.get("primary_local_enabled", True)),
            backup_local_enabled=(
                bool(value["backup_local_enabled"])
                if value.get("backup_local_enabled") is not None
                else None
            ),
            primary_calibration_factor=(
                optional_number("primary_calibration_factor", non_negative=True) or 1.0
            ),
            backup_calibration_factor=optional_number(
                "backup_calibration_factor", non_negative=True
            ),
            primary_adjusted_kwh=optional_number(
                "primary_adjusted_kwh", non_negative=True
            ),
            backup_adjusted_kwh=optional_number(
                "backup_adjusted_kwh", non_negative=True
            ),
            local_sources_disagree=bool(value.get("local_sources_disagree", False)),
            local_sources_difference_kwh=optional_number(
                "local_sources_difference_kwh"
            ),
            local_sources_difference_percent=optional_number(
                "local_sources_difference_percent"
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
    local_source_entity: str | None = None
    local_source_role: str | None = None
    local_selection_reason: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    primary_local_kwh: float | None = None
    backup_local_kwh: float | None = None
    local_source_name: str | None = None
    primary_local_name: str | None = None
    backup_local_name: str | None = None
    primary_local_enabled: bool = True
    backup_local_enabled: bool | None = None
    primary_calibration_factor: float = 1.0
    backup_calibration_factor: float | None = None
    primary_adjusted_kwh: float | None = None
    backup_adjusted_kwh: float | None = None
    local_sources_disagree: bool = False
    local_sources_difference_kwh: float | None = None
    local_sources_difference_percent: float | None = None


def _optional_source_role(value: Any) -> str | None:
    """Validate a persisted local source role."""
    if value is None:
        return None
    role = str(value)
    if role not in {"primary", "backup"}:
        raise ValueError("Invalid local_source_role")
    return role
