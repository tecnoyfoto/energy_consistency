"""Config flow for Energy Consistency."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_BACKUP_CALIBRATION_FACTOR,
    CONF_BACKUP_LOCAL_ENABLED,
    CONF_BACKUP_LOCAL_ENERGY_ENTITY,
    CONF_BACKUP_LOCAL_NAME,
    CONF_CRITICAL_ABS_KWH,
    CONF_CRITICAL_PERCENT,
    CONF_DAILY_ZERO_STREAK_HOURS,
    CONF_FROZEN_HOURS,
    CONF_GREEN_ABS_KWH,
    CONF_GREEN_PERCENT,
    CONF_LEARNING_DAYS,
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_MAX_OFFICIAL_DELAY_DAYS,
    CONF_NAME,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_OFFICIAL_ENERGY_ENTITY,
    CONF_PRIMARY_CALIBRATION_FACTOR,
    CONF_PRIMARY_LOCAL_ENABLED,
    CONF_PRIMARY_LOCAL_NAME,
    DEFAULT_BACKUP_LOCAL_ENABLED,
    DEFAULT_BACKUP_LOCAL_NAME,
    DEFAULT_CALIBRATION_FACTOR,
    DEFAULT_CRITICAL_ABS_KWH,
    DEFAULT_CRITICAL_PERCENT,
    DEFAULT_DAILY_ZERO_STREAK_HOURS,
    DEFAULT_FROZEN_HOURS,
    DEFAULT_GREEN_ABS_KWH,
    DEFAULT_GREEN_PERCENT,
    DEFAULT_LEARNING_DAYS,
    DEFAULT_MAX_OFFICIAL_DELAY_DAYS,
    DEFAULT_NAME,
    DEFAULT_PRIMARY_LOCAL_ENABLED,
    DEFAULT_PRIMARY_LOCAL_NAME,
    DOMAIN,
)
from .coordinator import _energy_to_kwh, _parse_date


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _entry_unique_id(data: dict[str, Any]) -> str:
    """Build a stable identity from the configured source entities."""
    return "|".join(
        (
            data[CONF_OFFICIAL_ENERGY_ENTITY],
            data[CONF_OFFICIAL_DATE_ENTITY],
            data[CONF_LOCAL_ENERGY_ENTITY],
            data.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY, ""),
        )
    )


def _source_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the source selection schema with optional current defaults."""
    defaults = defaults or {}

    def required_entity(key: str) -> vol.Required:
        if key in defaults:
            return vol.Required(key, default=defaults[key])
        return vol.Required(key)

    backup = (
        vol.Optional(
            CONF_BACKUP_LOCAL_ENERGY_ENTITY,
            default=defaults[CONF_BACKUP_LOCAL_ENERGY_ENTITY],
        )
        if defaults.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY)
        else vol.Optional(CONF_BACKUP_LOCAL_ENERGY_ENTITY)
    )

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            required_entity(CONF_OFFICIAL_ENERGY_ENTITY): _entity_selector(),
            required_entity(CONF_OFFICIAL_DATE_ENTITY): _entity_selector(),
            required_entity(CONF_LOCAL_ENERGY_ENTITY): _entity_selector(),
            vol.Required(
                CONF_PRIMARY_LOCAL_NAME,
                default=defaults.get(
                    CONF_PRIMARY_LOCAL_NAME, DEFAULT_PRIMARY_LOCAL_NAME
                ),
            ): str,
            backup: _entity_selector(),
            vol.Optional(
                CONF_BACKUP_LOCAL_NAME,
                default=defaults.get(CONF_BACKUP_LOCAL_NAME, DEFAULT_BACKUP_LOCAL_NAME),
            ): str,
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
                if not user_input.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY):
                    user_input.pop(CONF_BACKUP_LOCAL_ENERGY_ENTITY, None)
                    user_input.pop(CONF_BACKUP_LOCAL_NAME, None)
                user_input[CONF_NAME] = user_input[CONF_NAME].strip()
                user_input[CONF_PRIMARY_LOCAL_NAME] = user_input[
                    CONF_PRIMARY_LOCAL_NAME
                ].strip()
                if user_input.get(CONF_BACKUP_LOCAL_NAME):
                    user_input[CONF_BACKUP_LOCAL_NAME] = user_input[
                        CONF_BACKUP_LOCAL_NAME
                    ].strip()
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
                if not user_input.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY):
                    user_input.pop(CONF_BACKUP_LOCAL_ENERGY_ENTITY, None)
                    user_input.pop(CONF_BACKUP_LOCAL_NAME, None)
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
                    user_input[CONF_PRIMARY_LOCAL_NAME] = user_input[
                        CONF_PRIMARY_LOCAL_NAME
                    ].strip()
                    if user_input.get(CONF_BACKUP_LOCAL_NAME):
                        user_input[CONF_BACKUP_LOCAL_NAME] = user_input[
                            CONF_BACKUP_LOCAL_NAME
                        ].strip()
                    return self.async_update_and_abort(
                        entry,
                        data=user_input,
                        title=user_input[CONF_NAME],
                        unique_id=unique_id,
                    )

        defaults = self._source_defaults(entry)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_source_schema(defaults),
            errors=errors,
        )

    def _validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate entities without performing I/O."""
        if not data.get(CONF_NAME, "").strip():
            return {CONF_NAME: "invalid_name"}
        if not data.get(CONF_PRIMARY_LOCAL_NAME, "").strip():
            return {CONF_PRIMARY_LOCAL_NAME: "invalid_name"}
        if data[CONF_OFFICIAL_ENERGY_ENTITY] == data[CONF_LOCAL_ENERGY_ENTITY]:
            return {"base": "sources_must_differ"}
        backup_entity = data.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY)
        if backup_entity and not data.get(CONF_BACKUP_LOCAL_NAME, "").strip():
            return {CONF_BACKUP_LOCAL_NAME: "invalid_name"}
        if backup_entity and backup_entity in {
            data[CONF_OFFICIAL_ENERGY_ENTITY],
            data[CONF_LOCAL_ENERGY_ENTITY],
        }:
            return {"base": "sources_must_differ"}
        official = self.hass.states.get(data[CONF_OFFICIAL_ENERGY_ENTITY])
        official_date = self.hass.states.get(data[CONF_OFFICIAL_DATE_ENTITY])
        local_entities = [data[CONF_LOCAL_ENERGY_ENTITY]]
        if backup_entity:
            local_entities.append(backup_entity)
        local_states = [self.hass.states.get(entity_id) for entity_id in local_entities]
        if (
            official is None
            or official_date is None
            or any(state is None for state in local_states)
        ):
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
            return {CONF_OFFICIAL_ENERGY_ENTITY: "official_completeness_unavailable"}
        for entity_id, local in zip(local_entities, local_states, strict=True):
            assert local is not None
            field = (
                CONF_LOCAL_ENERGY_ENTITY
                if entity_id == data[CONF_LOCAL_ENERGY_ENTITY]
                else CONF_BACKUP_LOCAL_ENERGY_ENTITY
            )
            if local.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) and (
                _energy_to_kwh(
                    local.state,
                    local.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                )
                is None
            ):
                return {field: "invalid_energy_entity"}
            if local.attributes.get("device_class") != "energy":
                return {field: "local_must_be_energy"}
            if local.attributes.get("state_class") not in (
                "total",
                "total_increasing",
            ):
                return {field: "local_must_be_total"}
        return {}

    def _source_defaults(self, entry: config_entries.ConfigEntry) -> dict[str, Any]:
        """Return source defaults, migrating labels from entity names in the UI."""
        defaults = dict(entry.data)
        defaults.setdefault(
            CONF_PRIMARY_LOCAL_NAME,
            self._entity_name(
                defaults.get(CONF_LOCAL_ENERGY_ENTITY), DEFAULT_PRIMARY_LOCAL_NAME
            ),
        )
        if defaults.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY):
            defaults.setdefault(
                CONF_BACKUP_LOCAL_NAME,
                self._entity_name(
                    defaults.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY),
                    DEFAULT_BACKUP_LOCAL_NAME,
                ),
            )
        return defaults

    def _entity_name(self, entity_id: str | None, fallback: str) -> str:
        state = self.hass.states.get(entity_id) if entity_id else None
        return (
            str(state.attributes.get("friendly_name", fallback)) if state else fallback
        )

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
        """Offer clearly separated source and threshold settings."""
        return self.async_show_menu(
            step_id="init", menu_options=["sources", "thresholds"]
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure local meters and whether they participate in coherence."""
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            new_data = dict(entry.data)
            for key in (
                CONF_LOCAL_ENERGY_ENTITY,
                CONF_BACKUP_LOCAL_ENERGY_ENTITY,
                CONF_PRIMARY_LOCAL_NAME,
                CONF_BACKUP_LOCAL_NAME,
            ):
                if user_input.get(key):
                    new_data[key] = (
                        user_input[key].strip()
                        if isinstance(user_input[key], str)
                        and key in {CONF_PRIMARY_LOCAL_NAME, CONF_BACKUP_LOCAL_NAME}
                        else user_input[key]
                    )
                elif key in {
                    CONF_BACKUP_LOCAL_ENERGY_ENTITY,
                    CONF_BACKUP_LOCAL_NAME,
                }:
                    new_data.pop(key, None)

            errors = EnergyConsistencyConfigFlow._validate(self, new_data)
            unique_id = _entry_unique_id(new_data)
            if not errors and any(
                other.entry_id != entry.entry_id and other.unique_id == unique_id
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                errors["base"] = "already_configured"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, data=new_data, title=new_data[CONF_NAME], unique_id=unique_id
                )
                options = dict(entry.options)
                for key in (
                    CONF_PRIMARY_LOCAL_ENABLED,
                    CONF_BACKUP_LOCAL_ENABLED,
                    CONF_PRIMARY_CALIBRATION_FACTOR,
                    CONF_BACKUP_CALIBRATION_FACTOR,
                ):
                    options[key] = user_input[key]
                return self.async_create_entry(title="", data=options)

        data = dict(entry.data)
        primary_entity = data[CONF_LOCAL_ENERGY_ENTITY]
        backup_entity = data.get(CONF_BACKUP_LOCAL_ENERGY_ENTITY)
        primary_state = self.hass.states.get(primary_entity)
        backup_state = self.hass.states.get(backup_entity) if backup_entity else None
        current = entry.options
        number = selector.NumberSelector
        factor_config = selector.NumberSelectorConfig(
            min=0.5,
            max=1.5,
            step=0.001,
            mode=selector.NumberSelectorMode.BOX,
        )
        backup_selector_key = (
            vol.Optional(CONF_BACKUP_LOCAL_ENERGY_ENTITY, default=backup_entity)
            if backup_entity
            else vol.Optional(CONF_BACKUP_LOCAL_ENERGY_ENTITY)
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCAL_ENERGY_ENTITY, default=primary_entity
                ): _entity_selector(),
                vol.Required(
                    CONF_PRIMARY_LOCAL_NAME,
                    default=data.get(
                        CONF_PRIMARY_LOCAL_NAME,
                        (
                            primary_state.attributes.get("friendly_name")
                            if primary_state
                            else DEFAULT_PRIMARY_LOCAL_NAME
                        ),
                    ),
                ): str,
                vol.Required(
                    CONF_PRIMARY_LOCAL_ENABLED,
                    default=current.get(
                        CONF_PRIMARY_LOCAL_ENABLED, DEFAULT_PRIMARY_LOCAL_ENABLED
                    ),
                ): bool,
                vol.Required(
                    CONF_PRIMARY_CALIBRATION_FACTOR,
                    default=current.get(
                        CONF_PRIMARY_CALIBRATION_FACTOR, DEFAULT_CALIBRATION_FACTOR
                    ),
                ): number(factor_config),
                backup_selector_key: _entity_selector(),
                vol.Optional(
                    CONF_BACKUP_LOCAL_NAME,
                    default=data.get(
                        CONF_BACKUP_LOCAL_NAME,
                        (
                            backup_state.attributes.get("friendly_name")
                            if backup_state
                            else DEFAULT_BACKUP_LOCAL_NAME
                        ),
                    ),
                ): str,
                vol.Required(
                    CONF_BACKUP_LOCAL_ENABLED,
                    default=current.get(
                        CONF_BACKUP_LOCAL_ENABLED, DEFAULT_BACKUP_LOCAL_ENABLED
                    ),
                ): bool,
                vol.Required(
                    CONF_BACKUP_CALIBRATION_FACTOR,
                    default=current.get(
                        CONF_BACKUP_CALIBRATION_FACTOR, DEFAULT_CALIBRATION_FACTOR
                    ),
                ): number(factor_config),
            }
        )
        return self.async_show_form(
            step_id="sources", data_schema=schema, errors=errors
        )

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage comparison and health thresholds."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_GREEN_ABS_KWH] >= user_input[CONF_CRITICAL_ABS_KWH]:
                errors[CONF_CRITICAL_ABS_KWH] = "critical_must_exceed_green"
            if user_input[CONF_GREEN_PERCENT] >= user_input[CONF_CRITICAL_PERCENT]:
                errors[CONF_CRITICAL_PERCENT] = "critical_must_exceed_green"
            if not errors:
                options = dict(self.config_entry.options)
                options.update(user_input)
                return self.async_create_entry(title="", data=options)

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
                    CONF_DAILY_ZERO_STREAK_HOURS,
                    default=current.get(
                        CONF_DAILY_ZERO_STREAK_HOURS,
                        DEFAULT_DAILY_ZERO_STREAK_HOURS,
                    ),
                ): number(config(min=2, max=12, step=1, mode=mode)),
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
            step_id="thresholds", data_schema=schema, errors=errors
        )
