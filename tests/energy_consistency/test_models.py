"""Tests for persisted Energy Consistency records."""

from __future__ import annotations

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

from custom_components.energy_consistency.models import (  # noqa: E402
    COMPARISON_ALGORITHM_VERSION,
    DailyComparison,
)


LEGACY_RECORD = {
    "date": "2026-07-26",
    "official_kwh": 6.18,
    "local_kwh": 6.17,
    "difference_kwh": -0.01,
    "difference_percent": -0.16,
    "coverage_percent": 100.0,
    "status": "ok",
    "reason": "within_tolerance",
}


def test_legacy_record_loads_without_losing_measurements() -> None:
    record = DailyComparison.from_dict(LEGACY_RECORD)
    assert record.date == "2026-07-26"
    assert record.official_kwh == pytest.approx(6.18)
    assert record.algorithm_version == 1
    assert record.official_hours is None


def test_new_record_round_trip_preserves_audit_metadata() -> None:
    original = DailyComparison(
        **LEGACY_RECORD,
        official_hours=24,
        expected_official_hours=24,
        green_abs_kwh=0.5,
        green_percent=5,
        critical_abs_kwh=2,
        critical_percent=15,
        min_coverage_percent=100,
    )
    restored = DailyComparison.from_dict(original.as_dict())
    assert restored == original
    assert restored.algorithm_version == COMPARISON_ALGORITHM_VERSION


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("date", "../../x"),
        ("official_kwh", float("nan")),
        ("local_kwh", -1),
        ("coverage_percent", 101),
        ("status", "unexpected"),
    ],
)
def test_invalid_stored_records_are_rejected(key: str, value: object) -> None:
    damaged = {**LEGACY_RECORD, key: value}
    with pytest.raises((TypeError, ValueError)):
        DailyComparison.from_dict(damaged)
