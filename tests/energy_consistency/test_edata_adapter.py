# ruff: noqa: DTZ001
# eData aggregates use local naive datetimes.
"""Tests for the optional eData history compatibility layer."""

from __future__ import annotations

import sys
import types
from pathlib import Path

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

from custom_components.energy_consistency.edata_adapter import (
    EDataAdapterState,
    resolve_edata_daily_rows,
)


@pytest.mark.parametrize(
    "edata_data",
    [
        None,
        [],
        {},
        {"test_cups": None},
        {"test_cups": {}},
        {"test_cups": {"ws_consumptions_day": None}},
        {"test_cups": {"ws_consumptions_day": []}},
    ],
)
def test_missing_history_is_explicitly_unavailable(edata_data: object) -> None:
    state, rows = resolve_edata_daily_rows(edata_data, "test_cups")
    assert state is EDataAdapterState.HISTORY_UNAVAILABLE
    assert rows == ()


def test_missing_scups_never_activates_history_adapter() -> None:
    state, rows = resolve_edata_daily_rows(
        {"test_cups": {"ws_consumptions_day": []}}, ""
    )
    assert state is EDataAdapterState.HISTORY_UNAVAILABLE
    assert rows == ()


def test_changed_internal_field_names_enable_safe_fallback() -> None:
    state, rows = resolve_edata_daily_rows(
        {
            "test_cups": {
                "ws_consumptions_day": [
                    {"date": "2026-07-27", "energy": 10.99, "hours": 24}
                ]
            }
        },
        "test_cups",
    )
    assert state is EDataAdapterState.HISTORY_UNAVAILABLE
    assert rows == ()


def test_compatible_history_is_authoritative() -> None:
    valid_row = {
        "datetime": "2026-07-27T00:00:00+02:00",
        "value_kWh": 10.99,
        "delta_h": 24,
    }
    state, rows = resolve_edata_daily_rows(
        {
            "test_cups": {
                "ws_consumptions_day": [
                    {"unexpected": "ignored"},
                    valid_row,
                ]
            }
        },
        "test_cups",
    )
    assert state is EDataAdapterState.HISTORY_AVAILABLE
    assert rows == (valid_row,)


@pytest.mark.parametrize(
    "unique_id,expected",
    [
        ("demo last_registered_day_kwh", "demo last_day_kwh"),
        ("other last_registered_day_kwh", "other last_day_kwh"),
        ("demo last_registered_day_surplus_kwh", None),
        ("demo last_day_kwh", None),
    ],
)
def test_sensor_identity_migration_is_supply_specific(unique_id, expected):
    from custom_components.energy_consistency.edata_adapter import (
        replacement_edata_unique_id,
    )

    assert replacement_edata_unique_id(unique_id) == expected


def test_both_generations_of_day_hours():
    from custom_components.energy_consistency.edata_adapter import official_day_hours

    assert official_day_hours({"last_registered_day_hours": 24}) == 24
    assert official_day_hours({"last_day_delta_h": 23}) == 23
    assert official_day_hours({}) is None
    assert (
        official_day_hours({"last_registered_day_hours": 0, "last_day_delta_h": 24})
        == 0
    )


def test_modern_edata_daily_history():
    import asyncio
    from datetime import datetime
    from types import SimpleNamespace

    from custom_components.energy_consistency.edata_adapter import (
        async_resolve_edata_daily_rows,
    )

    start = datetime(2026, 10, 11)

    class Manager:
        async def get_aggr_energy(self, *, aggregation, start):
            assert aggregation == "day"
            assert start == datetime(2026, 10, 11)
            return [
                SimpleNamespace(
                    datetime=datetime(2026, 10, 23), consumption_kwh=6.981, delta_h=24
                )
            ]

    state, rows = asyncio.run(
        async_resolve_edata_daily_rows(
            {"demo": {"data_manager": Manager()}}, "demo", start=start
        )
    )
    assert state is EDataAdapterState.HISTORY_AVAILABLE
    assert rows == (
        {"datetime": datetime(2026, 10, 23), "value_kWh": 6.981, "delta_h": 24},
    )


def test_legacy_history_does_not_call_modern_manager():
    import asyncio

    from custom_components.energy_consistency.edata_adapter import (
        async_resolve_edata_daily_rows,
    )

    row = {"datetime": "2026-10-23", "value_kWh": 6.981, "delta_h": 24}
    state, rows = asyncio.run(
        async_resolve_edata_daily_rows(
            {"demo": {"ws_consumptions_day": [row]}}, "demo", start=None
        )
    )
    assert state is EDataAdapterState.HISTORY_AVAILABLE
    assert rows == (row,)
