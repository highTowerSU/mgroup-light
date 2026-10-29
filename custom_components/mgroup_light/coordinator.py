"""Use HA's shared Bluetooth infrastructure, plus notifications and polling."""
from __future__ import annotations

from datetime import timedelta
import logging

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (MODEL, DOMAIN, CONF_POWER_CHANNEL, CONF_SHUTDOWN_CHANNEL,
                    EVENT_SHUTDOWN_REQUESTED)
from .panel import Panel
from .protocol import PanelError, PanelState

_LOGGER = logging.getLogger(__name__)


async def async_panel_service_info(hass: HomeAssistant, address: str, *, refresh=False):
    """Request an active window for this address when passive discovery misses it."""
    if not refresh and (info := bluetooth.async_last_service_info(hass, address, connectable=True)):
        return info
    try:
        return await bluetooth.async_process_advertisements(
            hass, lambda info: info.address.upper() == address.upper(),
            {"address": address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE, 25,
        )
    except TimeoutError as exc:
        raise PanelError("Das Panel wurde auch bei aktiver Suche nicht gefunden") from exc


def create_panel(hass: HomeAssistant, address: str, on_state) -> Panel:
    async def connect(disconnected_callback):
        device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
        if device is None:
            info = await async_panel_service_info(hass, address, refresh=True)
            device = bluetooth.async_ble_device_from_address(hass, address, connectable=True) or info.device
        return await establish_connection(
            BleakClient, device, MODEL,
            disconnected_callback=disconnected_callback,
            max_attempts=2, use_services_cache=False,
        )

    return Panel(connect, on_state)


class MgroupCoordinator(DataUpdateCoordinator[PanelState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=entry.title, config_entry=entry,
            update_interval=timedelta(seconds=30),
        )
        self.address = entry.data["address"]
        self.power_channel = entry.options.get(CONF_POWER_CHANNEL, 0)
        self.shutdown_channel = entry.options.get(CONF_SHUTDOWN_CHANNEL, 0)
        self._last_channels: tuple[int, ...] | None = None
        self._event_hass = hass
        self._closed = False
        self.panel = create_panel(hass, self.address, self._on_state)

    @callback
    def _on_state(self, state: PanelState | None) -> None:
        if self._closed:
            return
        if state is None:
            self._last_channels = None
            self.async_set_update_error(UpdateFailed("Bluetooth-Verbindung unterbrochen"))
        else:
            previous, self._last_channels = self._last_channels, state.channels
            channel = self.shutdown_channel
            if channel and previous is not None and not previous[channel - 1] & 1 and state.channels[channel - 1] & 1:
                self.request_shutdown("channel", channel)
            self.async_set_updated_data(state)

    async def _async_update_data(self) -> PanelState:
        try:
            return await self.panel.query(include_lighting=True)
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc

    async def async_set_channel(self, channel: int, turn_on: bool) -> None:
        await self.async_set_channels((channel,), turn_on)

    async def async_set_channels(self, channels: tuple[int, ...], turn_on: bool) -> None:
        if not turn_on and self.power_channel and self.power_channel in channels:
            self.request_shutdown("software", self.power_channel)
            return
        try:
            state = await self.panel.set_channels(channels, turn_on)
        except Exception as exc:
            raise HomeAssistantError(str(exc)) from exc
        self.async_set_updated_data(state)

    async def async_close(self) -> None:
        self._closed = True
        await self.panel.close()

    @callback
    def request_shutdown(self, source: str, channel: int | None = None) -> None:
        """Request an automation; never cut power or shut the host down here."""
        self._event_hass.bus.async_fire(EVENT_SHUTDOWN_REQUESTED, {
            "address": self.address, "source": source, "channel": channel,
        })

    async def async_set_mode(self, channel: int, mode: int) -> None:
        if channel == self.power_channel:
            raise HomeAssistantError("Die Betriebsart des HA-Versorgungskanals ist geschützt")
        try:
            state = await self.panel.set_mode(channel, mode)
        except Exception as exc:
            raise HomeAssistantError(str(exc)) from exc
        self.async_set_updated_data(state)

    async def async_set_lighting(self, **changes) -> None:
        try:
            state = await self.panel.set_lighting(**changes)
        except Exception as exc:
            raise HomeAssistantError(str(exc)) from exc
        self.async_set_updated_data(state)
