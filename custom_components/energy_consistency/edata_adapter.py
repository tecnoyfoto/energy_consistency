"""Compatibility helpers for the optional eData history adapter."""

from __future__ import annotations

from enum import Enum
from typing import Any


class EDataAdapterState(Enum):
    """Describe whether eData history can be used authoritatively."""

    NOT_EDATA = "not_edata"
    HISTORY_AVAILABLE = "history_available"
    HISTORY_UNAVAILABLE = "history_unavailable"


_REQUIRED_DAILY_FIELDS = frozenset({"datetime", "value_kWh", "delta_h"})


def resolve_edata_daily_rows(
    edata_data: Any, scups: str
) -> tuple[EDataAdapterState, tuple[dict[str, Any], ...]]:
    """Return compatible daily rows or an explicit unavailable state.

    eData does not currently expose its historical daily values through a public
    Home Assistant API. Treat its internal structure as optional: if it is
    absent or changes, callers can safely fall back to the configured official
    sensor for its latest demonstrably complete day.
    """
    if not scups or not isinstance(edata_data, dict):
        return EDataAdapterState.HISTORY_UNAVAILABLE, ()

    scups_data = edata_data.get(scups)
    if not isinstance(scups_data, dict):
        return EDataAdapterState.HISTORY_UNAVAILABLE, ()

    rows = scups_data.get("ws_consumptions_day")
    if not isinstance(rows, list) or not rows:
        return EDataAdapterState.HISTORY_UNAVAILABLE, ()

    compatible_rows = tuple(
        row
        for row in rows
        if isinstance(row, dict) and _REQUIRED_DAILY_FIELDS <= row.keys()
    )
    if not compatible_rows:
        return EDataAdapterState.HISTORY_UNAVAILABLE, ()

    return EDataAdapterState.HISTORY_AVAILABLE, compatible_rows
