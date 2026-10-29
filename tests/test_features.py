"""Mode configuration, RGB readback, and shutdown interception."""
import asyncio
from dataclasses import replace
import types
import unittest
from unittest.mock import AsyncMock, Mock

import test_discovery as discovery
import test_panel as shared

protocol = shared.protocol
HEADER = bytes.fromhex('02000100bc0219000101')
RGB = (12, 34, 56)


def frames(header=HEADER, colors=(RGB,)):
    palette = b''.join(bytes(c) for c in colors).ljust(42, b'\0')
    return {0xF1: b'\xf1'+header, 0xF2: b'\xf2'+palette[:18],
            0xF3: b'\xf3'+palette[18:36], 0xF4: b'\xf4'+palette[36:]}


class ModeProtocolTests(unittest.TestCase):
    def test_modes_preserve_other_circuits(self):
        state = protocol.parse_status(shared.CAPTURE)
        for mode in range(4):
            command = protocol.mode_command(state, 5, mode)
            if mode == 0:
                self.assertIsNone(command)
                continue
            result = protocol.parse_status(b'\xf9'+command[1:])
            self.assertEqual(result.channels[4], mode << 1)
            self.assertEqual(result.channels[:4], state.channels[:4])
            self.assertEqual(result.channels[5:], state.channels[5:])

    def test_live_circuit_mode_change_is_rejected(self):
        with self.assertRaises(protocol.PanelError):
            protocol.mode_command(protocol.parse_status(shared.CAPTURE), 3, 2)

    def test_disabled_or_master_off_cannot_be_reconfigured(self):
        state = protocol.parse_status(shared.CAPTURE)
        for invalid in (replace(state, master_on=False), replace(state, channels=(8,)*12)):
            with self.assertRaises(protocol.PanelError):protocol.mode_command(invalid, 5, 1)


class LightingProtocolTests(unittest.TestCase):
    def test_read_header_and_palette(self):
        state = protocol.parse_lighting(frames())
        self.assertEqual(state.colors, (RGB,))
        self.assertEqual(state.brightness, 25)
        self.assertTrue(state.is_on)

    def test_all_four_replies_are_required_and_lengths_checked(self):
        for code in frames():
            partial = frames();partial.pop(code)
            self.assertIsNone(protocol.parse_lighting(partial))
            partial = frames();partial[code] = partial[code][:-1]
            self.assertIsNone(protocol.parse_lighting(partial))

    def test_invalid_palette_count_is_rejected(self):
        header = bytearray(HEADER);header[8]=15
        self.assertIsNone(protocol.parse_lighting(frames(bytes(header))))

    def test_multicolor_palette_retains_all_colors(self):
        colors = tuple((i, i+1, i+2) for i in range(14))
        header = bytearray(HEADER);header[8]=14
        self.assertEqual(protocol.parse_lighting(frames(bytes(header),colors)).colors,colors)

    def test_rgb_is_staged_before_commit_and_preserves_unrelated_fields(self):
        state = protocol.parse_lighting(frames())
        commands = protocol.lighting_commands(state, rgb=(255,0,128), brightness=80, turn_on=True)
        self.assertEqual(commands[0], (2, bytes((255,0,128))+bytes(15)))
        self.assertEqual(commands[1][0], 1)
        self.assertEqual(commands[1][1][:3], HEADER[:3])
        self.assertEqual(commands[1][1][6],80)
        self.assertEqual(commands[1][1][7],HEADER[7])

    def test_brightness_only_does_not_replace_palette(self):
        state = protocol.parse_lighting(frames())
        commands = protocol.lighting_commands(state,brightness=200)
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][1][:6],HEADER[:6])
        self.assertEqual(commands[0][1][7:9],HEADER[7:9])

    def test_illumination_off_uses_zero_brightness_and_preserves_device_flag(self):
        state = protocol.parse_lighting(frames())
        commands = protocol.lighting_commands(state, turn_on=False)
        self.assertEqual(commands[0][1][2], HEADER[2])
        self.assertEqual(commands[0][1][6], 0)
        self.assertFalse(protocol.LightingState(commands[0][1], (RGB,)).is_on)

    def test_bad_rgb_or_brightness_is_rejected(self):
        state = protocol.parse_lighting(frames())
        for kwargs in ({'rgb':(-1,0,0)}, {'rgb':(1,2)}, {'brightness':256}, {'brightness':1.5}):
            with self.assertRaises(ValueError):protocol.lighting_commands(state,**kwargs)


class ColorClient(shared.FakeClient):
    async def write_gatt_char(self, uuid, data, response):
        if data in (b'\xf1\x00',b'\xf2\x00',b'\xf3\x00',b'\xf4\x00') and uuid.endswith('effa'):
            self.link.commands.append(bytes(data))
            if self.link.color_replies:
                self.callback(None,bytearray(self.link.frames[data[0]]))
        elif uuid.endswith('eff2'):
            self.link.commands.append(bytes(data));self.link.staged=bytes(data)
        elif uuid.endswith('eff1'):
            self.link.commands.append(bytes(data));self.link.commits+=1
            if self.link.fail_commit:raise OSError('uncertain color write')
            colors = (tuple(self.link.staged[:3]),) if self.link.staged else (RGB,)
            self.link.frames=frames(bytes(data),colors)
        else:await super().write_gatt_char(uuid,data,response)


class ColorLink(shared.FakeLink):
    def __init__(self):
        super().__init__();self.frames=frames();self.color_replies=True
        self.staged=None;self.commits=0;self.fail_commit=False

    async def connect(self, disconnected):
        self.client=ColorClient(self,disconnected);return self.client


class FeatureTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.link=ColorLink();self.updates=[]
        self.panel=shared.panel_module.Panel(self.link.connect,self.updates.append,timeout=0.02)

    async def asyncTearDown(self):await self.panel.close()

    async def test_status_and_rgb_queries_never_actuate_relays(self):
        state=await self.panel.query(include_lighting=True)
        self.assertEqual(state.lighting.colors,(RGB,))
        self.assertEqual(self.link.commands,[bytes((code,0)) for code in (0xF8,0xF1,0xF2,0xF3,0xF4)])

    async def test_channel_notification_during_rgb_query_is_not_overwritten(self):
        original = ColorClient.write_gatt_char
        async def write(client, uuid, data, response):
            await original(client, uuid, data, response)
            if data == b"\xf2\x00":
                values = list(protocol.parse_status(self.link.state).channels)
                values[4] = 1
                packet = bytes.fromhex('f9'+''.join(format(c,'x') for c in values))
                client.callback(None,bytearray(packet))
        from unittest.mock import patch
        with patch.object(ColorClient,'write_gatt_char',write):
            state=await self.panel.query(include_lighting=True)
        self.assertEqual(state.channels[4],1)
        self.assertEqual(self.updates[-1].channels[4],1)

    async def test_missing_color_reply_keeps_channel_status_available(self):
        self.link.color_replies=False
        state=await self.panel.query(include_lighting=True)
        self.assertIsNone(state.lighting)
        self.assertEqual(state.channels,protocol.parse_status(shared.CAPTURE).channels)

    async def test_disconnect_during_rgb_query_does_not_restore_stale_availability(self):
        original = ColorClient.write_gatt_char
        async def write(client, uuid, data, response):
            await original(client, uuid, data, response)
            if data == b"\xf2\x00":
                await client.disconnect()
        from unittest.mock import patch
        with patch.object(ColorClient,'write_gatt_char',write):
            with self.assertRaises(Exception):
                await self.panel.query(include_lighting=True)
        self.assertIsNone(self.updates[-1])

    async def test_rgb_write_is_read_back_and_relays_stay_unchanged(self):
        before=self.link.state
        state=await self.panel.set_lighting(rgb=(1,2,3),brightness=100,turn_on=True)
        self.assertEqual(state.lighting.colors,((1,2,3),))
        self.assertEqual(state.lighting.brightness,100)
        self.assertEqual(self.link.state,before)
        self.assertEqual(self.link.commits,1)

    async def test_failed_rgb_commit_is_not_replayed(self):
        self.link.fail_commit=True
        with self.assertRaises(OSError):await self.panel.set_lighting(rgb=(1,2,3))
        self.assertEqual(self.link.commits,1)

    async def test_color_write_requires_a_fresh_complete_snapshot(self):
        self.link.color_replies=False
        with self.assertRaises(protocol.PanelError):await self.panel.set_lighting(rgb=(1,2,3))
        self.assertEqual(self.link.commits,0)

    async def test_mode_is_confirmed_and_other_outputs_preserved(self):
        state=await self.panel.set_mode(5,1)
        self.assertEqual(state.channels[4],2)
        self.assertEqual(state.channels[2],1)


class ShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.coordinator=object.__new__(discovery.coordinator.MgroupCoordinator)
        self.coordinator.power_channel=3;self.coordinator.shutdown_channel=5
        self.coordinator.address='AA:BB:CC:DD:EE:FF';self.coordinator._closed=False
        self.coordinator._last_channels=None
        self.fire=Mock();self.coordinator._event_hass=types.SimpleNamespace(bus=types.SimpleNamespace(async_fire=self.fire))
        self.coordinator.panel=types.SimpleNamespace(set_channels=AsyncMock(),set_mode=AsyncMock())
        self.coordinator.async_set_updated_data=Mock();self.coordinator.async_set_update_error=Mock()

    async def test_software_power_off_fires_request_without_any_bluetooth_write(self):
        await self.coordinator.async_set_channel(3,False)
        self.coordinator.panel.set_channels.assert_not_awaited()
        self.fire.assert_called_once_with('mgroup_light_shutdown_requested',{'address':self.coordinator.address,'source':'software','channel':3})

    async def test_other_channels_still_use_the_panel(self):
        await self.coordinator.async_set_channel(7,False)
        self.coordinator.panel.set_channels.assert_awaited_once_with((7,),False)
        self.fire.assert_not_called()

    async def test_initial_and_reconnect_snapshot_do_not_trigger_shutdown(self):
        state=protocol.parse_status(shared.CAPTURE)
        values=list(state.channels);values[4]=1;state=replace(state,channels=tuple(values))
        self.coordinator._on_state(state)
        self.coordinator._on_state(None)
        self.coordinator._on_state(state)
        self.fire.assert_not_called()

    async def test_request_channel_rising_edge_triggers_once(self):
        state=protocol.parse_status(shared.CAPTURE)
        self.coordinator._on_state(state)
        values=list(state.channels);values[4]=1;state=replace(state,channels=tuple(values))
        self.coordinator._on_state(state);self.coordinator._on_state(state)
        self.fire.assert_called_once()

    async def test_power_channel_mode_is_protected(self):
        with self.assertRaises(RuntimeError):await self.coordinator.async_set_mode(3,1)
        self.coordinator.panel.set_mode.assert_not_awaited()
