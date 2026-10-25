"""Exercise source migration without requiring a Home Assistant installation."""

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

from custom_components.energy_consistency.edata_adapter import (
    replacement_edata_unique_id,
)


def migrate_fixture(*, replacement_supply="demo", stored_source="sensor.old"):
    source = (
        Path(__file__).parents[2]
        / "custom_components/energy_consistency/coordinator.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "_migrate_edata_source"
    )
    old = SimpleNamespace(
        platform="edata",
        config_entry_id="supply-one",
        unique_id="demo last_registered_day_kwh",
    )
    new = SimpleNamespace(
        platform="edata",
        unique_id=f"{replacement_supply} last_day_kwh",
        disabled_by=None,
        entity_id="sensor.new",
    )
    entry = SimpleNamespace(
        entry_id="consistency", data={"official_energy_entity": "sensor.old"}
    )
    changes = []
    entries = SimpleNamespace(
        async_entries=lambda domain: [entry],
        async_update_entry=lambda *args, **kwargs: changes.append(kwargs),
    )
    namespace = {
        "Any": object,
        "er": SimpleNamespace(
            async_get=lambda hass: SimpleNamespace(async_get=lambda entity: old),
            async_entries_for_config_entry=lambda registry, entry_id: [new],
        ),
        "replacement_edata_unique_id": replacement_edata_unique_id,
        "CONF_OFFICIAL_ENERGY_ENTITY": "official_energy_entity",
        "DOMAIN": "energy_consistency",
        "_LOGGER": logging.getLogger(__name__),
    }
    exec(  # noqa: S102 - isolate a trusted local method from Home Assistant imports.
        compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"),
        namespace,
    )
    coordinator = SimpleNamespace(
        hass=SimpleNamespace(config_entries=entries),
        entry=entry,
        official_energy_entity="sensor.old",
        official_date_entity="sensor.date",
        local_energy_entity="sensor.local",
        backup_local_energy_entity=None,
    )
    stored = {
        "sources": {"official_energy": stored_source, "official_date": "sensor.date"},
        "records": [{"date": "2026-10-17"}],
    }
    migrated = namespace["_migrate_edata_source"](coordinator, stored)
    return migrated, coordinator, stored, changes


def test_same_supply_migrates_without_losing_comparisons():
    migrated, coordinator, stored, changes = migrate_fixture()
    assert migrated
    assert coordinator.official_energy_entity == "sensor.new"
    assert stored["sources"]["official_energy"] == "sensor.new"
    assert stored["records"] == [{"date": "2026-10-17"}]
    assert changes[0]["data"]["official_energy_entity"] == "sensor.new"


def test_another_supply_cannot_be_selected():
    migrated, coordinator, _stored, changes = migrate_fixture(
        replacement_supply="other"
    )
    assert not migrated
    assert coordinator.official_energy_entity == "sensor.old"
    assert not changes


def test_unrelated_stored_source_is_not_relabelled():
    migrated, _coordinator, stored, _changes = migrate_fixture(
        stored_source="sensor.another_supply"
    )
    assert migrated
    assert stored["sources"]["official_energy"] == "sensor.another_supply"
