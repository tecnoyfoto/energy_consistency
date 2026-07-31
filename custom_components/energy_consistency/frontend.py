"""Frontend resource registration for Energy Consistency."""

from __future__ import annotations

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant


async def async_register_frontend_resource(
    hass: HomeAssistant, resource_url: str, version: str
) -> None:
    """Register a persistent Lovelace module, with a YAML-mode fallback."""
    versioned_url = f"{resource_url}?v={version}"
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()

    for item in resources.async_items():
        if item.get("url", "").partition("?")[0] != resource_url:
            continue

        if item["url"] == versioned_url and item.get("type") == "module":
            return

        if isinstance(resources, ResourceStorageCollection):
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": versioned_url}
            )
        else:
            item["url"] = versioned_url
        return

    if isinstance(resources, ResourceStorageCollection):
        await resources.async_create_item(
            {"res_type": "module", "url": versioned_url}
        )
    else:
        # YAML-managed Lovelace resources cannot be changed persistently.
        add_extra_js_url(hass, versioned_url)
