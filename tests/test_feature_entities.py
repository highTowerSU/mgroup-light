"""Check native HA controls and read-only BCM21 access."""
import importlib
import mmap
import os
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_discovery as discovery
import test_hazard_switch as switches
import test_panel as shared
from test_features import frames


class CoordinatorEntity(switches.CoordinatorEntity):
    @property
    def available(self):
        return self.coordinator.last_update_success


stubs = {
    **discovery.stubs,
    'homeassistant.helpers.update_coordinator':discovery.module('update_coordinator',
        CoordinatorEntity=CoordinatorEntity,DataUpdateCoordinator=discovery.CoordinatorBase,UpdateFailed=RuntimeError),
    'homeassistant.helpers.entity':discovery.module('entity',EntityCategory=types.SimpleNamespace(CONFIG='config')),
    'homeassistant.components.select':discovery.module('select',SelectEntity=type('SelectEntity',(),{})),
    'homeassistant.components.button':discovery.module('button',ButtonEntity=type('ButtonEntity',(),{})),
    'homeassistant.components.binary_sensor':discovery.module('binary_sensor',BinarySensorEntity=type('BinarySensorEntity',(),{})),
    'homeassistant.components.light':discovery.module('light',LightEntity=type('LightEntity',(),{}),
        ColorMode=types.SimpleNamespace(RGB='rgb'),ATTR_BRIGHTNESS='brightness',ATTR_RGB_COLOR='rgb_color'),
}
with patch.dict(sys.modules,stubs):
    select = importlib.import_module(f'{shared.PACKAGE}.select')
    light = importlib.import_module(f'{shared.PACKAGE}.light')
    button = importlib.import_module(f'{shared.PACKAGE}.button')
    gpio = importlib.import_module(f'{shared.PACKAGE}.gpio')
    binary_sensor = importlib.import_module(f'{shared.PACKAGE}.binary_sensor')


class EntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        state=shared.protocol.parse_status(shared.CAPTURE)
        from dataclasses import replace
        self.coordinator=types.SimpleNamespace(address='AA:BB:CC:DD:EE:FF',last_update_success=True,
            data=replace(state,lighting=shared.protocol.parse_lighting(frames())),
            async_set_mode=AsyncMock(),async_set_lighting=AsyncMock(),request_shutdown=Mock())

    async def test_channel_modes_report_and_delegate(self):
        entity=select.MgroupModeSelect(self.coordinator,7,'Left')
        self.assertEqual(entity.current_option,'flash')
        await entity.async_select_option('momentary')
        self.coordinator.async_set_mode.assert_awaited_once_with(7,1)

    async def test_light_reports_current_rgb_and_palette(self):
        entity=light.MgroupPanelLight(self.coordinator)
        self.assertTrue(entity.available)
        self.assertEqual(entity.rgb_color,(12,34,56))
        self.assertEqual(entity.brightness,25)
        self.assertEqual(entity.extra_state_attributes['palette'],[[12,34,56]])

    async def test_light_unavailable_when_readback_missing(self):
        from dataclasses import replace
        self.coordinator.data=replace(self.coordinator.data,lighting=None)
        entity=light.MgroupPanelLight(self.coordinator)
        self.assertFalse(entity.available)
        self.assertIsNone(entity.rgb_color)

    async def test_light_controls_never_delegate_a_relay_operation(self):
        entity=light.MgroupPanelLight(self.coordinator)
        await entity.async_turn_on(rgb_color=[1,2,3],brightness=120)
        self.coordinator.async_set_lighting.assert_awaited_once_with(turn_on=True,rgb=(1,2,3),brightness=120)
        self.coordinator.async_set_lighting.reset_mock()
        await entity.async_turn_off()
        self.coordinator.async_set_lighting.assert_awaited_once_with(turn_on=False)

    async def test_shutdown_button_only_fires_a_request(self):
        entity=button.MgroupShutdownButton(self.coordinator)
        await entity.async_press()
        self.coordinator.request_shutdown.assert_called_once_with('button')

    async def test_strompi_signal_has_its_own_device(self):
        self.coordinator.data=True
        entity=binary_sensor.StromPiSignal(self.coordinator,self.coordinator.address)
        self.assertTrue(entity.is_on)
        self.assertEqual(entity._attr_device_info['model'],'StromPi 2')
        self.assertTrue(entity._attr_extra_state_attributes['read_only'])


class GpioTests(unittest.TestCase):
    def test_reads_gpio21_without_changing_registers(self):
        for high in (False,True):
            with tempfile.TemporaryFile() as file:
                data=bytearray(4096)
                struct.pack_into('<I',data,0x34,(1<<21) if high else 0)
                file.write(data);file.flush()
                descriptor=os.dup(file.fileno())
                with patch.object(gpio.os,'open',return_value=descriptor) as opened:
                    self.assertEqual(gpio.read_strompi2_signal(),high)
                    opened.assert_called_once_with('/dev/gpiomem',os.O_RDONLY|os.O_CLOEXEC)
                file.seek(0);self.assertEqual(file.read(),data)

    def test_does_not_reconfigure_a_non_input_pin(self):
        with tempfile.TemporaryFile() as file:
            data=bytearray(4096);struct.pack_into('<I',data,0x08,1<<3)
            file.write(data);file.flush()
            descriptor=os.dup(file.fileno())
            with patch.object(gpio.os,'open',return_value=descriptor):
                with self.assertRaises(OSError):gpio.read_strompi2_signal()
            file.seek(0);self.assertEqual(file.read(),data)
