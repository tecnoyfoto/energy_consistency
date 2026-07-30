"""Config flow for Energy Consistency."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CRITICAL_ABS_KWH,
    CONF_CRITICAL_PERCENT,
    CONF_FROZEN_HOURS,
    CONF_GREEN_ABS_KWH,
    CONF_GREEN_PERCENT,
    CONF_LEARNING_DAYS,
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_MAX_OFFICIAL_DELAY_DAYS,
    CONF_NAME,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_OFFICIAL_ENERGY_ENTITY,
    DEFAULT_CRITICAL_ABS_KWH,
    DEFAULT_CRITICAL_PERCENT,
    DEFAULT_FROZEN_HOURS,
    DEFAULT_GREEN_ABS_KWH,
    DEFAULT_GREEN_PERCENT,
    DEFAULT_LEARNING_DAYS,
    DEFAULT_MAX_OFFICIAL_DELAY_DAYS,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import _energy_to_kwh, _parse_date


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _entry_unique_id(data: dict[str, Any]) -> str:
    """Build a stable identity from the three source entities."""
    return "|".join(
        (
            data[CONF_OFFICIAL_ENERGY_ENTITY],
            data[CONF_OFFICIAL_DATE_ENTITY],
            data[CONF_LOCAL_ENERGY_ENTITY],
        )
    )


def _source_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the source selection schema with optional current defaults."""
    defaults = defaults or {}
    def required_entity(key: str) -> vol.Required:
        if key in defaults:
            return vol.Required(key, default=defaults[key])
        return vol.Required(key)

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            required_entity(CONF_OFFICIAL_ENERGY_ENTITY): _entity_selector(),
            required_entity(CONF_OFFICIAL_DATE_ENTITY): _entity_selector(),
            required_entity(CONF_LOCAL_ENERGY_ENTITY): _entity_selector(),
        }
    )


class EnergyConsistencyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Energy Consistency configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the source entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate(user_input)
            if not errors:
                user_input[CONF_NAME] = user_input[CONF_NAME].strip()
                await self.async_set_unique_id(_entry_unique_id(user_input))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=_source_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow source entities and the display name to be changed safely."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate(user_input)
            if not errors:
                unique_id = _entry_unique_id(user_input)
                duplicate = next(
                    (
                        other
                        for other in self.hass.config_entries.async_entries(DOMAIN)
                        if other.entry_id != entry.entry_id
                        and other.unique_id == unique_id
                    ),
                    None,
                )
                if duplicate is not None:
                    errors["base"] = "already_configured"
                else:
                    user_input[CONF_NAME] = user_input[CONF_NAME].strip()
                    return self.async_update_and_abort(
                        entry,
                        data=user_input,
                        title=user_input[CONF_NAME],
                        unique_id=unique_id,
                    )

        defaults = dict(entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_source_schema(defaults),
            errors=errors,
        )

    def _validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate entities without performing I/O."""
        if not data.get(CONF_NAME, "").strip():
            return {CONF_NAME: "invalid_name"}
        if data[CONF_OFFICIAL_ENERGY_ENTITY] == data[CONF_LOCAL_ENERGY_ENTITY]:
            return {"base": "sources_must_differ"}
        official = self.hass.states.get(data[CONF_OFFICIAL_ENERGY_ENTITY])
        official_date = self.hass.states.get(data[CONF_OFFICIAL_DATE_ENTITY])
        local = self.hass.states.get(data[CONF_LOCAL_ENERGY_ENTITY])
        if official is None or official_date is None or local is None:
            return {"base": "entity_not_found"}
        if _parse_date(official_date.state) is None:
            return {CONF_OFFICIAL_DATE_ENTITY: "invalid_date_entity"}
        if (
            _energy_to_kwh(
                official.state, official.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            )
            is None
        ):
            return {CONF_OFFICIAL_ENERGY_ENTITY: "invalid_energy_entity"}
        official_hours = official.attributes.get("last_registered_day_hours")
        entity_entry = er.async_get(self.hass).async_get(
            data[CONF_OFFICIAL_ENERGY_ENTITY]
        )
        source_entry = (
            self.hass.config_entries.async_get_entry(entity_entry.config_entry_id)
            if entity_entry is not None and entity_entry.config_entry_id is not None
            else None
        )
        if official_hours is None and (
            source_entry is None or source_entry.domain != "edata"
        ):
            return {
                CONF_OFFICIAL_ENERGY_ENTITY: "official_completeness_unavailable"
            }
        if (
            _energy_to_kwh(local.state, local.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
            is None
        ):
            return {CONF_LOCAL_ENERGY_ENTITY: "invalid_energy_entity"}
        if local.attributes.get("device_class") != "energy":
            return {CONF_LOCAL_ENERGY_ENTITY: "local_must_be_energy"}
        if local.attributes.get("state_class") not in ("total", "total_increasing"):
            return {CONF_LOCAL_ENERGY_ENTITY: "local_must_be_total"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EnergyConsistencyOptionsFlow:
        """Return the options flow."""
        return EnergyConsistencyOptionsFlow()


class EnergyConsistencyOptionsFlow(config_entries.OptionsFlow):
    """Configure tolerances and health thresholds."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_GREEN_ABS_KWH] >= user_input[CONF_CRITICAL_ABS_KWH]:
                errors[CONF_CRITICAL_ABS_KWH] = "critical_must_exceed_green"
            if user_input[CONF_GREEN_PERCENT] >= user_input[CONF_CRITICAL_PERCENT]:
                errors[CONF_CRITICAL_PERCENT] = "critical_must_exceed_green"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        number = selector.NumberSelector
        config = selector.NumberSelectorConfig
        mode = selector.NumberSelectorMode.BOX
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GREEN_ABS_KWH,
                    default=current.get(CONF_GREEN_ABS_KWH, DEFAULT_GREEN_ABS_KWH),
                ): number(config(min=0, max=20, step=0.1, mode=mode)),
                vol.Required(
                    CONF_GREEN_PERCENT,
                    default=current.get(CONF_GREEN_PERCENT, DEFAULT_GREEN_PERCENT),
                ): number(config(min=0, max=100, step=0.5, mode=mode)),
                vol.Required(
                    CONF_CRITICAL_ABS_KWH,
                    default=current.get(
                        CONF_CRITICAL_ABS_KWH, DEFAULT_CRITICAL_ABS_KWH
                    ),
                ): number(config(min=0, max=100, step=0.1, mode=mode)),
                vol.Required(
                    CONF_CRITICAL_PERCENT,
                    default=current.get(
                        CONF_CRITICAL_PERCENT, DEFAULT_CRITICAL_PERCENT
                    ),
                ): number(config(min=0, max=500, step=0.5, mode=mode)),
                vol.Required(
                    CONF_LEARNING_DAYS,
                    default=current.get(CONF_LEARNING_DAYS, DEFAULT_LEARNING_DAYS),
                ): number(config(min=1, max=30, step=1, mode=mode)),
                vol.Required(
                    CONF_FROZEN_HOURS,
                    default=current.get(CONF_FROZEN_HOURS, DEFAULT_FROZEN_HOURS),
                ): number(config(min=0.5, max=48, step=0.5, mode=mode)),
                vol.Required(
                    CONF_MAX_OFFICIAL_DELAY_DAYS,
                    default=current.get(
                        CONF_MAX_OFFICIAL_DELAY_DAYS,
                        DEFAULT_MAX_OFFICIAL_DELAY_DAYS,
                    ),
                ): number(config(min=1, max=30, step=1, mode=mode)),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
