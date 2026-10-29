"""Exercise the actual meta-entity without loading Home Assistant."""
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

import test_discovery as discovery
import test_panel as shared


class CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator


stubs = {
    **discovery.stubs,
    "homeassistant.components.switch": discovery.module("switch", SwitchEntity=type("SwitchEntity", (), {})),
    "homeassistant.helpers.device_registry": discovery.module("device_registry", CONNECTION_BLUETOOTH="bluetooth", DeviceInfo=dict),
    "homeassistant.helpers.entity_platform": discovery.module("entity_platform", AddEntitiesCallback=object),
    "homeassistant.helpers.update_coordinator": discovery.module(
        "update_coordinator", CoordinatorEntity=CoordinatorEntity,
        DataUpdateCoordinator=discovery.CoordinatorBase, UpdateFailed=RuntimeError,
    ),
}
with patch.dict(sys.modules, stubs), patch.object(shared.package, "MgroupConfigEntry", object, create=True):
    switches = importlib.import_module(f"{shared.PACKAGE}.switch")


class HazardEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.coordinator = types.SimpleNamespace(
            address="D4:10:F2:1C:F0:8E", data=shared.protocol.parse_status(shared.CAPTURE),
            async_set_channels=AsyncMock(),
        )
        self.entity = switches.MgroupHazardSwitch(self.coordinator)

    async def test_state_requires_both_blinkers_and_master_on(self):
        for master_on in (False, True):
            for left_on in (False, True):
                for right_on in (False, True):
                    values = list(shared.protocol.parse_status(shared.CAPTURE).channels)
                    values[6:8] = [4 | int(left_on), 4 | int(right_on)]
                    self.coordinator.data = shared.protocol.PanelState(master_on, tuple(values))
                    self.assertEqual(self.entity.is_on, master_on and left_on and right_on)

    async def test_on_and_off_use_one_group_operation_each(self):
        await self.entity.async_turn_on()
        self.coordinator.async_set_channels.assert_awaited_once_with((7, 8), True)
        self.coordinator.async_set_channels.reset_mock()
        await self.entity.async_turn_off()
        self.coordinator.async_set_channels.assert_awaited_once_with((7, 8), False)

    async def test_setup_keeps_old_unique_ids_and_adds_one_meta_switch(self):
        entry = types.SimpleNamespace(runtime_data=self.coordinator, options={})
        entities = []
        await switches.async_setup_entry(None, entry, entities.extend)
        self.assertEqual(len(entities), 13)
        self.assertEqual(entities[6]._attr_unique_id, "D4:10:F2:1C:F0:8E_channel_7")
        self.assertEqual(entities[-1]._attr_unique_id, "D4:10:F2:1C:F0:8E_warnblinker")
        self.assertEqual(entities[-1]._attr_name, "Warnblinker")
        self.coordinator.async_set_channels.assert_not_awaited()
