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


@dataclass(frozen=True, slots=True)
class LocalSourceSelection:
    """Result of choosing exactly one local meter."""

    reading: LocalDayReading | None
    reason: str
    fallback_used: bool = False
    fallback_reason: str | None = None


def readings_agree(
    first: LocalDayReading,
    second: LocalDayReading,
    *,
    absolute_tolerance_kwh: float,
    relative_tolerance_percent: float,
) -> bool:
    """Return whether two complete meters agree within either tolerance."""
    if first.kwh is None or second.kwh is None:
        return False
    difference = abs(first.kwh - second.kwh)
    reference = max(first.kwh, second.kwh)
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
    primary_stalled = (
        primary.complete and primary.zero_streak_hours >= zero_streak_limit_hours
    )
    backup_stalled = (
        backup is not None
        and backup.complete
        and backup.zero_streak_hours >= zero_streak_limit_hours
    )

    if not primary.complete:
        if backup is not None and backup.complete and not backup_stalled:
            return LocalSourceSelection(
                backup,
                "backup_selected",
                fallback_used=True,
                fallback_reason=primary.error or "primary_incomplete",
            )
        return LocalSourceSelection(None, primary.error or "primary_incomplete")

    if primary_stalled:
        if backup is not None and backup.complete and not backup_stalled:
            return LocalSourceSelection(
                backup,
                "backup_selected",
                fallback_used=True,
                fallback_reason="primary_frozen",
            )
        return LocalSourceSelection(None, "local_sensor_may_be_frozen")

    if backup is None or not backup.complete or backup_stalled:
        return LocalSourceSelection(primary, "primary_selected")

    if not readings_agree(
        primary,
        backup,
        absolute_tolerance_kwh=agreement_absolute_kwh,
        relative_tolerance_percent=agreement_percent,
    ):
        return LocalSourceSelection(None, "local_sources_disagree")

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
