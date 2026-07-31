"""Energy Consistency integration."""

from __future__ import annotations

from pathlib import Path
import shutil

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    FRONTEND_VERSION,
    PLATFORMS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .coordinator import EnergyConsistencyCoordinator
from .frontend import async_register_frontend_resource

EnergyConsistencyConfigEntry = ConfigEntry[EnergyConsistencyCoordinator]

FRONTEND_URL = "/energy_consistency/energy-consistency-badge.js"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the traffic-light badge frontend module."""
    badge_path = Path(__file__).parent / "www" / "energy-consistency-badge.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(badge_path), cache_headers=True)]
    )
    await async_register_frontend_resource(hass, FRONTEND_URL, FRONTEND_VERSION)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergyConsistencyConfigEntry
) -> bool:
    """Set up Energy Consistency from a config entry."""
    coordinator = EnergyConsistencyCoordinator(hass, entry)
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergyConsistencyConfigEntry
) -> bool:
    """Unload an Energy Consistency entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove persisted comparisons and generated reports with the entry."""
    store: Store[dict] = Store(
        hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}"
    )
    await store.async_remove()
    report_dir = Path(hass.config.path(DOMAIN, "reports", entry.entry_id))
    await hass.async_add_executor_job(shutil.rmtree, report_dir, True)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
