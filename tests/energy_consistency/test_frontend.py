"""Tests for persistent frontend resource registration."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[2]
CUSTOM_COMPONENTS = ROOT / "custom_components"
COMPONENT = CUSTOM_COMPONENTS / "energy_consistency"

custom_components = sys.modules.setdefault(
    "custom_components", types.ModuleType("custom_components")
)
custom_components.__path__ = [str(CUSTOM_COMPONENTS)]
package = sys.modules.setdefault(
    "custom_components.energy_consistency",
    types.ModuleType("custom_components.energy_consistency"),
)
package.__path__ = [str(COMPONENT)]

homeassistant = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
ha_frontend = types.ModuleType("homeassistant.components.frontend")
lovelace = types.ModuleType("homeassistant.components.lovelace")
resources_module = types.ModuleType("homeassistant.components.lovelace.resources")
core = types.ModuleType("homeassistant.core")


class ResourceStorageCollection:
    """Test marker matching Home Assistant's storage resource collection."""


ha_frontend.add_extra_js_url = lambda hass, url: None
resources_module.ResourceStorageCollection = ResourceStorageCollection
core.HomeAssistant = object
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.components", components)
sys.modules.setdefault("homeassistant.components.frontend", ha_frontend)
sys.modules.setdefault("homeassistant.components.lovelace", lovelace)
sys.modules.setdefault("homeassistant.components.lovelace.resources", resources_module)
sys.modules.setdefault("homeassistant.core", core)

from custom_components.energy_consistency import frontend  # noqa: E402


class StoredResources(ResourceStorageCollection):
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.loaded = False
        self.created: dict | None = None
        self.updated: tuple[str, dict] | None = None

    async def async_get_info(self) -> None:
        self.loaded = True

    def async_items(self) -> list[dict]:
        return self.items

    async def async_create_item(self, data: dict) -> None:
        self.created = data

    async def async_update_item(self, item_id: str, data: dict) -> None:
        self.updated = (item_id, data)


class YamlResources:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    async def async_get_info(self) -> None:
        return None

    def async_items(self) -> list[dict]:
        return self.items


def _hass(resources: object) -> object:
    return types.SimpleNamespace(
        data={"lovelace": types.SimpleNamespace(resources=resources)}
    )


def test_creates_persistent_resource() -> None:
    resources = StoredResources([])
    asyncio.run(
        frontend.async_register_frontend_resource(
            _hass(resources), "/energy/test.js", "1.2.3"
        )
    )
    assert resources.loaded
    assert resources.created == {
        "res_type": "module",
        "url": "/energy/test.js?v=1.2.3",
    }


def test_updates_existing_resource_version() -> None:
    resources = StoredResources(
        [{"id": "resource-id", "type": "module", "url": "/energy/test.js?v=1"}]
    )
    asyncio.run(
        frontend.async_register_frontend_resource(
            _hass(resources), "/energy/test.js", "2"
        )
    )
    assert resources.updated == (
        "resource-id",
        {"res_type": "module", "url": "/energy/test.js?v=2"},
    )


def test_current_resource_is_unchanged() -> None:
    resources = StoredResources(
        [{"id": "resource-id", "type": "module", "url": "/energy/test.js?v=2"}]
    )
    asyncio.run(
        frontend.async_register_frontend_resource(
            _hass(resources), "/energy/test.js", "2"
        )
    )
    assert resources.created is None
    assert resources.updated is None


def test_yaml_mode_uses_extra_module_fallback(monkeypatch) -> None:
    loaded: list[str] = []
    monkeypatch.setattr(frontend, "add_extra_js_url", lambda hass, url: loaded.append(url))
    asyncio.run(
        frontend.async_register_frontend_resource(
            _hass(YamlResources([])), "/energy/test.js", "2"
        )
    )
    assert loaded == ["/energy/test.js?v=2"]
