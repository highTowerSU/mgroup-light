"""Panel packets, reconstructed from the app and checked against real frames."""
from dataclasses import dataclass


class PanelError(Exception):
    """The requested panel operation could not be confirmed."""


@dataclass(frozen=True)
class PanelState:
    master_on: bool
    channels: tuple[int, ...]
    brightness: int | None = None
    lighting: "LightingState | None" = None


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


@dataclass(frozen=True)
class LightingState:
    """Reported F1 header and the RGB palette from F2/F3/F4."""

    header: bytes
    colors: tuple[tuple[int, int, int], ...]

    @property
    def is_on(self) -> bool:
        return self.brightness > 0

    @property
    def brightness(self) -> int:
        return self.header[6]


def parse_lighting(frames: dict[int, bytes]) -> LightingState | None:
    if any(code not in frames for code in (0xF1, 0xF2, 0xF3, 0xF4)):
        return None
    if len(frames[0xF1]) != 11 or any(frames[code][0] != code for code in frames):
        return None
    header = frames[0xF1][1:]
    count = header[8]
    if not 1 <= count <= 14:
        return None
    if any(len(frames[code]) != size for code, size in ((0xF2, 19), (0xF3, 19), (0xF4, 7))):
        return None
    rgb = b''.join(frames[code][1:] for code in (0xF2, 0xF3, 0xF4))[:count * 3]
    return LightingState(header, tuple(tuple(rgb[i:i+3]) for i in range(0, len(rgb), 3)))


def lighting_commands(
    state: LightingState, *, rgb: tuple[int, int, int] | None = None,
    brightness: int | None = None, turn_on: bool | None = None,
) -> tuple[tuple[int, bytes], ...]:
    """Stage RGB on eff2 and commit on eff1, as the original app does."""
    header = bytearray(state.header)
    if len(header) != 10:
        raise PanelError('Keine vollständige Beleuchtungskonfiguration vorhanden')
    commands = []
    if brightness is not None:
        if not isinstance(brightness, int) or not 0 <= brightness <= 255:
            raise ValueError('brightness must be an integer between 0 and 255')
        header[6] = brightness
    # Preserve the reported device power flag; only change illumination level.
    # Do not risk changing relay/master power through an RGB operation.
    if turn_on is False:
        header[6] = 0
    elif turn_on is True and header[6] == 0:
        header[6] = 255
    if rgb is not None:
        if len(rgb) != 3 or any(not isinstance(c, int) or not 0 <= c <= 255 for c in rgb):
            raise ValueError('rgb must contain three integers between 0 and 255')
        # A single static color uses type 0 and speed 700 in WriteConfig.
        header[3:6] = bytes((0, 0xBC, 0x02))
        header[8] = 1
        commands.append((2, bytes(rgb) + bytes(15)))
    header[9] = 1  # Save the configuration, matching the app.
    commands.append((1, bytes(header)))
    return tuple(commands)


def mode_command(state: PanelState, channel: int, mode: int) -> bytes | None:
    if not 1 <= channel <= 12 or mode not in range(4):
        raise ValueError('invalid channel or mode')
    if len(state.channels) != 12 or state.channels[channel - 1] > 7:
        raise PanelError('Kein konfigurierbarer Kanalzustand vorhanden')
    if not state.master_on:
        raise PanelError('Der Gesamtschalter am Panel ist ausgeschaltet')
    if state.channels[channel - 1] >> 1 == mode:
        return None
    # Changing modes on a live circuit could pulse or flash a connected load.
    if state.channels[channel - 1] & 1:
        raise PanelError('Den Kanal vor dem Ändern der Betriebsart ausschalten')
    channels = list(state.channels)
    channels[channel - 1] = mode << 1
    return bytes.fromhex('f5' + ''.join(format(c, 'x') for c in channels))
