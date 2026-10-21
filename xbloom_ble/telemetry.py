from __future__ import annotations
import struct
from dataclasses import dataclass
__all__ = ['STATE_NAMES', 'IGNORED_STATES', 'TERMINAL_STATES', 'StatusEvent', 'parse_notification', 'is_idle_or_complete']
STATE_NAMES: dict[int, str] = {1: 'idle', 10: 'standby', 12: 'no_water', 15: 'no_beans', 16: 'brewing', 29: 'loading', 31: 'armed', 30: 'awaiting_confirm', 34: 'starting', 35: 'brewing', 36: 'ready', 59: 'brewing', 65: 'complete', 67: 'saving_slots', 37: 'slots_saved'}
WATER_TYPE = 75
COFFEE_TYPE = 21
IGNORED_STATES = frozenset({21, 75})
TERMINAL_STATES = frozenset({36, 65, 1})
STATUS_CMD = 87
STATE_MARKER = 193

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
            bits.append(f'water={self.water_g:g}g')
        if self.coffee_g is not None:
            bits.append(f'coffee={self.coffee_g:g}g')
        return ' '.join(bits)

def _marker_idx(data: bytes) -> int:
    if len(data) > 9 and data[9] == STATE_MARKER:
        return 9
    return data.find(STATE_MARKER, 5)

def _decode_scale_grams(data: bytes, *, scale: float) -> float | None:
    marker = _marker_idx(data)
    if marker < 0 or marker + 5 > len(data):
        return None
    try:
        raw = struct.unpack_from('<f', data, marker + 1)[0]
    except struct.error:
        return None
    grams = raw * scale
    if grams != grams or grams < 0.0 or grams > 2000.0:
        return None
    return round(grams, 2)

def parse_notification(data: bytes) -> StatusEvent | None:
    if isinstance(data, str):
        data = bytes.fromhex(data.replace(' ', ''))
    else:
        data = bytes(data)
    if len(data) < 10 or data[0] != 88:
        return None
    ftype = data[3]
    if ftype == WATER_TYPE:
        g = _decode_scale_grams(data, scale=0.001)
        return StatusEvent(state=None, state_name='scale', raw=data, water_g=g)
    if ftype == COFFEE_TYPE:
        g = _decode_scale_grams(data, scale=1.0)
        return StatusEvent(state=None, state_name='scale', raw=data, coffee_g=g)
    marker = _marker_idx(data)
    payload = data[marker + 1:-2] if marker >= 0 else b''
    if ftype == STATUS_CMD and payload:
        state = payload[0]
        name = STATE_NAMES.get(state, f'unknown_0x{state:02x}')
        return StatusEvent(state=state, state_name=name, raw=data)
    return StatusEvent(state=None, state_name=f'ack_0x{ftype:02x}', raw=data)

def is_idle_or_complete(event: StatusEvent) -> bool:
    return event.state in TERMINAL_STATES
