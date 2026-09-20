"""Inclusion controls for Energy Consistency local meters."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EnergyConsistencyConfigEntry
from .const import (
    CONF_BACKUP_LOCAL_ENABLED,
    CONF_NAME,
    CONF_PRIMARY_LOCAL_ENABLED,
    DEFAULT_BACKUP_LOCAL_ENABLED,
    DEFAULT_NAME,
    DEFAULT_PRIMARY_LOCAL_ENABLED,
    DOMAIN,
    FRONTEND_VERSION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyConsistencyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one persistent inclusion switch for each configured meter."""
    coordinator = entry.runtime_data
    entities = [
        LocalSourceInclusionSwitch(
            entry,
            option_key=CONF_PRIMARY_LOCAL_ENABLED,
            default=DEFAULT_PRIMARY_LOCAL_ENABLED,
            role="primary",
            source_name=coordinator.primary_local_name,
        )
    ]
    if coordinator.backup_local_energy_entity:
        entities.append(
            LocalSourceInclusionSwitch(
                entry,
                option_key=CONF_BACKUP_LOCAL_ENABLED,
                default=DEFAULT_BACKUP_LOCAL_ENABLED,
                role="backup",
                source_name=coordinator.backup_local_name or "Backup local meter",
            )
        )
    async_add_entities(entities)


class LocalSourceInclusionSwitch(SwitchEntity):
    """Control whether one local meter participates in coherence decisions."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:compare-horizontal"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "include_local_source"

    def __init__(
        self,
        entry: EnergyConsistencyConfigEntry,
        *,
        option_key: str,
        default: bool,
        role: str,
        source_name: str,
    ) -> None:
        self.entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_unique_id = f"{entry.entry_id}_{role}_included"
        self._attr_translation_placeholders = {"source_name": source_name}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="Energy Consistency",
            model="Daily energy comparison",
            sw_version=FRONTEND_VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return whether this source is included in coherence."""
        return bool(self.entry.options.get(self._option_key, self._default))

    async def async_turn_on(self, **kwargs: object) -> None:
        """Include this meter without changing its Recorder history."""
        self._set_included(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Exclude this meter without changing its Recorder history."""
        self._set_included(False)

    def _set_included(self, included: bool) -> None:
        options = dict(self.entry.options)
        options[self._option_key] = included
        self.hass.config_entries.async_update_entry(self.entry, options=options)
