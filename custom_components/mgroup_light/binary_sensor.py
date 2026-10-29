"""Optional StromPi 2 signal monitoring on the local Raspberry Pi."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_STROMPI2
from .gpio import read_strompi2_signal

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    if not entry.options.get(CONF_STROMPI2, False):
        return
    coordinator = StromPiCoordinator(hass, entry)
    await coordinator.async_refresh()
    async_add_entities([StromPiSignal(coordinator, entry.runtime_data.address)])


class StromPiCoordinator(DataUpdateCoordinator[bool]):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name="StromPi 2 GPIO 21", config_entry=entry,
                         update_interval=timedelta(seconds=2))

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(read_strompi2_signal)
        except (OSError, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc


class StromPiSignal(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = False
    _attr_name = "USV-Signal (StromPi 2)"
    _attr_icon = "mdi:power-plug-battery"

    def __init__(self, coordinator, address):
        super().__init__(coordinator)
        self._attr_unique_id = f"{address}_strompi2_gpio21"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{address}_strompi2")},
            "name": "StromPi 2", "manufacturer": "Joy-IT", "model": "StromPi 2",
        }
        self._attr_extra_state_attributes = {
            "gpio": 21, "gpio_numbering": "BCM",
            "signal": "High bedeutet fehlende Micro-USB-Primärversorgung, sofern T-PIN mit BCM21 verbunden ist",
            "read_only": True,
        }

    @property
    def is_on(self):
        return self.coordinator.data
