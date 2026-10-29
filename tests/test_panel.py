"""Protocol and concurrency checks; no HA installation or radio required."""
import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest

PACKAGE = "mgroup_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/mgroup_light")]
sys.modules[PACKAGE] = package
protocol = importlib.import_module(f"{PACKAGE}.protocol")
panel_module = importlib.import_module(f"{PACKAGE}.panel")

CAPTURE = bytes.fromhex("f900100044001019040404040404040404040404")


class ProtocolTests(unittest.TestCase):
    def test_actual_capture_and_channel7_command(self):
        state = protocol.parse_status(CAPTURE)
        self.assertEqual(state.channels, (0, 0, 1, 0, 0, 0, 4, 4, 0, 0, 1, 0))
        self.assertTrue(state.master_on)
        self.assertEqual(state.brightness, 25)
        self.assertEqual(protocol.channel_command(state, 7, True).hex(), "f5001000540010")

    def test_only_one_channel_bit_changes_for_all_modes(self):
        for channel in range(1, 13):
            for raw_status in range(8):
                values = list(protocol.parse_status(CAPTURE).channels)
                values[channel - 1] = raw_status
                state = protocol.PanelState(True, tuple(values))
                command = protocol.channel_command(state, channel, not bool(raw_status & 1))
                before = bytes.fromhex("".join(format(x, "x") for x in values))
                xor = int.from_bytes(command[1:]) ^ int.from_bytes(before)
                self.assertEqual(xor.bit_count(), 1)
                self.assertEqual(xor, 1 << (4 * (12 - channel)))

    def test_noop_disabled_and_master_off(self):
        state = protocol.parse_status(CAPTURE)
        self.assertIsNone(protocol.channel_command(state, 3, True))
        with self.assertRaises(protocol.PanelError):
            protocol.channel_command(protocol.PanelState(False, state.channels), 7, True)
        with self.assertRaises(protocol.PanelError):
            protocol.channel_command(protocol.PanelState(True, (8,) * 12), 7, True)

    def test_other_packets_and_bad_states_are_ignored(self):
        for packet in [b"", b"\xf9\x00", b"\xf1" + bytes(19), b"\xf9" + b"\xff" * 6]:
            self.assertIsNone(protocol.parse_status(packet))

    def test_hazard_packet_preserves_every_other_channel_and_mode(self):
        original = protocol.parse_status(CAPTURE)
        for left_on in (False, True):
            for right_on in (False, True):
                statuses = list(original.channels)
                statuses[6:8] = [4 | int(left_on), 4 | int(right_on)]
                state = protocol.PanelState(True, tuple(statuses))
                command = protocol.channels_command(state, (7, 8), True)
                if left_on and right_on:
                    self.assertIsNone(command)
                else:
                    self.assertEqual(command.hex(), "f5001000550010")

    def test_group_validates_all_channels_before_creating_a_packet(self):
        state = protocol.parse_status(CAPTURE)
        for channels in [(), (0, 7), (7, 13)]:
            with self.assertRaises(ValueError):
                protocol.channels_command(state, channels, True)
        statuses = list(state.channels)
        statuses[7] = 8
        with self.assertRaises(protocol.PanelError):
            protocol.channels_command(protocol.PanelState(True, tuple(statuses)), (7, 8), True)


class FakeLink:
    def __init__(self):
        self.state = CAPTURE
        self.commands = []
        self.fail_write = False
        self.answer_queries = True
        self.client = None

    async def connect(self, disconnected):
        self.client = FakeClient(self, disconnected)
        return self.client


class FakeClient:
    def __init__(self, link, disconnected):
        self.link = link
        self.disconnected = disconnected
        self.is_connected = True
        self.services = self
        self.callback = None

    def get_characteristic(self, uuid):
        return types.SimpleNamespace(properties=["notify", "write-without-response"])

    async def start_notify(self, char, callback):
        self.callback = callback

    async def write_gatt_char(self, uuid, data, response):
        assert response is False
        self.link.commands.append(bytes(data))
        await asyncio.sleep(0)
        if data == b"\xf8\x00":
            if self.link.answer_queries:
                self.callback(None, bytearray(self.link.state))
        elif data[0] == 0xF5:
            if self.link.fail_write:
                raise OSError("write failed after send; delivery uncertain")
            self.link.state = b"\xf9" + data[1:] + CAPTURE[7:]
        else:
            raise AssertionError("Unexpected command")

    async def disconnect(self):
        self.is_connected = False
        self.disconnected(self)


class PanelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.link = FakeLink()
        self.updates = []
        self.panel = panel_module.Panel(self.link.connect, self.updates.append, timeout=0.05)

    async def asyncTearDown(self):
        await self.panel.close()

    async def test_query_and_setup_never_send_switch_commands(self):
        state = await self.panel.query()
        self.assertEqual(state.channels[6], 4)
        self.assertEqual(self.link.commands, [b"\xf8\x00"])

    async def test_two_simultaneous_switches_preserve_each_other(self):
        await asyncio.gather(self.panel.set_channel(7, True), self.panel.set_channel(8, True))
        state = protocol.parse_status(self.link.state)
        self.assertEqual(state.channels[6:8], (5, 5))
        self.assertEqual(state.channels[:6], protocol.parse_status(CAPTURE).channels[:6])
        writes = [c.hex() for c in self.link.commands if c[0] == 0xF5]
        self.assertEqual(writes, ["f5001000540010", "f5001000550010"])

    async def test_no_switch_without_fresh_status(self):
        self.link.answer_queries = False
        with self.assertRaises(protocol.PanelError):
            await self.panel.set_channel(7, True)
        self.assertFalse(any(c[0] == 0xF5 for c in self.link.commands))

    async def test_hazard_on_is_one_write_for_both_outputs(self):
        state = await self.panel.set_channels((7, 8), True)
        self.assertEqual(state.channels[6:8], (5, 5))
        self.assertEqual(self.link.commands, [bytes.fromhex(h) for h in [
            "f800", "f5001000550010", "f800",
        ]])
        self.assertEqual(state.channels[:6], protocol.parse_status(CAPTURE).channels[:6])
        self.assertEqual(state.channels[8:], protocol.parse_status(CAPTURE).channels[8:])

    async def test_hazard_off_is_one_write_preserving_blink_modes(self):
        self.link.state = bytes.fromhex("f9001000550010") + CAPTURE[7:]
        state = await self.panel.set_channels((7, 8), False)
        self.assertEqual(state.channels[6:8], (4, 4))
        self.assertEqual([c.hex() for c in self.link.commands if c[0] == 0xF5], ["f5001000440010"])

    async def test_hazard_and_other_switch_are_serialized(self):
        await asyncio.gather(self.panel.set_channels((7, 8), True), self.panel.set_channel(4, True))
        state = protocol.parse_status(self.link.state)
        self.assertEqual(state.channels[6:8], (5, 5))
        self.assertEqual(state.channels[3], 1)
        self.assertEqual(state.channels[2], 1)
        self.assertEqual(state.channels[10], 1)
        self.assertEqual(sum(c[0] == 0xF5 for c in self.link.commands), 2)

    async def test_hazard_disabled_side_does_not_switch_the_other(self):
        self.link.state = bytes.fromhex("f9001000480010") + CAPTURE[7:]
        with self.assertRaises(protocol.PanelError):
            await self.panel.set_channels((7, 8), True)
        self.assertFalse(any(c[0] == 0xF5 for c in self.link.commands))

    async def test_uncertain_state_write_is_never_retried(self):
        self.link.fail_write = True
        with self.assertRaises(OSError):
            await self.panel.set_channel(7, True)
        self.assertEqual(sum(c[0] == 0xF5 for c in self.link.commands), 1)
        self.assertIsNone(self.updates[-1])

    async def test_invalid_notifications_do_not_finish_query(self):
        self.link.answer_queries = False
        task = asyncio.create_task(self.panel.query())
        await asyncio.sleep(0.005)
        self.link.client.callback(None, bytearray(b"\xf1" + bytes(19)))
        self.assertFalse(task.done())
        self.link.client.callback(None, bytearray(CAPTURE))
        self.assertEqual((await task).channels[6], 4)

    async def test_disconnect_fails_query_immediately(self):
        self.link.answer_queries = False
        task = asyncio.create_task(self.panel.query())
        await asyncio.sleep(0.005)
        await self.link.client.disconnect()
        with self.assertRaises(protocol.PanelError):
            await task


if __name__ == "__main__":
    unittest.main()
