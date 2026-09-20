"""Diagnostics for Energy Consistency."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import EnergyConsistencyConfigEntry
from .const import (
    CONF_BACKUP_LOCAL_ENERGY_ENTITY,
    CONF_BACKUP_LOCAL_NAME,
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_NAME,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_OFFICIAL_ENERGY_ENTITY,
    CONF_PRIMARY_LOCAL_NAME,
)

TO_REDACT_ENTRY = {
    CONF_NAME,
    CONF_OFFICIAL_ENERGY_ENTITY,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_BACKUP_LOCAL_ENERGY_ENTITY,
    CONF_PRIMARY_LOCAL_NAME,
    CONF_BACKUP_LOCAL_NAME,
}
TO_REDACT_RECORD = {
    "official_kwh",
    "local_kwh",
    "local_source_entity",
    "primary_local_kwh",
    "backup_local_kwh",
    "primary_adjusted_kwh",
    "backup_adjusted_kwh",
    "local_source_name",
    "primary_local_name",
    "backup_local_name",
}
TO_REDACT_SNAPSHOT = {
    "official_kwh",
    "local_kwh",
    "local_source_entity",
    "primary_local_kwh",
    "backup_local_kwh",
    "primary_adjusted_kwh",
    "backup_adjusted_kwh",
    "local_source_name",
    "primary_local_name",
    "backup_local_name",
}


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
        "snapshot": async_redact_data(asdict(coordinator.data), TO_REDACT_SNAPSHOT),
        "records": [
            async_redact_data(record.as_dict(), TO_REDACT_RECORD)
            for record in coordinator.records[-31:]
        ],
    }
