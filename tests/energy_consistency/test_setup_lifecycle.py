"""Failed setup must not leak source listeners or delayed refresh timers."""

import asyncio
from asyncio import CancelledError
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tests.support.source_loader import load_methods


@pytest.mark.parametrize("stage", ["initialize", "refresh", "platforms"])
def test_failed_setup_cleans_up_its_coordinator(stage):
    coordinator = SimpleNamespace(
        async_initialize=AsyncMock(),
        async_config_entry_first_refresh=AsyncMock(),
        async_shutdown=AsyncMock(),
    )
    forward = AsyncMock()
    {
        "initialize": coordinator.async_initialize,
        "refresh": coordinator.async_config_entry_first_refresh,
        "platforms": forward,
    }[stage].side_effect = RuntimeError("simulated setup failure")
    ns = {
        "CancelledError": CancelledError,
        "EnergyConsistencyCoordinator": lambda hass, entry: coordinator,
        "PLATFORMS": ["sensor", "switch"],
        "_async_reload_entry": Mock(),
    }
    load_methods("__init__.py", {"async_setup_entry"}, ns)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_forward_entry_setups=forward)
    )
    entry = SimpleNamespace(add_update_listener=Mock(), async_on_unload=Mock())
    with pytest.raises(RuntimeError, match="simulated setup failure"):
        asyncio.run(ns["async_setup_entry"](hass, entry))
    coordinator.async_shutdown.assert_awaited_once()
    entry.add_update_listener.assert_not_called()


def test_successful_setup_attaches_reload_listener_once():
    coordinator = SimpleNamespace(
        async_initialize=AsyncMock(),
        async_config_entry_first_refresh=AsyncMock(),
        async_shutdown=AsyncMock(),
    )
    ns = {
        "CancelledError": CancelledError,
        "EnergyConsistencyCoordinator": lambda hass, entry: coordinator,
        "PLATFORMS": ["sensor", "switch"],
        "_async_reload_entry": Mock(),
    }
    load_methods("__init__.py", {"async_setup_entry"}, ns)
    forward = AsyncMock()
    entry = SimpleNamespace(add_update_listener=Mock(), async_on_unload=Mock())
    assert asyncio.run(
        ns["async_setup_entry"](
            SimpleNamespace(
                config_entries=SimpleNamespace(async_forward_entry_setups=forward)
            ),
            entry,
        )
    )
    assert entry.runtime_data is coordinator
    entry.add_update_listener.assert_called_once()
    coordinator.async_shutdown.assert_not_awaited()
