"""Serialize Bluetooth operations and wait for real panel feedback."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .const import CONTROL_UUID
from .protocol import PanelError, PanelState, channels_command, parse_status


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
        self._closing = False
        self.state: PanelState | None = None

    def _disconnected(self, client: Any) -> None:
        if self._client is not client:
            return
        self._client = None
        if self._waiter is not None and not self._waiter.done():
            self._waiter.set_exception(PanelError("Bluetooth-Verbindung unterbrochen"))
        if not self._closing:
            self._on_state(None)

    def _notify(self, sender: Any, data: bytearray) -> None:
        state = parse_status(bytes(data))
        if state is None or self._closing:
            return
        self.state = state
        if self._waiter is not None and not self._waiter.done():
            self._waiter.set_result(state)
        self._on_state(state)

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

    async def query(self) -> PanelState:
        async with self._lock:
            try:
                return await self._query_locked()
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
