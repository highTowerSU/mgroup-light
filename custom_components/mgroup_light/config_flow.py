"""UI setup and channel labels."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components import bluetooth
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_CHANNEL_NAMES, DEFAULT_NAMES, DOMAIN, MODEL, CONF_POWER_CHANNEL, CONF_SHUTDOWN_CHANNEL, CONF_STROMPI2
from .coordinator import async_panel_service_info, create_panel


class MgroupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _address: str | None = None

    async def _validate(self, address: str) -> str | None:
        try:
            info = await async_panel_service_info(self.hass, address)
        except Exception:
            return "cannot_connect"
        if info.name != MODEL:
            return "unsupported_device"
        panel = create_panel(self.hass, address, lambda state: None)
        try:
            await panel.query()
        except Exception:
            return "cannot_connect"
        finally:
            await panel.close()
        return None

    async def async_step_user(self, user_input=None):
        configured = {entry.unique_id for entry in self._async_current_entries()}
        devices = {
            info.address.upper(): f"{info.name} ({info.address})"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
            if info.name == MODEL and info.address.upper() not in configured
        }
        if user_input is not None:
            if user_input["device"] == "manual":
                return await self.async_step_manual()
            return await self.async_step_manual({"address": user_input["device"]})
        if not devices:
            return await self.async_step_manual()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device"): vol.In({**devices, "manual": "Andere Bluetooth-Adresse / Other Bluetooth address"})}),
        )

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input["address"].strip().upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                errors["address"] = "invalid_address"
            else:
                # A manual retry can supersede an abandoned or discovered
                # wizard; configured entries are still checked below.
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                if error := await self._validate(address):
                    errors["base"] = error
                else:
                    self._address = address
                    return await self.async_step_channels()
        return self.async_show_form(
            step_id="manual", data_schema=vol.Schema({vol.Required("address"): str}), errors=errors,
        )

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak):
        self._address = discovery_info.address.upper()
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            if error := await self._validate(self._address):
                errors["base"] = error
            else:
                return await self.async_step_channels()
        return self.async_show_form(step_id="bluetooth_confirm", errors=errors)

    async def async_step_channels(self, user_input=None):
        if user_input is not None:
            names = [user_input[f"channel_{i}"].strip() or DEFAULT_NAMES[i - 1] for i in range(1, 13)]
            return self.async_create_entry(
                title=MODEL, data={"address": self._address},
                options={CONF_CHANNEL_NAMES: names},
            )
        return self.async_show_form(
            step_id="channels",
            data_schema=vol.Schema({
                vol.Required(f"channel_{i}", default=DEFAULT_NAMES[i - 1]): str
                for i in range(1, 13)
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MgroupOptionsFlow()


class MgroupOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            power = user_input.get(CONF_POWER_CHANNEL, 0)
            shutdown = user_input.get(CONF_SHUTDOWN_CHANNEL, 0)
            if power and power == shutdown:
                errors["base"] = "same_power_and_shutdown_channel"
            else:
                names = [user_input[f"channel_{i}"].strip() or DEFAULT_NAMES[i - 1] for i in range(1, 13)]
                return self.async_create_entry(title="", data={
                    **self.config_entry.options, CONF_CHANNEL_NAMES: names,
                    CONF_POWER_CHANNEL: power, CONF_SHUTDOWN_CHANNEL: shutdown,
                    CONF_STROMPI2: user_input.get(CONF_STROMPI2, False),
                })
        names = self.config_entry.options.get(CONF_CHANNEL_NAMES, DEFAULT_NAMES)
        fields = {
            vol.Required(f"channel_{i}", default=names[i - 1]): str
            for i in range(1, 13)
        }
        for key in (CONF_POWER_CHANNEL, CONF_SHUTDOWN_CHANNEL):
            fields[vol.Required(key, default=self.config_entry.options.get(key, 0))] = vol.In(list(range(13)))
        fields[vol.Required(CONF_STROMPI2, default=self.config_entry.options.get(CONF_STROMPI2, False))] = bool
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields), errors=errors)
