"""Pure local-meter health and failover rules."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalDayReading:
    """A single meter's reconstructed value for one calendar day."""

    entity_id: str
    role: str
    kwh: float | None
    coverage_percent: float
    zero_streak_hours: int = 0
    error: str | None = None
    name: str | None = None
    included: bool = True
    calibration_factor: float = 1.0

    @property
    def complete(self) -> bool:
        """Return whether Recorder supplied a usable complete day."""
        return (
            self.error is None
            and self.kwh is not None
            and math.isfinite(self.kwh)
            and self.kwh >= 0
            and math.isfinite(self.coverage_percent)
            and self.coverage_percent >= 100.0
        )

    @property
    def adjusted_kwh(self) -> float | None:
        """Return the calibrated value without altering the raw measurement."""
        if self.kwh is None:
            return None
        return self.kwh * self.calibration_factor


@dataclass(frozen=True, slots=True)
class LocalSourceSelection:
    """Result of choosing exactly one local meter."""

    reading: LocalDayReading | None
    reason: str
    fallback_used: bool = False
    fallback_reason: str | None = None
    sources_disagree: bool = False


def readings_agree(
    first: LocalDayReading,
    second: LocalDayReading,
    *,
    absolute_tolerance_kwh: float,
    relative_tolerance_percent: float,
) -> bool:
    """Return whether two complete meters agree within either tolerance."""
    if first.adjusted_kwh is None or second.adjusted_kwh is None:
        return False
    difference = abs(first.adjusted_kwh - second.adjusted_kwh)
    reference = max(first.adjusted_kwh, second.adjusted_kwh)
    relative_limit = reference * relative_tolerance_percent / 100
    return difference <= max(absolute_tolerance_kwh, relative_limit)


def select_local_source(
    primary: LocalDayReading,
    backup: LocalDayReading | None,
    *,
    zero_streak_limit_hours: int,
    agreement_absolute_kwh: float,
    agreement_percent: float,
) -> LocalSourceSelection:
    """Choose one meter by priority without ever combining their values."""
    if not primary.included:
        if backup is None or not backup.included:
            return LocalSourceSelection(None, "no_local_source_included")
        if backup.complete and backup.zero_streak_hours < zero_streak_limit_hours:
            return LocalSourceSelection(
                backup,
                "backup_selected_primary_excluded",
                fallback_reason="primary_excluded",
            )
        return LocalSourceSelection(
            None,
            (
                "local_sensor_may_be_frozen"
                if backup.complete
                else backup.error or "backup_incomplete"
            ),
        )

    eligible_backup = backup if backup is not None and backup.included else None
    primary_stalled = (
        primary.complete and primary.zero_streak_hours >= zero_streak_limit_hours
    )
    backup_stalled = (
        eligible_backup is not None
        and eligible_backup.complete
        and eligible_backup.zero_streak_hours >= zero_streak_limit_hours
    )

    if not primary.complete:
        if (
            eligible_backup is not None
            and eligible_backup.complete
            and not backup_stalled
        ):
            return LocalSourceSelection(
                eligible_backup,
                "backup_selected",
                fallback_used=True,
                fallback_reason=primary.error or "primary_incomplete",
            )
        return LocalSourceSelection(None, primary.error or "primary_incomplete")

    if primary_stalled:
        if (
            eligible_backup is not None
            and eligible_backup.complete
            and not backup_stalled
        ):
            return LocalSourceSelection(
                eligible_backup,
                "backup_selected",
                fallback_used=True,
                fallback_reason="primary_frozen",
            )
        return LocalSourceSelection(None, "local_sensor_may_be_frozen")

    if eligible_backup is None or not eligible_backup.complete or backup_stalled:
        return LocalSourceSelection(primary, "primary_selected")

    if not readings_agree(
        primary,
        eligible_backup,
        absolute_tolerance_kwh=agreement_absolute_kwh,
        relative_tolerance_percent=agreement_percent,
    ):
        return LocalSourceSelection(
            primary,
            "primary_selected_sources_disagree",
            sources_disagree=True,
        )

    return LocalSourceSelection(primary, "primary_selected")


def official_sources_changed(
    stored: dict[str, object] | None,
    current: dict[str, object],
) -> bool:
    """Only official-source changes invalidate objective comparison history."""
    if not isinstance(stored, dict):
        return False
    return any(
        stored.get(key) != current.get(key)
        for key in ("official_energy", "official_date")
    )
