"""Serialize Bluetooth operations and wait for real panel feedback."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .const import CONTROL_UUID
from .protocol import (PanelError, PanelState, LightingState, channels_command,
                       parse_status, parse_lighting, lighting_commands, mode_command)

_LOGGER = logging.getLogger(__name__)


class Panel:
    def __init__(
        self,
        connect: Callable[[Callable], Awaitable[Any]],
        on_state: Callable[[PanelState | None], None],
        timeout: float = 12,
    ) -> None:
        self._connect = connect
        self._on_state = on_state
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._client: Any = None
        self._waiter: asyncio.Future[PanelState] | None = None
        self._lighting_waiter: asyncio.Future[LightingState] | None = None
        self._lighting_frames: dict[int, bytes] = {}
        self._closing = False
        self.state: PanelState | None = None

    def _disconnected(self, client: Any) -> None:
        if self._client is not client:
            return
        self._client = None
        if self._lighting_waiter is not None and not self._lighting_waiter.done():
            self._lighting_waiter.set_exception(PanelError("Bluetooth-Verbindung unterbrochen"))
        if self._waiter is not None and not self._waiter.done():
            self._waiter.set_exception(PanelError("Bluetooth-Verbindung unterbrochen"))
        if not self._closing:
            self._on_state(None)

    def _notify(self, sender: Any, data: bytearray) -> None:
        if self._closing:
            return
        packet = bytes(data)
        if packet and packet[0] in (0xF1, 0xF2, 0xF3, 0xF4):
            if self._lighting_waiter is None:
                return  # Only combine replies from a current requested snapshot.
            self._lighting_frames[packet[0]] = packet
            lighting = parse_lighting(self._lighting_frames)
            if lighting is not None and not self._lighting_waiter.done():
                self._lighting_waiter.set_result(lighting)
            return
        state = parse_status(packet)
        if state is None:
            return
        if self.state is not None:
            state = replace(state, lighting=self.state.lighting)
        self.state = state
        if self._waiter is not None and not self._waiter.done():
            self._waiter.set_result(state)
        self._on_state(state)

    async def _query_lighting_locked(self) -> LightingState:
        await self._ensure_connected()
        waiter = asyncio.get_running_loop().create_future()
        self._lighting_waiter = waiter
        self._lighting_frames = {}
        try:
            for code in (0xF1, 0xF2, 0xF3, 0xF4):
                await self._client.write_gatt_char(CONTROL_UUID, bytes((code, 0)), response=False)
                await asyncio.sleep(0.1)
            return await asyncio.wait_for(waiter, timeout=self._timeout)
        except TimeoutError as exc:
            raise PanelError("Keine vollständige RGB-Rückmeldung vom Panel") from exc
        finally:
            self._lighting_waiter = None
            self._lighting_frames = {}
            if not waiter.done():
                waiter.cancel()
            elif not waiter.cancelled():
                waiter.exception()

    async def _ensure_connected(self) -> None:
        if self._closing:
            raise PanelError("Die Integration wurde beendet")
        if self._client is not None and self._client.is_connected:
            return
        # A new BlueZ discovery on this panel can initially be incomplete.
        for attempt in range(2):
            client = await self._connect(self._disconnected)
            self._client = client
            char = client.services.get_characteristic(CONTROL_UUID)
            if char is not None and {"notify", "write-without-response"} <= set(char.properties):
                try:
                    await client.start_notify(char, self._notify)
                    return
                except BaseException:
                    self._client = None
                    await client.disconnect()
                    raise
            self._client = None
            await client.disconnect()
            if attempt == 0:
                await asyncio.sleep(0.5)
        raise PanelError("Der erwartete Panel-Dienst wurde nicht vollständig erkannt")

    async def _query_locked(self) -> PanelState:
        await self._ensure_connected()
        waiter = asyncio.get_running_loop().create_future()
        self._waiter = waiter
        try:
            await self._client.write_gatt_char(CONTROL_UUID, b"\xf8\x00", response=False)
            return await asyncio.wait_for(waiter, timeout=self._timeout)
        except TimeoutError as exc:
            raise PanelError("Keine Statusantwort vom Panel") from exc
        finally:
            self._waiter = None
            if not waiter.done():
                waiter.cancel()
            elif not waiter.cancelled():
                waiter.exception()

    async def query(self, *, include_lighting: bool = False) -> PanelState:
        async with self._lock:
            try:
                state = await self._query_locked()
                if not include_lighting:
                    return state
                try:
                    lighting = await self._query_lighting_locked()
                except Exception as exc:
                    if self._client is None or not self._client.is_connected:
                        raise
                    _LOGGER.debug("RGB-Abfrage fehlgeschlagen: %s", exc)
                    lighting = None
                self.state = replace(self.state or state, lighting=lighting)
                self._on_state(self.state)
                return self.state
            except Exception:
                await self._drop_connection()
                raise

    async def set_channel(self, channel: int, turn_on: bool) -> PanelState:
        return await self.set_channels((channel,), turn_on)

    async def set_channels(self, channels: tuple[int, ...], turn_on: bool) -> PanelState:
        async with self._lock:
            try:
                before = await self._query_locked()
                command = channels_command(before, channels, turn_on)
                if command is None:
                    return before
                # Never replay a failed state write automatically: pulse modes
                # must not be triggered twice. A fresh read follows the write.
                await self._client.write_gatt_char(CONTROL_UUID, command, response=False)
                await asyncio.sleep(0.15)
                after = await self._query_locked()
                # Momentary modes may already have returned to off. Only check
                # sustained modes whose semantics are known from the app.
                for channel in channels:
                    if before.channels[channel - 1] // 2 in (0, 2):
                        if bool(after.channels[channel - 1] & 1) != turn_on:
                            raise PanelError("Das Panel hat den gewünschten Zustand nicht bestätigt")
                return after
            except Exception:
                await self._drop_connection()
                raise

    async def set_mode(self, channel: int, mode: int) -> PanelState:
        async with self._lock:
            try:
                before = await self._query_locked()
                command = mode_command(before, channel, mode)
                if command is None:
                    return before
                await self._client.write_gatt_char(CONTROL_UUID, command, response=False)
                await asyncio.sleep(0.15)
                after = await self._query_locked()
                if after.channels[channel - 1] != mode << 1:
                    raise PanelError("Das Panel hat die Betriebsart nicht bestätigt")
                return after
            except Exception:
                await self._drop_connection()
                raise

    async def set_lighting(self, **changes) -> PanelState:
        async with self._lock:
            try:
                await self._query_locked()
                before = await self._query_lighting_locked()
                commands = lighting_commands(before, **changes)
                for suffix, data in commands:
                    uuid = f"0003cbbb-0000-1000-8000-00805f9beff{suffix}"
                    char = self._client.services.get_characteristic(uuid)
                    if char is None or "write-without-response" not in char.properties:
                        raise PanelError("Der RGB-Schreibdienst fehlt")
                for suffix, data in commands:
                    uuid = f"0003cbbb-0000-1000-8000-00805f9beff{suffix}"
                    await self._client.write_gatt_char(uuid, data, response=False)
                    await asyncio.sleep(0.1)
                after = await self._query_lighting_locked()
                if ("rgb" in changes and after.colors != (tuple(changes["rgb"]),)) or (
                    "brightness" in changes and after.brightness != changes["brightness"]
                ) or ("turn_on" in changes and after.is_on != changes["turn_on"]):
                    raise PanelError("Das Panel hat die RGB-Einstellung nicht bestätigt")
                self.state = replace(self.state, lighting=after)
                self._on_state(self.state)
                return self.state
            except Exception:
                await self._drop_connection()
                raise

    async def _drop_connection(self) -> None:
        client, self._client = self._client, None
        if not self._closing:
            self._on_state(None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def close(self) -> None:
        self._closing = True
        async with self._lock:
            await self._drop_connection()
