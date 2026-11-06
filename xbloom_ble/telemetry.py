from __future__ import annotations

import struct
from dataclasses import dataclass

__all__ = [
    "STATE_NAMES",
    "IGNORED_STATES",
    "TERMINAL_STATES",
    "StatusEvent",
    "parse_notification",
    "is_idle_or_complete",
]

STATE_NAMES: dict[int, str] = {
    0x01: "idle",
    0x0A: "standby",
    0x0C: "no_water",
    0x0F: "no_beans",
    0x10: "brewing",
    0x1D: "loading",
    0x1F: "armed",
    0x1E: "awaiting_confirm",
    0x22: "starting",
    0x23: "brewing",
    0x24: "ready",
    0x3B: "brewing",
    0x41: "complete",
    0x43: "saving_slots",
    0x25: "slots_saved",
}

WATER_TYPE = 0x4B
COFFEE_TYPE = 0x15
IGNORED_STATES = frozenset({0x15, 0x4B})

TERMINAL_STATES = frozenset({0x24, 0x41, 0x01})

STATUS_CMD = 0x57
STATE_MARKER = 0xC1

@dataclass
class StatusEvent:

    state: int | None
    state_name: str
    raw: bytes
    water_g: float | None = None
    coffee_g: float | None = None

    @property
    def is_heartbeat(self) -> bool:
        return self.state in IGNORED_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def __str__(self) -> str:
        bits = [self.state_name]
        if self.water_g is not None:
            bits.append(f"water={self.water_g:g}g")
        if self.coffee_g is not None:
            bits.append(f"coffee={self.coffee_g:g}g")
        return " ".join(bits)

def _marker_idx(data: bytes) -> int:
    if len(data) > 9 and data[9] == STATE_MARKER:
        return 9
    return data.find(STATE_MARKER, 5)

def _decode_scale_grams(data: bytes, *, scale: float) -> float | None:
    marker = _marker_idx(data)
    if marker < 0 or marker + 5 > len(data):
        return None
    try:
        raw = struct.unpack_from("<f", data, marker + 1)[0]
    except struct.error:
        return None
    grams = raw * scale
    if grams != grams or grams < -0.5 or grams > 2000.0:
        return None
    return round(max(0.0, grams), 2)

def parse_notification(data: bytes) -> StatusEvent | None:
    if isinstance(data, str):
        data = bytes.fromhex(data.replace(" ", ""))
    else:
        data = bytes(data)

    if len(data) < 10 or data[0] != 0x58:
        return None

    ftype = data[3]

    if ftype == WATER_TYPE:
        g = _decode_scale_grams(data, scale=0.001)
        return StatusEvent(state=None, state_name="scale", raw=data, water_g=g)
    if ftype == COFFEE_TYPE:
        g = _decode_scale_grams(data, scale=1.0)
        return StatusEvent(state=None, state_name="scale", raw=data, coffee_g=g)

    marker = _marker_idx(data)
    payload = data[marker + 1 : -2] if marker >= 0 else b""

    if ftype == STATUS_CMD and payload:
        state = payload[0]
        name = STATE_NAMES.get(state, f"unknown_0x{state:02x}")
        return StatusEvent(state=state, state_name=name, raw=data)

    return StatusEvent(state=None, state_name=f"ack_0x{ftype:02x}", raw=data)

def is_idle_or_complete(event: StatusEvent) -> bool:
    return event.state in TERMINAL_STATES
