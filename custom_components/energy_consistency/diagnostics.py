"""Diagnostics for Energy Consistency."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import (
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_NAME,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_OFFICIAL_ENERGY_ENTITY,
)
from . import EnergyConsistencyConfigEntry

TO_REDACT_ENTRY = {
    CONF_NAME,
    CONF_OFFICIAL_ENERGY_ENTITY,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_LOCAL_ENERGY_ENTITY,
}
TO_REDACT_RECORD = {"official_kwh", "local_kwh"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnergyConsistencyConfigEntry
) -> dict[str, Any]:
    """Return non-sensitive diagnostics."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT_ENTRY),
            "options": dict(entry.options),
        },
        "snapshot": asdict(coordinator.data),
        "records": [
            async_redact_data(record.as_dict(), TO_REDACT_RECORD)
            for record in coordinator.records[-31:]
        ],
    }
