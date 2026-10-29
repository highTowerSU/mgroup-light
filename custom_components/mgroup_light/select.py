"""Reported output modes, editable while the selected circuit is off."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CHANNEL_NAMES, DEFAULT_NAMES, DOMAIN, MODEL, MODE_OPTIONS


async def async_setup_entry(hass, entry, async_add_entities):
    names = entry.options.get(CONF_CHANNEL_NAMES, DEFAULT_NAMES)
    async_add_entities([MgroupModeSelect(entry.runtime_data, i + 1, names[i]) for i in range(12)])


class MgroupModeSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "channel_mode"
    _attr_options = list(MODE_OPTIONS)

    def __init__(self, coordinator, channel, name):
        super().__init__(coordinator)
        self.channel = channel
        self._attr_name = f"{name} Betriebsart"
        self._attr_unique_id = f"{coordinator.address}_mode_{channel}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def current_option(self):
        value = self.coordinator.data.channels[self.channel - 1]
        return MODE_OPTIONS[value >> 1] if value <= 7 else None

    async def async_select_option(self, option):
        await self.coordinator.async_set_mode(self.channel, MODE_OPTIONS.index(option))
