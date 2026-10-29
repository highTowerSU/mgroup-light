"""Twelve channels and an atomic hazard switch, using confirmed panel states."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MgroupConfigEntry
from .const import CONF_CHANNEL_NAMES, DEFAULT_NAMES, DOMAIN, MODEL
from .coordinator import MgroupCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: MgroupConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    names = entry.options.get(CONF_CHANNEL_NAMES, DEFAULT_NAMES)
    async_add_entities([
        MgroupSwitch(entry.runtime_data, index + 1, names[index])
        for index in range(12)
    ] + [MgroupHazardSwitch(entry.runtime_data)])


class MgroupBaseSwitch(CoordinatorEntity[MgroupCoordinator], SwitchEntity):
    _attr_has_entity_name = False
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator: MgroupCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name="Mgroup Panel", model=MODEL,
        )


class MgroupSwitch(MgroupBaseSwitch):
    def __init__(self, coordinator: MgroupCoordinator, channel: int, name: str) -> None:
        super().__init__(coordinator, f"channel_{channel}", name)
        self.channel = channel

    @property
    def is_on(self) -> bool:
        state = self.coordinator.data
        return state.master_on and bool(state.channels[self.channel - 1] & 1)

    @property
    def extra_state_attributes(self):
        state = self.coordinator.data
        return {
            "channel": self.channel,
            "panel_mode": state.channels[self.channel - 1] >> 1,
            "panel_master_on": state.master_on,
            "shutdown_protected": self.channel == getattr(self.coordinator, "power_channel", 0),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_channel(self.channel, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_channel(self.channel, False)


class MgroupHazardSwitch(MgroupBaseSwitch):
    """Set both blinkers with one shared F5 write and preserve their modes."""

    _attr_icon = "mdi:hazard-lights"

    def __init__(self, coordinator: MgroupCoordinator) -> None:
        super().__init__(coordinator, "warnblinker", "Warnblinker")

    @property
    def is_on(self) -> bool:
        state = self.coordinator.data
        return state.master_on and all(state.channels[i] & 1 for i in (6, 7))

    @property
    def extra_state_attributes(self):
        state = self.coordinator.data
        return {
            "channels": [7, 8],
            "left_on": state.master_on and bool(state.channels[6] & 1),
            "right_on": state.master_on and bool(state.channels[7] & 1),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_channels((7, 8), True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_channels((7, 8), False)
