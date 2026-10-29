"""Panel packets, reconstructed from the app and checked against real frames."""
from dataclasses import dataclass


class PanelError(Exception):
    """The requested panel operation could not be confirmed."""


@dataclass(frozen=True)
class PanelState:
    master_on: bool
    channels: tuple[int, ...]
    brightness: int | None = None


def parse_status(data: bytes) -> PanelState | None:
    """Ignore color/firmware/short packets; unpack the twelve channel nibbles."""
    if len(data) < 7 or data[0] not in (0xF8, 0xF9):
        return None
    channels = tuple(int(c, 16) for c in data[1:7].hex())
    if any(c > 8 for c in channels):
        return None
    return PanelState(data[0] == 0xF9, channels, data[7] if len(data) > 7 else None)


def channel_command(state: PanelState, channel: int, turn_on: bool) -> bytes | None:
    """Use an absolute state, preserving every mode and every other channel."""
    return channels_command(state, (channel,), turn_on)


def channels_command(
    state: PanelState, selected: tuple[int, ...], turn_on: bool,
) -> bytes | None:
    """Change selected state bits together in a single panel telegram."""
    selected = tuple(dict.fromkeys(selected))
    if not selected or any(not 1 <= channel <= 12 for channel in selected):
        raise ValueError("select at least one channel between 1 and 12")
    if len(state.channels) != 12:
        raise PanelError("Kein vollständiger Kanalzustand vorhanden")
    if not state.master_on:
        raise PanelError("Der Gesamtschalter am Panel ist ausgeschaltet")
    if any(state.channels[channel - 1] > 7 for channel in selected):
        raise PanelError("Dieser Kanal ist am Panel deaktiviert")
    channels = list(state.channels)
    for channel in selected:
        channels[channel - 1] = (channels[channel - 1] & ~1) | int(turn_on)
    if tuple(channels) == state.channels:
        return None
    return bytes.fromhex("f5" + "".join(format(c, "x") for c in channels))
