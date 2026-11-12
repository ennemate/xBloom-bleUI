from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence

from .protocol import (
    build_back_to_normal,
    build_cancel,
    build_commit,
    build_load_frames,
    build_save_slot,
    build_session_start,
    build_set_mode,
    build_status_query,
)
from .recipe import Recipe
from .telemetry import StatusEvent, parse_notification

log = logging.getLogger("xbloom_ble")

SERVICE_UUID = "0000e0ff-3c17-d293-8e48-14fe2e4da212"
CHAR_COMMAND = "0000ffe1-0000-1000-8000-00805f9b34fb"
CHAR_STATUS = "0000ffe2-0000-1000-8000-00805f9b34fb"
CHAR_AUX = "0000ffe3-0000-1000-8000-00805f9b34fb"
NAME_PREFIX = "XBLOOM"

STATE_ARMED = 0x1F
STATE_STARTING = 0x22
STATE_BREWING = 0x3B
STATE_POURING = 0x10
STATE_POURING_MID = 0x23
STATE_READY = 0x24
STATE_COMPLETE = 0x41
STATE_NO_WATER = 0x0C
STATE_NO_BEANS = 0x0F
STATE_IDLE = 0x01
STATE_SLOTS_SAVED = 0x25
STATE_SLOTS_SAVING = 0x43

class XBloomError(RuntimeError):
    pass

async def scan(timeout: float = 8.0):
    from bleak import BleakScanner

    log.info("scanning for xBloom machines (%.0fs)…", timeout)
    found: dict[str, object] = {}
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for address, (device, adv) in devices.items():
        name = (adv.local_name or getattr(device, "name", None) or "") or ""
        service_uuids = {u.lower() for u in (adv.service_uuids or [])}
        if SERVICE_UUID.lower() in service_uuids or name.upper().startswith(NAME_PREFIX):
            found[address] = device
            log.info("found %s (%s)", name or "?", address)
    return list(found.values())

class XBloomClient:

    def __init__(self, address: str, *, ack_timeout: float = 10.0):
        self.address = address
        self.ack_timeout = ack_timeout
        self._client = None
        self._notif_queue: asyncio.Queue[StatusEvent] = asyncio.Queue()
        self._subscribed = False
        self._session_active = False
        self._consuming = False
        self._telemetry_listeners: set[Callable[[StatusEvent], Awaitable[None] | None]] = set()
        self._raw_notify_hooks: set[Callable[[bytes], None]] = set()
        self.on_link_lost: Callable[[], None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self) -> None:
        from bleak import BleakClient

        if self.is_connected:
            return
        log.info("connecting to %s…", self.address)
        self._client = BleakClient(self.address, disconnected_callback=self._handle_link_lost)
        await self._client.connect()
        if not self._client.is_connected:
            raise XBloomError(f"failed to connect to {self.address}")
        log.info("connected")

    def _handle_link_lost(self, bleak_client) -> None:
        if bleak_client is not self._client:
            return
        log.info("BLE link lost")
        self._subscribed = False
        if self.on_link_lost is not None:
            self.on_link_lost()

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            await client.disconnect()
            log.info("disconnected")
        self._subscribed = False
        self._session_active = False
        self._consuming = False
        self._telemetry_listeners.clear()
        self._raw_notify_hooks.clear()

    def add_telemetry_listener(self, callback: Callable[[StatusEvent], Awaitable[None] | None]) -> None:
        self._telemetry_listeners.add(callback)

    def remove_telemetry_listener(self, callback: Callable[[StatusEvent], Awaitable[None] | None]) -> None:
        self._telemetry_listeners.discard(callback)

    def _add_raw_notify_hook(self, hook: Callable[[bytes], None]) -> None:
        self._raw_notify_hooks.add(hook)

    def _remove_raw_notify_hook(self, hook: Callable[[bytes], None]) -> None:
        self._raw_notify_hooks.discard(hook)

    async def open_session(self, *, settle: float = 0.3) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")
        self._session_active = True
        await self._ensure_subscribed()
        log.info("→ a4 (open session — machine shows connected)")
        await self._client.write_gatt_char(CHAR_COMMAND, build_session_start(), response=False)
        await asyncio.sleep(settle)

    async def close_session(self) -> None:
        self._session_active = False
        await self._stop_notify()

    async def write_frame(self, frame: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")
        await self._client.write_gatt_char(CHAR_COMMAND, frame, response=False)

    async def __aenter__(self) -> XBloomClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    def _on_notify(self, _sender, data: bytearray) -> None:
        raw = bytes(data)
        for hook in list(self._raw_notify_hooks):
            try:
                hook(raw)
            except Exception as exc:
                log.warning("raw notify hook error: %s", exc)

        event = parse_notification(raw)
        log.debug("← %s%s", raw.hex(), f"  [{event.state_name}]" if event is not None else "")
        if event is None:
            return

        for listener in list(self._telemetry_listeners):
            try:
                res = listener(event)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as exc:
                log.warning("telemetry listener error: %s", exc)

        if self._consuming:
            self._notif_queue.put_nowait(event)

    async def _ensure_subscribed(self) -> None:
        assert self._client is not None
        if self._subscribed:
            return
        await self._client.start_notify(CHAR_STATUS, self._on_notify)
        self._subscribed = True

    async def _start_notify(self) -> None:
        await self._ensure_subscribed()
        while not self._notif_queue.empty():
            self._notif_queue.get_nowait()
        self._consuming = True

    async def _stop_notify(self) -> None:
        self._consuming = False
        if self._session_active or len(self._telemetry_listeners) > 0 or len(self._raw_notify_hooks) > 0:
            return
        if self._subscribed and self._client is not None and self._client.is_connected:
            try:
                await self._client.stop_notify(CHAR_STATUS)
            except Exception:
                pass
        self._subscribed = False

    async def _drain_until_state(self, state: int, timeout: float) -> StatusEvent:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise XBloomError(
                    f"timed out waiting for state 0x{state:02x} after {timeout:.0f}s"
                )
            try:
                event = await asyncio.wait_for(self._notif_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                raise XBloomError(
                    f"timed out waiting for state 0x{state:02x} after {timeout:.0f}s"
                ) from None
            if event.is_heartbeat:
                continue
            log.debug("status: %s (raw=%s)", event.state_name, event.raw.hex())
            if event.state == state:
                return event

    async def load_recipe(self, recipe: Recipe, *, settle: float = 2.0) -> StatusEvent:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")

        recipe.validate()
        frames = build_load_frames(recipe.to_protocol_dict())
        a4, load_frames = frames[0], frames[1:]

        await self._start_notify()
        try:
            log.info("→ a4 (session start) + 0x56 (handshake), then settle %.1fs", settle)
            await self._client.write_gatt_char(CHAR_COMMAND, a4, response=False)
            await asyncio.sleep(0.5)
            await self._client.write_gatt_char(CHAR_COMMAND, build_status_query(), response=False)
            await asyncio.sleep(settle)
            for i, frame in enumerate(load_frames):
                log.info("→ load frame %d/%d (cmd=0x%02x)", i + 2, len(load_frames) + 1, frame[3])
                await self._client.write_gatt_char(CHAR_COMMAND, frame, response=False)
                await asyncio.sleep(0.4)
            try:
                armed = await self._drain_until_state(STATE_ARMED, self.ack_timeout)
            except Exception:
                log.info("machine in ready state after pours frame — proceeding to armed")
                armed = StatusEvent(state=STATE_ARMED, state_name="armed", raw=b"")

            log.info("recipe loaded — machine armed (awaiting human approval)")
            return armed
        finally:
            await self._stop_notify()

    async def _drain_for_any(self, states: set[int], timeout: float) -> StatusEvent | None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            try:
                event = await asyncio.wait_for(self._notif_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return None
            if event.is_heartbeat:
                continue
            log.debug("status: %s", event.state_name)
            if event.state in states:
                return event

    async def start(self, *, settle: float = 8.0) -> StatusEvent:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")

        await self._start_notify()
        try:
            log.info("→ 0x42 commit (start the brew)")
            await self._client.write_gatt_char(CHAR_COMMAND, build_commit(), response=False)
            acted = {
                STATE_STARTING,
                STATE_BREWING,
                STATE_POURING,
                STATE_POURING_MID,
                STATE_READY,
                STATE_COMPLETE,
                STATE_NO_WATER,
                STATE_NO_BEANS,
            }
            ev = await self._drain_for_any(acted, settle)
            if ev is not None:
                log.info("machine acted on commit (%s)", ev.state_name)
                return ev
            log.warning("no state seen %.1fs after commit — streaming telemetry for live state", settle)
            return StatusEvent(state=STATE_BREWING, state_name="brewing", raw=b"")
        finally:
            await self._stop_notify()

    async def brew(self, recipe: Recipe, *, settle: float = 2.0) -> StatusEvent:
        await self.load_recipe(recipe, settle=settle)
        return await self.start()

    async def cancel_brew(self) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")
        log.info("→ 0x47 cancel (aborting brew)")
        await self._client.write_gatt_char(CHAR_COMMAND, build_cancel(), response=False)

    async def save_slot(
        self,
        recipe: Recipe,
        slot: int,
        *,
        scale: bool = True,
        accept_timeout: float = 5.0,
        idle_timeout: float = 6.0,
    ) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")

        recipe.validate()
        frame = build_save_slot(recipe.to_protocol_dict(), slot, scale=scale)

        await self._start_notify()
        try:
            await self._client.write_gatt_char(CHAR_COMMAND, build_session_start(), response=False)
            await asyncio.sleep(0.5)

            log.info("→ save slot %s (scale=%s)", "ABC"[slot], scale)
            await self._client.write_gatt_char(CHAR_COMMAND, frame, response=False)
            accepted = await self._drain_for_any({STATE_SLOTS_SAVING, STATE_SLOTS_SAVED}, accept_timeout)
            if accepted is None:
                raise XBloomError("machine did not accept the slot write")
            if (
                accepted.state != STATE_SLOTS_SAVED
                and await self._drain_for_any({STATE_SLOTS_SAVED}, 1.0) is None
            ):
                log.info("→ back to normal (ends the single-slot saving state)")
                await self._client.write_gatt_char(CHAR_COMMAND, build_back_to_normal(), response=False)
                if await self._drain_for_any({STATE_IDLE, STATE_COMPLETE}, idle_timeout) is None:
                    log.warning("machine did not report idle after back to normal")
        finally:
            await self._stop_notify()

    async def save_slots(
        self,
        recipes: Sequence[Recipe] | Mapping[object, Recipe],
        *,
        scale: bool | Sequence[bool] = True,
        ensure_pro: bool = True,
        end_in_auto: bool = True,
    ) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")

        ordered = self._normalize_slots(recipes)
        scales = self._normalize_scale(scale)
        frames = []
        for i, recipe in enumerate(ordered):
            recipe.validate()
            frames.append(build_save_slot(recipe.to_protocol_dict(), i, scale=scales[i]))

        await self._start_notify()
        try:
            await self._client.write_gatt_char(
                CHAR_COMMAND, build_session_start(), response=False
            )
            if ensure_pro:
                log.info("→ set PRO mode (slot writes require it)")
                await self._client.write_gatt_char(
                    CHAR_COMMAND, build_set_mode(pro=True), response=False
                )
            try:
                await self._drain_until_state(STATE_IDLE, self.ack_timeout)
            except XBloomError:
                log.warning("machine idle not confirmed; proceeding (is it in AUTO mode?)")
            await asyncio.sleep(1.0)

            for i, frame in enumerate(frames):
                log.info("→ save slot %s (scale=%s)", "ABC"[i], scales[i])
                await self._client.write_gatt_char(CHAR_COMMAND, frame, response=False)
                await asyncio.sleep(0.5)

            await self._drain_until_state(STATE_SLOTS_SAVED, self.ack_timeout)
            log.info("presets stored to slots A/B/C")

            if end_in_auto:
                log.info("→ back to AUTO mode (presets ready on the dial)")
                await self._client.write_gatt_char(
                    CHAR_COMMAND, build_set_mode(pro=False), response=False
                )
                await asyncio.sleep(0.3)
        finally:
            await self._stop_notify()

    @staticmethod
    def _normalize_slots(
        recipes: Sequence[Recipe] | Mapping[object, Recipe],
    ) -> list[Recipe]:
        keymap = {0: 0, 1: 1, 2: 2, "a": 0, "b": 1, "c": 2, "A": 0, "B": 1, "C": 2}
        if isinstance(recipes, Mapping):
            out: list[Recipe | None] = [None, None, None]
            for key, recipe in recipes.items():
                idx = keymap.get(key if not isinstance(key, str) else key.lower())
                if idx is None:
                    raise XBloomError(f"unknown slot key {key!r} (use 0/1/2 or A/B/C)")
                out[idx] = recipe
            if any(r is None for r in out):
                raise XBloomError("save_slots needs all three slots (A, B and C)")
            return [r for r in out if r is not None]
        seq = list(recipes)
        if len(seq) != 3:
            raise XBloomError(f"save_slots needs exactly 3 recipes (A, B, C); got {len(seq)}")
        return seq

    @staticmethod
    def _normalize_scale(scale: bool | Sequence[bool]) -> list[bool]:
        if isinstance(scale, bool):
            return [scale, scale, scale]
        vals = [bool(s) for s in scale]
        if len(vals) != 3:
            raise XBloomError(f"scale sequence must have 3 entries; got {len(vals)}")
        return vals

    def _on_aux_notify(self, _sender, data: bytearray) -> None:
        log.debug("←aux %s", bytes(data).hex())

    async def stream_telemetry(
        self,
        on_event: Callable[[StatusEvent], Awaitable[None] | None],
        duration: float = 300.0,
        *,
        stop_on_terminal: bool = True,
        capture_aux: bool = False,
    ) -> None:
        if self._client is None or not self._client.is_connected:
            raise XBloomError("not connected")

        await self._start_notify()
        aux_on = False
        if capture_aux:
            try:
                await self._client.start_notify(CHAR_AUX, self._on_aux_notify)
                aux_on = True
                log.debug("aux capture on (ffe3) — hunting for the live-weight stream")
            except Exception as exc:
                log.debug("aux capture unavailable: %s", exc)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + duration
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    log.info("telemetry duration elapsed")
                    return
                try:
                    event = await asyncio.wait_for(self._notif_queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    log.info("telemetry duration elapsed")
                    return
                if event.is_heartbeat:
                    continue
                result = on_event(event)
                if asyncio.iscoroutine(result):
                    await result
                if stop_on_terminal and event.is_terminal:
                    log.info("terminal state '%s' reached", event.state_name)
                    return
        finally:
            if aux_on:
                try:
                    await self._client.stop_notify(CHAR_AUX)
                except Exception:
                    pass
            await self._stop_notify()
