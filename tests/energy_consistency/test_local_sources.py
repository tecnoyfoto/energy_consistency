"""Tests for local-meter priority and failover."""

from __future__ import annotations

from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[2]
CUSTOM_COMPONENTS = ROOT / "custom_components"
COMPONENT = CUSTOM_COMPONENTS / "energy_consistency"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(CUSTOM_COMPONENTS)]
sys.modules.setdefault("custom_components", custom_components)

package = types.ModuleType("custom_components.energy_consistency")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components.energy_consistency", package)

from custom_components.energy_consistency.local_sources import (  # noqa: E402
    LocalDayReading,
    official_sources_changed,
    select_local_source,
)


def reading(
    role: str,
    kwh: float | None,
    *,
    coverage: float = 100,
    zero_streak: int = 0,
    error: str | None = None,
) -> LocalDayReading:
    return LocalDayReading(
        entity_id=f"sensor.{role}",
        role=role,
        kwh=kwh,
        coverage_percent=coverage,
        zero_streak_hours=zero_streak,
        error=error,
    )


def select(primary: LocalDayReading, backup: LocalDayReading | None = None):
    return select_local_source(
        primary,
        backup,
        zero_streak_limit_hours=3,
        agreement_absolute_kwh=0.5,
        agreement_percent=5,
    )


def test_single_healthy_meter_is_used() -> None:
    result = select(reading("primary", 10.0))
    assert result.reading is not None
    assert result.reading.role == "primary"
    assert result.fallback_used is False


def test_single_incomplete_meter_is_not_accepted() -> None:
    result = select(
        reading(
            "primary",
            None,
            coverage=91.7,
            error="insufficient_local_coverage",
        )
    )
    assert result.reading is None
    assert result.reason == "insufficient_local_coverage"


def test_backup_replaces_incomplete_primary_without_adding_values() -> None:
    result = select(
        reading(
            "primary",
            None,
            coverage=87.5,
            error="insufficient_local_coverage",
        ),
        reading("backup", 11.4),
    )
    assert result.reading is not None
    assert result.reading.kwh == 11.4
    assert result.fallback_used is True
    assert result.fallback_reason == "insufficient_local_coverage"


def test_backup_replaces_primary_frozen_for_three_hours() -> None:
    result = select(
        reading("primary", 9.71, zero_streak=3),
        reading("backup", 11.55),
    )
    assert result.reading is not None
    assert result.reading.role == "backup"
    assert result.reading.kwh == 11.55
    assert result.fallback_reason == "primary_frozen"


def test_two_healthy_disagreeing_meters_are_not_cherry_picked() -> None:
    result = select(reading("primary", 10), reading("backup", 12))
    assert result.reading is None
    assert result.reason == "local_sources_disagree"


def test_healthy_primary_ignores_frozen_backup() -> None:
    result = select(
        reading("primary", 10),
        reading("backup", 8, zero_streak=3),
    )
    assert result.reading is not None
    assert result.reading.role == "primary"


def test_local_meter_changes_preserve_history() -> None:
    stored = {
        "official_energy": "sensor.official",
        "official_date": "sensor.date",
        "local_energy": "sensor.chinese",
    }
    current = {
        "official_energy": "sensor.official",
        "official_date": "sensor.date",
        "local_energy": "sensor.airzone",
        "backup_local_energy": "sensor.chinese",
    }
    assert official_sources_changed(stored, current) is False


def test_official_meter_changes_start_a_new_history() -> None:
    stored = {
        "official_energy": "sensor.official_old",
        "official_date": "sensor.date",
    }
    current = {
        "official_energy": "sensor.official_new",
        "official_date": "sensor.date",
    }
    assert official_sources_changed(stored, current) is True
