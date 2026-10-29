"""Check the real discovery helper with HA's radio API replaced by a fake."""
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_panel as shared


def module(name, **attrs):
    result = types.ModuleType(name)
    result.__dict__.update(attrs)
    return result


class CoordinatorBase:
    def __class_getitem__(cls, item):
        return cls


radio = module("homeassistant.components.bluetooth")
stubs = {
    "bleak": module("bleak", BleakClient=object),
    "bleak_retry_connector": module("bleak_retry_connector", establish_connection=AsyncMock()),
    "homeassistant": module("homeassistant"),
    "homeassistant.components": module("homeassistant.components", bluetooth=radio),
    "homeassistant.components.bluetooth": radio,
    "homeassistant.config_entries": module("homeassistant.config_entries", ConfigEntry=object),
    "homeassistant.core": module("homeassistant.core", HomeAssistant=object, callback=lambda f: f),
    "homeassistant.exceptions": module("homeassistant.exceptions", HomeAssistantError=RuntimeError),
    "homeassistant.helpers": module("homeassistant.helpers"),
    "homeassistant.helpers.update_coordinator": module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=CoordinatorBase, UpdateFailed=RuntimeError,
    ),
}
with patch.dict(sys.modules, stubs):
    coordinator = importlib.import_module(f"{shared.PACKAGE}.coordinator")


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        radio.async_last_service_info = Mock(return_value=None)
        radio.async_process_advertisements = AsyncMock()
        radio.BluetoothScanningMode = types.SimpleNamespace(ACTIVE="active")
        self.address = "D4:10:F2:1C:F0:8E"

    async def test_known_device_does_not_start_active_scan(self):
        cached = object()
        radio.async_last_service_info.return_value = cached
        self.assertIs(await coordinator.async_panel_service_info(None, self.address), cached)
        radio.async_process_advertisements.assert_not_awaited()

    async def test_missing_device_gets_address_specific_active_window(self):
        found = types.SimpleNamespace(address=self.address)
        radio.async_process_advertisements.return_value = found
        self.assertIs(await coordinator.async_panel_service_info(None, self.address), found)
        args = radio.async_process_advertisements.await_args.args
        self.assertTrue(args[1](found))
        self.assertFalse(args[1](types.SimpleNamespace(address="00:00:00:00:00:00")))
        self.assertEqual(args[2], {"address": self.address, "connectable": True})
        self.assertEqual(args[3:], ("active", 25))

    async def test_reconnect_can_refresh_an_old_advertisement(self):
        radio.async_last_service_info.return_value = object()
        await coordinator.async_panel_service_info(None, self.address, refresh=True)
        radio.async_process_advertisements.assert_awaited_once()
        radio.async_last_service_info.assert_not_called()

    async def test_missing_radio_response_becomes_panel_error(self):
        radio.async_process_advertisements.side_effect = TimeoutError
        with self.assertRaises(shared.protocol.PanelError):
            await coordinator.async_panel_service_info(None, self.address)
