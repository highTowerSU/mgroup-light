"""Read and set the panel's shared RGB illumination, not its relay outputs."""
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MgroupPanelLight(entry.runtime_data)])


class MgroupPanelLight(CoordinatorEntity, LightEntity):
    _attr_has_entity_name = False
    _attr_name = "Tastenbeleuchtung"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_rgb"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def available(self):
        return super().available and self.coordinator.data.lighting is not None

    @property
    def is_on(self):
        lighting = self.coordinator.data.lighting
        return lighting.is_on if lighting else None

    @property
    def brightness(self):
        lighting = self.coordinator.data.lighting
        return lighting.brightness if lighting else None

    @property
    def rgb_color(self):
        lighting = self.coordinator.data.lighting
        # A changing palette has no single measured current RGB color.
        return lighting.colors[0] if lighting and len(lighting.colors) == 1 else None

    @property
    def extra_state_attributes(self):
        lighting = self.coordinator.data.lighting
        return {
            "palette": [list(color) for color in lighting.colors] if lighting else None,
            "palette_mode": lighting.header[3] if lighting else None,
            "strobe": lighting.header[7] if lighting else None,
        }

    async def async_turn_on(self, **kwargs):
        changes = {"turn_on": True}
        if ATTR_RGB_COLOR in kwargs:
            changes["rgb"] = tuple(kwargs[ATTR_RGB_COLOR])
        if ATTR_BRIGHTNESS in kwargs:
            changes["brightness"] = kwargs[ATTR_BRIGHTNESS]
        await self.coordinator.async_set_lighting(**changes)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_lighting(turn_on=False)
