"""Sensor entities for Energy Consistency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    FRONTEND_VERSION,
    STATUS_CRITICAL,
    STATUS_DATA_ISSUE,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_OPTIONS,
    STATUS_WAITING,
    STATUS_WARNING,
)
from .coordinator import EnergyConsistencyCoordinator
from . import EnergyConsistencyConfigEntry


@dataclass(frozen=True, kw_only=True)
class EnergyConsistencySensorDescription(SensorEntityDescription):
    """Describe an Energy Consistency sensor."""

    data_key: str


SENSORS = (
    EnergyConsistencySensorDescription(
        key="official_energy",
        translation_key="official_energy",
        data_key="official_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="local_energy",
        translation_key="local_energy",
        data_key="local_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="difference",
        translation_key="difference",
        data_key="difference_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="difference_percent",
        translation_key="difference_percent",
        data_key="difference_percent",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="coverage",
        translation_key="coverage",
        data_key="coverage_percent",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="comparison_date",
        translation_key="comparison_date",
        data_key="comparison_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EnergyConsistencySensorDescription(
        key="official_delay",
        translation_key="official_delay",
        data_key="official_delay_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyConsistencyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Consistency sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [EnergyConsistencyStatusSensor(coordinator, entry)]
        + [
            EnergyConsistencyValueSensor(coordinator, entry, description)
            for description in SENSORS
        ]
    )


class EnergyConsistencyBaseSensor(
    CoordinatorEntity[EnergyConsistencyCoordinator], SensorEntity
):
    """Base Energy Consistency sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnergyConsistencyCoordinator,
        entry: EnergyConsistencyConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="Energy Consistency",
            model="Daily energy comparison",
            sw_version=FRONTEND_VERSION,
        )


class EnergyConsistencyStatusSensor(EnergyConsistencyBaseSensor):
    """Overall traffic-light state."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "status"
    _unrecorded_attributes = frozenset(
        {
            "reason",
            "valid_days",
            "warning_days_last_7",
            "critical_days_last_7",
            "comparison_date",
            "official_kwh",
            "local_kwh",
            "difference_kwh",
            "difference_percent",
            "coverage_percent",
            "official_delay_days",
            "official_hours",
            "expected_official_hours",
            "pending_official_hours",
            "pending_expected_official_hours",
            "using_cached_result",
            "pending_sources",
            "recent_comparisons",
        }
    )

    def __init__(
        self,
        coordinator: EnergyConsistencyCoordinator,
        entry: EnergyConsistencyConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status

    @property
    def icon(self) -> str:
        return {
            STATUS_OK: "mdi:check-circle",
            STATUS_LEARNING: "mdi:school",
            STATUS_WAITING: "mdi:clock-outline",
            STATUS_DATA_ISSUE: "mdi:database-alert",
            STATUS_WARNING: "mdi:alert",
            STATUS_CRITICAL: "mdi:alert-octagon",
        }.get(self.coordinator.data.status, "mdi:compare")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "reason": data.reason,
            "valid_days": data.valid_days,
            "warning_days_last_7": data.warning_days,
            "critical_days_last_7": data.critical_days,
            "comparison_date": data.comparison_date,
            "official_kwh": data.official_kwh,
            "local_kwh": data.local_kwh,
            "difference_kwh": data.difference_kwh,
            "difference_percent": data.difference_percent,
            "coverage_percent": data.coverage_percent,
            "official_delay_days": data.official_delay_days,
            "official_hours": data.official_hours,
            "expected_official_hours": data.expected_official_hours,
            "pending_official_hours": data.pending_official_hours,
            "pending_expected_official_hours": data.pending_expected_official_hours,
            "using_cached_result": data.using_cached_result,
            "pending_sources": list(data.pending_sources),
            "recent_comparisons": [
                {
                    "date": record.date,
                    "official_kwh": record.official_kwh,
                    "local_kwh": record.local_kwh,
                    "difference_kwh": record.difference_kwh,
                    "difference_percent": record.difference_percent,
                    "coverage_percent": record.coverage_percent,
                    "official_hours": record.official_hours,
                    "expected_official_hours": record.expected_official_hours,
                    "status": record.status,
                    "reason": record.reason,
                }
                for record in self.coordinator.records[-7:]
            ],
        }


class EnergyConsistencyValueSensor(EnergyConsistencyBaseSensor):
    """Expose one value from the coordinator snapshot."""

    entity_description: EnergyConsistencySensorDescription

    def __init__(
        self,
        coordinator: EnergyConsistencyCoordinator,
        entry: EnergyConsistencyConfigEntry,
        description: EnergyConsistencySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        value = getattr(self.coordinator.data, self.entity_description.data_key)
        if self.entity_description.device_class == SensorDeviceClass.DATE and value:
            return date.fromisoformat(value)
        return value
