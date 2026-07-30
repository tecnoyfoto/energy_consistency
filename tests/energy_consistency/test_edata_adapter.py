"""Tests for the optional eData history compatibility layer."""

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

from custom_components.energy_consistency.edata_adapter import (  # noqa: E402
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
