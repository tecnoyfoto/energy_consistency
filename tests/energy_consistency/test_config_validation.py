"""Validate first installation and reconfiguration during source outages."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from custom_components.energy_consistency import const
from custom_components.energy_consistency.edata_adapter import official_day_hours
from tests.support.source_loader import load_methods


def validate(
    *,
    official="10",
    day="2026-10-23",
    local="1000",
    attributes=None,
    allow_unavailable=False,
    edata=False,
):
    def parse(value):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    states = {
        "sensor.official": SimpleNamespace(
            state=official,
            attributes=attributes
            or {"unit_of_measurement": "kWh", "last_day_delta_h": 24},
        ),
        "sensor.day": SimpleNamespace(state=day, attributes={}),
        "sensor.local": SimpleNamespace(
            state=local,
            attributes={
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "state_class": "total_increasing",
            },
        ),
    }
    ns = {key: getattr(const, key) for key in dir(const) if key.isupper()}
    ns.update(
        {
            "STATE_UNKNOWN": "unknown",
            "STATE_UNAVAILABLE": "unavailable",
            "ATTR_UNIT_OF_MEASUREMENT": "unit_of_measurement",
            "official_day_hours": official_day_hours,
            "_parse_date": parse,
            "math": __import__("math"),
            "er": SimpleNamespace(
                async_get=lambda hass: SimpleNamespace(
                    async_get=lambda entity: (
                        SimpleNamespace(config_entry_id="supply") if edata else None
                    )
                )
            ),
        }
    )
    load_methods("coordinator.py", {"_energy_to_kwh"}, ns)
    load_methods("config_flow.py", {"_validate"}, ns)
    hass = SimpleNamespace(
        states=SimpleNamespace(get=states.get),
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry_id: SimpleNamespace(domain="edata")
        ),
    )
    data = {
        "name": "Comparison",
        "primary_local_name": "Primary",
        "official_energy_entity": "sensor.official",
        "official_date_entity": "sensor.day",
        "local_energy_entity": "sensor.local",
    }
    return ns["_validate"](
        SimpleNamespace(hass=hass), data, allow_unavailable=allow_unavailable
    )


def test_new_installation_accepts_modern_official_hours():
    assert validate() == {}


def test_new_installation_accepts_legacy_official_hours():
    assert (
        validate(
            attributes={"unit_of_measurement": "kWh", "last_registered_day_hours": 24}
        )
        == {}
    )


def test_new_installation_requires_valid_official_value():
    assert validate(official="unavailable", edata=True) == {
        "official_energy_entity": "invalid_energy_entity"
    }


def test_reconfiguration_remains_available_during_an_outage():
    assert (
        validate(
            official="unavailable",
            day="unknown",
            local="unavailable",
            allow_unavailable=True,
            edata=True,
        )
        == {}
    )


def test_first_installation_rejects_sensor_without_complete_day_evidence():
    assert validate(attributes={"unit_of_measurement": "kWh"}) == {
        "official_energy_entity": "official_completeness_unavailable"
    }


def test_registered_edata_sensor_can_wait_for_history():
    assert validate(attributes={"unit_of_measurement": "kWh"}, edata=True) == {}


def test_local_options_are_committed_atomically_without_losing_thresholds():
    import asyncio
    from unittest.mock import Mock

    ns = {key: getattr(const, key) for key in dir(const) if key.isupper()}
    ns["EnergyConsistencyConfigFlow"] = SimpleNamespace(
        _validate=lambda self, data, **kwargs: {}
    )
    load_methods("config_flow.py", {"async_step_sources", "_entry_unique_id"}, ns)
    entry = SimpleNamespace(
        entry_id="comparison",
        data={
            "name": "Comparison",
            "official_energy_entity": "sensor.official",
            "official_date_entity": "sensor.day",
            "local_energy_entity": "sensor.old",
            "backup_local_energy_entity": "sensor.old_backup",
            "primary_local_name": "Primary",
        },
        options={"green_abs_kwh": 0.7},
    )
    update = Mock()
    flow = SimpleNamespace(
        config_entry=entry,
        hass=SimpleNamespace(
            config_entries=SimpleNamespace(
                async_entries=lambda domain: [], async_update_entry=update
            )
        ),
        async_create_entry=lambda **kwargs: kwargs,
    )
    user = {
        "local_energy_entity": "sensor.new",
        "primary_local_name": "New primary",
        "primary_local_enabled": True,
        "backup_local_enabled": False,
        "primary_calibration_factor": 1.05,
        "backup_calibration_factor": 1.0,
    }
    result = asyncio.run(ns["async_step_sources"](flow, user))
    update.assert_called_once()
    committed = update.call_args.kwargs
    assert committed["data"]["local_energy_entity"] == "sensor.new"
    assert "backup_local_energy_entity" not in committed["data"]
    assert committed["options"]["green_abs_kwh"] == 0.7
    assert committed["options"]["primary_calibration_factor"] == 1.05
    assert result["data"] == committed["options"]
