"""Read-only protocol diagnostics without credentials or automation contents."""
from .const import MODEL


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    state = coordinator.data
    lighting = state.lighting if state else None
    return {
        "model": MODEL,
        "master_on": state.master_on if state else None,
        "channels": list(state.channels) if state else None,
        "panel_brightness": state.brightness if state else None,
        "lighting_header": lighting.header.hex() if lighting else None,
        "palette": [list(color) for color in lighting.colors] if lighting else None,
        "protected_power_channel": coordinator.power_channel,
        "shutdown_request_channel": coordinator.shutdown_channel,
    }
