"""Exercise setup navigation, duplicate checks, and saved channel labels."""
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

try:
    import voluptuous
except ImportError:
    voluptuous = None

import test_discovery as discovery
import test_panel as shared


class FlowBase:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    def __init__(self):
        self.hass = object()
        self.configured = []

    def _async_current_entries(self):
        return self.configured

    async def async_set_unique_id(self, unique_id, **kwargs):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        if any(e.unique_id == self.unique_id for e in self.configured):
            raise RuntimeError('already_configured')

    def async_show_form(self, **kwargs):
        return {'type': 'form', **kwargs}

    def async_create_entry(self, **kwargs):
        return {'type': 'create_entry', **kwargs}


@unittest.skipIf(voluptuous is None, 'Install voluptuous to test UI forms')
class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        entries = discovery.module('config_entries', ConfigFlow=FlowBase, OptionsFlow=FlowBase, ConfigEntry=object)
        radio = discovery.module('bluetooth', BluetoothServiceInfoBleak=object,
                                 async_discovered_service_info=lambda *a, **kw: [])
        stubs = {
            **discovery.stubs,
            'homeassistant': discovery.module('homeassistant', config_entries=entries),
            'homeassistant.config_entries': entries,
            'homeassistant.components': discovery.module('components', bluetooth=radio),
            'homeassistant.components.bluetooth': radio,
        }
        # Import the actual config flow while only replacing HA's host framework.
        sys.modules.pop(f'{shared.PACKAGE}.config_flow', None)
        with patch.dict(sys.modules, stubs):
            self.module = importlib.import_module(f'{shared.PACKAGE}.config_flow')
        self.radio = radio
        self.flow = self.module.MgroupConfigFlow()
        self.flow._validate = AsyncMock(return_value=None)
        self.address = 'D4:10:F2:1C:F0:8E'

    async def test_no_devices_falls_back_to_address_form(self):
        result = await self.flow.async_step_user()
        self.assertEqual(result['step_id'], 'manual')
        self.flow._validate.assert_not_awaited()

    async def test_selection_excludes_configured_and_other_models(self):
        self.flow.configured = [types.SimpleNamespace(unique_id='AA:BB:CC:DD:EE:FF')]
        self.radio.async_discovered_service_info = lambda *a, **kw: [
            types.SimpleNamespace(name='MG-P1SR-12P', address=self.address),
            types.SimpleNamespace(name='MG-P1SR-12P', address='AA:BB:CC:DD:EE:FF'),
            types.SimpleNamespace(name='Other', address='00:00:00:00:00:00'),
        ]
        result = await self.flow.async_step_user()
        schema = result['data_schema']
        self.assertEqual(schema({'device': self.address}), {'device': self.address})
        with self.assertRaises(voluptuous.Invalid):
            schema({'device': 'AA:BB:CC:DD:EE:FF'})
        result = await self.flow.async_step_user({'device': self.address})
        self.assertEqual(result['step_id'], 'channels')
        self.flow._validate.assert_awaited_once_with(self.address)

    async def test_invalid_address_and_connection_error_remain_editable(self):
        result = await self.flow.async_step_manual({'address': 'invalid'})
        self.assertEqual(result['errors'], {'address': 'invalid_address'})
        self.flow._validate.assert_not_awaited()
        self.flow._validate.return_value = 'cannot_connect'
        result = await self.flow.async_step_manual({'address': self.address.lower()})
        self.assertEqual(result['step_id'], 'manual')
        self.assertEqual(result['errors'], {'base': 'cannot_connect'})

    async def test_duplicate_is_rejected_before_connection(self):
        self.flow.configured = [types.SimpleNamespace(unique_id=self.address)]
        with self.assertRaisesRegex(RuntimeError, 'already_configured'):
            await self.flow.async_step_manual({'address': self.address})
        self.flow._validate.assert_not_awaited()

    async def test_bluetooth_confirmation_then_names_creates_entry(self):
        result = await self.flow.async_step_bluetooth(types.SimpleNamespace(address=self.address))
        self.assertEqual(result['step_id'], 'bluetooth_confirm')
        self.flow._validate.assert_not_awaited()
        result = await self.flow.async_step_bluetooth_confirm({})
        self.assertEqual(result['step_id'], 'channels')
        labels = {f'channel_{i}': f' Licht {i} ' for i in range(1, 13)}
        labels['channel_5'] = ' '
        result = await self.flow.async_step_channels(labels)
        self.assertEqual(result['data'], {'address': self.address})
        self.assertEqual(result['options']['channel_names'][0], 'Licht 1')
        self.assertEqual(result['options']['channel_names'][4], 'Kanal 5')
