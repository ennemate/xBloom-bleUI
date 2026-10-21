from __future__ import annotations
import struct
from collections.abc import Iterable, Mapping
__all__ = ['PATTERN_CODES', 'LOAD_SEQ', 'crc16_kermit', 'xbloom_frame', 'build_a4', 'build_a6', 'build_a8', 'build_41', 'build_load_frames', 'build_session_start', 'build_status_query', 'build_save_slot', 'build_set_mode', 'build_commit', 'build_start', 'build_cancel', 'POURS_CMD_GRIND', 'POURS_CMD_NO_GRIND', 'NO_GRIND', 'NO_GRIND_WIRE', 'CMD_SAVE_SLOT', 'CMD_SET_MODE', 'LOAD_SEQ', 'BREW_SEQ', 'COMMIT_OPCODE', 'START_OPCODE', 'CANCEL_OPCODE']
LOAD_SEQ = 31
BREW_SEQ = 158
COMMIT_OPCODE = 66
START_OPCODE = 70
CANCEL_OPCODE = 71
PATTERN_CODES: dict[tuple[str, bool], tuple[int, int]] = {('spiral', True): (2, 2), ('spiral', False): (2, 0), ('ring', False): (1, 0), ('center', False): (0, 1)}

def crc16_kermit(data: bytes) -> int:
    crc = 0
    for byte in data:
        byte = int(f'{byte:08b}'[::-1], 2)
        crc ^= byte << 8
        for _ in range(8):
            if crc & 32768:
                crc = (crc << 1 ^ 4129) & 65535
            else:
                crc = crc << 1 & 65535
    return int(f'{crc:016b}'[::-1], 2)

def xbloom_frame(cmd: int, seq: int, payload: bytes) -> bytes:
    body = bytes([88, 1, 1, cmd, seq]) + b'\x00\x00' + b'\x00\x00' + payload
    total = len(body) + 2
    frame = bytearray(body)
    frame[5:7] = struct.pack('<H', total)
    crc = crc16_kermit(bytes(frame))
    return bytes(frame) + struct.pack('<H', crc)

def build_a4() -> bytes:
    return bytes.fromhex('01b900000001000000')

def build_a6(dose_g: int) -> bytes:
    pl = bytearray(13)
    pl[0] = 1
    pl[9] = int(dose_g) & 255
    return bytes(pl)

def build_a8(temp1: float=110.0, temp2: float=90.0) -> bytes:
    f1 = struct.pack('<f', float(temp1))
    f2 = struct.pack('<f', float(temp2))
    return bytes([1]) + f1 + f2

def _pour_segments(p: Mapping) -> list[bytes]:
    pat_name = str(p.get('pattern', 'spiral')).strip().lower()
    if pat_name in ('center', '1'):
        pat = 0
    elif pat_name in ('ring', 'circular', '3'):
        pat = 1
    else:
        pat = 2
    has_explicit_before = 'agitation_before' in p or 'isEnableVibrationBefore' in p
    has_explicit_after = 'agitation_after' in p or 'isEnableVibrationAfter' in p
    if has_explicit_before or has_explicit_after:
        vibe_before = bool(p.get('agitation_before', False) or p.get('isEnableVibrationBefore', False))
        vibe_after = bool(p.get('agitation_after', False) or p.get('isEnableVibrationAfter', False) or p.get('agitation', False))
        agit = (1 if vibe_before else 0) | (2 if vibe_after else 0)
    else:
        has_agit = bool(p.get('agitation', False))
        pat_agit = PATTERN_CODES.get((pat_name, has_agit))
        if pat_agit is not None:
            pat, agit = pat_agit
        else:
            pat, agit = PATTERN_CODES.get((pat_name, False), (pat, 2 if has_agit else 0))
    ml = int(p['ml'])
    temp = int(p['temp']) & 255
    pause = int(p.get('pause', 0))
    rpm = int(p.get('rpm', 0)) & 255
    flow10 = int(round(float(p.get('flow', 3.0)) * 10)) & 255
    negpause = 256 - pause & 255
    segs: list[bytes] = []
    remaining = ml
    while remaining > 127:
        segs.append(bytes([127, temp, pat, agit]))
        remaining -= 127
    segs.append(bytes([remaining & 255, temp, pat, agit, negpause, 0, rpm, flow10]))
    return segs
NO_GRIND = 0
NO_GRIND_WIRE = 254

def _grind_byte(grind: int) -> int:
    return NO_GRIND_WIRE if int(grind) == NO_GRIND else int(grind) & 255

def build_41(pours: Iterable[Mapping], grind: int, tail: int=160) -> bytes:
    segs: list[bytes] = []
    for i, p in enumerate(pours):
        segs.extend(_pour_segments({**p, 'rpm': 0} if i else p))
    body = b''.join(segs)
    return bytes([1, len(body) & 255]) + body + bytes([_grind_byte(grind), tail & 255])
POURS_CMD_GRIND = 65
POURS_CMD_NO_GRIND = 68

def _ratio_byte(recipe: Mapping) -> int:
    if recipe.get('tail') is not None:
        return int(recipe['tail']) & 255
    total = sum((int(p['ml']) for p in recipe['pours']))
    dose = int(recipe.get('dose', 0))
    return round(total / dose * 10) & 255 if dose else 160

def build_load_frames(recipe: Mapping) -> list[bytes]:
    seq = recipe.get('seq', LOAD_SEQ)
    t1, t2 = recipe.get('stage_temps', (110.0, 90.0))
    tail = _ratio_byte(recipe)
    pours_cmd = POURS_CMD_NO_GRIND if int(recipe['grind']) == 0 else POURS_CMD_GRIND
    frames = [xbloom_frame(164, seq, build_a4()), xbloom_frame(166, seq, build_a6(recipe['dose'])), xbloom_frame(168, seq, build_a8(t1, t2)), xbloom_frame(pours_cmd, seq, build_41(recipe['pours'], recipe['grind'], tail))]
    for fr in frames:
        if fr[3] in (COMMIT_OPCODE, START_OPCODE, CANCEL_OPCODE):
            raise AssertionError('load frames must never contain a brew-start/cancel opcode')
    return frames

def build_commit() -> bytes:
    return xbloom_frame(COMMIT_OPCODE, LOAD_SEQ, b'\x01')

def build_start() -> bytes:
    return xbloom_frame(START_OPCODE, BREW_SEQ, b'\x01')

def build_cancel() -> bytes:
    return xbloom_frame(CANCEL_OPCODE, BREW_SEQ, b'\x01')

def build_session_start() -> bytes:
    return xbloom_frame(164, LOAD_SEQ, build_a4())

def build_status_query() -> bytes:
    return xbloom_frame(86, LOAD_SEQ, b'\x01')
CMD_SAVE_SLOT = 11510
SLOT_FLAG_SCALE_ON = 18
SLOT_FLAG_SCALE_OFF = 2

def build_save_slot(recipe: Mapping, slot: int, scale: bool=True) -> bytes:
    if slot not in (0, 1, 2):
        raise ValueError(f'slot must be 0 (A), 1 (B) or 2 (C); got {slot!r}')
    tail = _ratio_byte(recipe)
    blob = build_41(recipe['pours'], recipe['grind'], tail)
    flags = SLOT_FLAG_SCALE_ON if scale else SLOT_FLAG_SCALE_OFF
    payload = bytes([1, slot, flags]) + blob[1:]
    body = bytearray(bytes([88, 1, 2]) + struct.pack('<H', CMD_SAVE_SLOT) + b'\x00\x00\x00\x00' + payload)
    body[5:9] = struct.pack('<I', len(body) + 2)
    return bytes(body) + struct.pack('<H', crc16_kermit(bytes(body)))
CMD_SET_MODE = 11511
MODE_PRO_PAYLOAD = bytes.fromhex('00000000')
MODE_AUTO_PAYLOAD = bytes.fromhex('91327856')

def build_set_mode(pro: bool=True) -> bytes:
    payload = bytes([1]) + (MODE_PRO_PAYLOAD if pro else MODE_AUTO_PAYLOAD)
    body = bytearray(bytes([88, 1, 2]) + struct.pack('<H', CMD_SET_MODE) + b'\x00\x00\x00\x00' + payload)
    body[5:9] = struct.pack('<I', len(body) + 2)
    return bytes(body) + struct.pack('<H', crc16_kermit(bytes(body)))
