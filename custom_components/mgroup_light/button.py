"""A shutdown request for user-defined automations, without cutting power."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MgroupShutdownButton(entry.runtime_data)])


class MgroupShutdownButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = False
    _attr_name = "Herunterfahren anfordern"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_shutdown_request"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    async def async_press(self):
        self.coordinator.request_shutdown("button")
