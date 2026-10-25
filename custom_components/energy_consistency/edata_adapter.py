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


def replacement_edata_unique_id(unique_id: str) -> str | None:
    """Map only eData's renamed daily consumption identity for the same supply."""
    suffix = " last_registered_day_kwh"
    if unique_id.endswith(suffix):
        return unique_id.removesuffix(suffix) + " last_day_kwh"
    return None


def official_day_hours(attributes: dict[str, Any]) -> Any:
    """Accept both generations of eData's complete-day attribute."""
    hours = attributes.get("last_registered_day_hours")
    return attributes.get("last_day_delta_h") if hours is None else hours


async def async_resolve_edata_daily_rows(
    edata_data: Any, scups: str, *, start: Any
) -> tuple[EDataAdapterState, tuple[dict[str, Any], ...]]:
    """Read legacy shared rows or daily aggregates from modern eData."""
    state, rows = resolve_edata_daily_rows(edata_data, scups)
    if state is EDataAdapterState.HISTORY_AVAILABLE:
        return state, rows
    if not scups or not isinstance(edata_data, dict):
        return state, rows
    shared = edata_data.get(scups)
    if not isinstance(shared, dict):
        return state, rows
    manager = shared.get("data_manager")
    if manager is None or not callable(getattr(manager, "get_aggr_energy", None)):
        return state, rows
    daily = await manager.get_aggr_energy(aggregation="day", start=start)
    normalized = tuple(
        {
            "datetime": row.datetime,
            "value_kWh": row.consumption_kwh,
            "delta_h": row.delta_h,
        }
        for row in daily
        if all(hasattr(row, key) for key in ("datetime", "consumption_kwh", "delta_h"))
    )
    if not normalized:
        return EDataAdapterState.HISTORY_UNAVAILABLE, ()
    return EDataAdapterState.HISTORY_AVAILABLE, normalized
