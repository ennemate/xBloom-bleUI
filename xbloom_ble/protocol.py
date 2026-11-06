from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping

__all__ = [
    "PATTERN_CODES",
    "LOAD_SEQ",
    "crc16_kermit",
    "xbloom_frame",
    "build_a4",
    "build_a6",
    "build_a8",
    "build_41",
    "build_load_frames",
    "build_session_start",
    "build_status_query",
    "build_save_slot",
    "build_set_mode",
    "build_commit",
    "build_start",
    "build_cancel",
    "POURS_CMD_GRIND",
    "POURS_CMD_NO_GRIND",
    "NO_GRIND",
    "NO_GRIND_WIRE",
    "CMD_SAVE_SLOT",
    "CMD_SET_MODE",
    "LOAD_SEQ",
    "BREW_SEQ",
    "COMMIT_OPCODE",
    "START_OPCODE",
    "CANCEL_OPCODE",
    "xbloom_frame_1",
    "xbloom_frame_2",
    "CMD_TARE",
    "CMD_SET_POUR_RADIUS",
    "CMD_SET_POUR_PATTERN",
    "CMD_SET_TEMP",
    "CMD_WATER_START",
    "CMD_WATER_STOP",
    "CMD_POUR_START",
    "CMD_POUR_PAUSE",
    "CMD_BREWER_EXIT",
    "CMD_GRINDER_MODE",
    "CMD_GRINDER_START",
    "CMD_GRINDER_STOP",
    "CMD_GRINDER_EXIT",
    "CMD_SCALE_EXIT",
    "RADIUS_L1",
    "RADIUS_L2",
    "RADIUS_L3",
    "RADIUS_L4",
    "RADIUS_L5",
    "RADIUS_MAP",
    "parse_radius_level",
    "build_tare",
    "build_set_pour_radius",
    "build_set_pour_pattern",
    "build_set_temp",
    "build_water_start",
    "build_water_stop",
    "build_pour_start",
    "build_pour_pause",
    "build_brewer_mode",
    "build_brewer_exit",
    "build_grinder_mode",
    "build_grinder_start",
    "build_grinder_stop",
    "build_grinder_exit",
    "build_scale_exit",
    "CMD_BREWER_MODE",
]

XBLOOM_CHAR_FFE1 = "0000ffe1-0000-1000-8000-00805f9b34fb"
XBLOOM_CHAR_FFE2 = "0000ffe2-0000-1000-8000-00805f9b34fb"

LOAD_SEQ = 0x1F
BREW_SEQ = 0x9E

COMMIT_OPCODE = 0x42
START_OPCODE = 0x46
CANCEL_OPCODE = 0x47

PATTERN_CODES: dict[tuple[str, bool], tuple[int, int]] = {
    ("spiral", True): (0x02, 0x02),
    ("spiral", False): (0x02, 0x00),
    ("ring", False): (0x01, 0x00),
    ("center", False): (0x00, 0x01),
}

def crc16_kermit(data: bytes) -> int:
    crc = 0
    for byte in data:
        byte = int(f"{byte:08b}"[::-1], 2)
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return int(f"{crc:016b}"[::-1], 2)

def xbloom_frame(cmd: int, seq: int, payload: bytes) -> bytes:
    body = bytes([0x58, 0x01, 0x01, cmd, seq]) + b"\x00\x00" + b"\x00\x00" + payload
    total = len(body) + 2
    frame = bytearray(body)
    frame[5:7] = struct.pack("<H", total)
    crc = crc16_kermit(bytes(frame))
    return bytes(frame) + struct.pack("<H", crc)

def xbloom_frame_1(cmd: int, payload: bytes = b"") -> bytes:
    total = 12 + len(payload)
    body = bytearray(bytes([0x58, 0x01, 0x01]) + struct.pack("<H", cmd)
                     + struct.pack("<I", total) + bytes([0x01]) + payload)
    crc = crc16_kermit(bytes(body))
    return bytes(body) + struct.pack("<H", crc)

def xbloom_frame_2(cmd: int, payload: bytes = b"") -> bytes:
    body = bytearray(bytes([0x58, 0x01, 0x02]) + struct.pack("<H", cmd)
                     + b"\x00\x00\x00\x00" + bytes([0x01]) + payload)
    total = len(body) + 2
    body[5:9] = struct.pack("<I", total)
    crc = crc16_kermit(bytes(body))
    return bytes(body) + struct.pack("<H", crc)

def build_a4() -> bytes:
    return bytes.fromhex("01b900000001000000")

def build_a6(dose_g: int, bypass_volume: float = 0.0, bypass_temp: float = 0.0) -> bytes:
    pl = bytearray(13)
    pl[0] = 0x01
    if float(bypass_volume) > 0:
        pl[1:5] = struct.pack("<f", float(bypass_volume))
        pl[5:9] = struct.pack("<f", float(bypass_temp))
    pl[9] = int(dose_g) & 0xFF
    return bytes(pl)

def build_a8(temp1: float = 110.0, temp2: float = 90.0) -> bytes:
    f1 = struct.pack("<f", float(temp1))
    f2 = struct.pack("<f", float(temp2))
    return bytes([0x01]) + f1 + f2

def _pour_segments(p: Mapping) -> list[bytes]:
    pat_name = str(p.get("pattern", "spiral")).strip().lower()
    if pat_name in ("center", "1"):
        pat = 0x00
    elif pat_name in ("ring", "circular", "3"):
        pat = 0x01
    else:
        pat = 0x02

    has_explicit_before = "agitation_before" in p or "isEnableVibrationBefore" in p
    has_explicit_after = "agitation_after" in p or "isEnableVibrationAfter" in p

    if has_explicit_before or has_explicit_after:
        vibe_before = bool(p.get("agitation_before", False) or p.get("isEnableVibrationBefore", False))
        vibe_after = bool(p.get("agitation_after", False) or p.get("isEnableVibrationAfter", False) or p.get("agitation", False))
        agit = (0x01 if vibe_before else 0x00) | (0x02 if vibe_after else 0x00)
    else:
        has_agit = bool(p.get("agitation", False))
        pat_agit = PATTERN_CODES.get((pat_name, has_agit))
        if pat_agit is not None:
            pat, agit = pat_agit
        else:
            pat, agit = PATTERN_CODES.get((pat_name, False), (pat, 0x02 if has_agit else 0x00))

    ml = int(p["ml"])
    temp = int(p["temp"]) & 0xFF
    pause = int(p.get("pause", 0))
    rpm = int(p.get("rpm", 0)) & 0xFF
    flow10 = int(round(float(p.get("flow", 3.0)) * 10)) & 0xFF
    negpause = (256 - pause) & 0xFF
    segs: list[bytes] = []
    remaining = ml
    while remaining > 127:
        segs.append(bytes([127, temp, pat, agit]))
        remaining -= 127
    segs.append(bytes([remaining & 0xFF, temp, pat, agit, negpause, 0x00, rpm, flow10]))
    return segs

NO_GRIND = 0
NO_GRIND_WIRE = 0xFE

def _grind_byte(grind: int) -> int:
    return NO_GRIND_WIRE if int(grind) == NO_GRIND else int(grind) & 0xFF

def build_41(pours: Iterable[Mapping], grind: int, tail: int = 0xA0) -> bytes:
    segs: list[bytes] = []
    for i, p in enumerate(pours):
        segs.extend(_pour_segments({**p, "rpm": 0} if i else p))
    body = b"".join(segs)
    return bytes([0x01, len(body) & 0xFF]) + body + bytes([_grind_byte(grind), tail & 0xFF])

POURS_CMD_GRIND = 0x41
POURS_CMD_NO_GRIND = 0x44

def _ratio_byte(recipe: Mapping) -> int:
    if recipe.get("tail") is not None:
        return int(recipe["tail"]) & 0xFF
    total = sum(int(p["ml"]) for p in recipe["pours"])
    dose = int(recipe.get("dose", 0))
    return (round(total / dose * 10) & 0xFF) if dose else 0xA0

def build_load_frames(recipe: Mapping) -> list[bytes]:
    seq = recipe.get("seq", LOAD_SEQ)
    t1, t2 = recipe.get("stage_temps", (110.0, 90.0))
    tail = _ratio_byte(recipe)
    pours_cmd = POURS_CMD_NO_GRIND if int(recipe["grind"]) == 0 else POURS_CMD_GRIND
    if "bypass_enabled" in recipe:
        bp_enabled = bool(recipe.get("bypass_enabled", False))
    else:
        bp_enabled = float(recipe.get("bypass_volume", 0.0) or 0.0) > 0
    bypass_vol = float(recipe.get("bypass_volume", 0.0) or 0.0) if bp_enabled else 0.0
    bypass_temp = float(recipe.get("bypass_temp", 85.0) or 85.0) if bypass_vol > 0 else 0.0
    frames = [
        xbloom_frame(0xA4, seq, build_a4()),
        xbloom_frame(0xA6, seq, build_a6(recipe["dose"], bypass_vol, bypass_temp)),
        xbloom_frame(0xA8, seq, build_a8(t1, t2)),
        xbloom_frame(pours_cmd, seq, build_41(recipe["pours"], recipe["grind"], tail)),
    ]
    for fr in frames:
        if fr[3] in (COMMIT_OPCODE, START_OPCODE, CANCEL_OPCODE):
            raise AssertionError("load frames must never contain a brew-start/cancel opcode")
    return frames

def build_commit() -> bytes:
    return xbloom_frame(COMMIT_OPCODE, LOAD_SEQ, b"\x01")

def build_start() -> bytes:
    return xbloom_frame(START_OPCODE, BREW_SEQ, b"\x01")

def build_cancel() -> bytes:
    return xbloom_frame(CANCEL_OPCODE, BREW_SEQ, b"\x01")

def build_session_start() -> bytes:
    return xbloom_frame(0xA4, LOAD_SEQ, build_a4())

def build_status_query() -> bytes:
    return xbloom_frame(0x56, LOAD_SEQ, b"\x01")

CMD_SAVE_SLOT = 0x2CF6
SLOT_FLAG_SCALE_ON = 0x12
SLOT_FLAG_SCALE_OFF = 0x02

def build_save_slot(recipe: Mapping, slot: int, scale: bool = True) -> bytes:
    if slot not in (0, 1, 2):
        raise ValueError(f"slot must be 0 (A), 1 (B) or 2 (C); got {slot!r}")
    tail = _ratio_byte(recipe)
    blob = build_41(recipe["pours"], recipe["grind"], tail)
    flags = SLOT_FLAG_SCALE_ON if scale else SLOT_FLAG_SCALE_OFF
    payload = bytes([0x01, slot, flags]) + blob[1:]
    body = bytearray(bytes([0x58, 0x01, 0x02]) + struct.pack("<H", CMD_SAVE_SLOT)
                     + b"\x00\x00\x00\x00" + payload)
    body[5:9] = struct.pack("<I", len(body) + 2)
    return bytes(body) + struct.pack("<H", crc16_kermit(bytes(body)))

CMD_SET_MODE = 0x2CF7
MODE_PRO_PAYLOAD = bytes.fromhex("00000000")
MODE_AUTO_PAYLOAD = bytes.fromhex("91327856")

def build_set_mode(pro: bool = True) -> bytes:
    payload = bytes([0x01]) + (MODE_PRO_PAYLOAD if pro else MODE_AUTO_PAYLOAD)
    body = bytearray(bytes([0x58, 0x01, 0x02]) + struct.pack("<H", CMD_SET_MODE)
                     + b"\x00\x00\x00\x00" + payload)
    body[5:9] = struct.pack("<I", len(body) + 2)
    return bytes(body) + struct.pack("<H", crc16_kermit(bytes(body)))

CMD_TARE = 0x2134
CMD_SET_POUR_RADIUS = 0x2CF3
CMD_SET_POUR_PATTERN = 0x1F50
CMD_SET_TEMP = 0x119E
CMD_WATER_START = 0x119A
CMD_WATER_STOP = 0x119B
CMD_POUR_START = 0x1F55
CMD_POUR_PAUSE = 0x1F53
CMD_BREWER_MODE = 0x1F47
CMD_BREWER_EXIT = 0x1F4D
CMD_GRINDER_MODE = 0x1F46
CMD_GRINDER_START = 0x1F54
CMD_GRINDER_STOP = 0x0DB1
CMD_GRINDER_EXIT = 0x1F4C
CMD_SCALE_EXIT = 0x1F4E

RADIUS_L1 = 0
RADIUS_L2 = 1
RADIUS_L3 = 2
RADIUS_L4 = 3
RADIUS_L5 = 4

RADIUS_MAP: dict[str | int, int] = {
    "L1": RADIUS_L1, "l1": RADIUS_L1, 0: RADIUS_L1, "1": RADIUS_L1,
    "L2": RADIUS_L2, "l2": RADIUS_L2, 1: RADIUS_L2, "2": RADIUS_L2,
    "L3": RADIUS_L3, "l3": RADIUS_L3, 2: RADIUS_L3, "3": RADIUS_L3,
    "L4": RADIUS_L4, "l4": RADIUS_L4, 3: RADIUS_L4, "4": RADIUS_L4,
    "L5": RADIUS_L5, "l5": RADIUS_L5, 4: RADIUS_L5, "5": RADIUS_L5,
}

def parse_radius_level(val: str | int) -> int:
    if val in RADIUS_MAP:
        return RADIUS_MAP[val]
    try:
        iv = int(val)
        if 0 <= iv <= 4:
            return iv
        if 1 <= iv <= 5:
            return iv - 1
    except (ValueError, TypeError):
        pass
    return RADIUS_L3

def build_tare() -> bytes:
    return xbloom_frame_1(CMD_TARE, b"")

def build_set_pour_radius(level: str | int = RADIUS_L3, base_radius: int = 700) -> bytes:
    lvl = parse_radius_level(level)
    diff = int(lvl) - 2
    target_pos = max(540, min(860, int(base_radius) + diff * 80))
    payload = struct.pack("<I", int(target_pos) & 0xFFFFFFFF)
    return xbloom_frame_2(CMD_SET_POUR_RADIUS, payload)

def _direct_pattern_code(pattern: str | int) -> int:
    if isinstance(pattern, str):
        p = pattern.lower().strip()
        if p in ("center", "1"):
            return 0
        if p in ("circle", "circular", "ring", "3"):
            return 1
        return 3
    return int(pattern) & 0xFF

def _direct_temp_c(temp_c: float) -> float:
    temp = float(temp_c)
    if temp <= 0.0:
        return 20.0
    if temp >= 100.0:
        return 98.0
    return temp

def build_set_pour_pattern(pattern: str | int = "spiral") -> bytes:
    code = _direct_pattern_code(pattern)
    return xbloom_frame_1(CMD_SET_POUR_PATTERN, struct.pack("<I", code & 0xFFFFFFFF))

def build_set_temp(temp: float) -> bytes:
    t10 = int(round(_direct_temp_c(temp) * 10))
    return xbloom_frame_1(CMD_SET_TEMP, struct.pack("<I", t10 & 0xFFFFFFFF))

def build_water_start(
    volume_ml: float = 10.0,
    flow_rate: float = 3.0,
    temp_c: float = 93.0,
    pattern: str | int = "center",
    water_feed: int = 0,
) -> bytes:
    temp_whole = float(int(_direct_temp_c(temp_c)))
    flow_bits = struct.unpack("<I", struct.pack("<f", float(flow_rate) * 10.0))[0]
    vol_bits = struct.unpack("<I", struct.pack("<f", float(volume_ml) * 10.0))[0]
    temp_bits = struct.unpack("<I", struct.pack("<f", temp_whole * 10.0))[0]
    payload = struct.pack(
        "<IIIII", flow_bits, vol_bits, temp_bits, int(water_feed), _direct_pattern_code(pattern)
    )
    return xbloom_frame_1(CMD_WATER_START, payload)

def build_water_stop() -> bytes:
    return xbloom_frame_1(CMD_WATER_STOP, b"")

def build_pour_start(volume_ml: float = 0.0) -> bytes:
    return xbloom_frame_1(CMD_POUR_START, b"")

def build_pour_pause() -> bytes:
    return xbloom_frame_1(CMD_POUR_PAUSE, b"")

def build_brewer_mode(pattern: str | int = "center", temp_c: float = 85.0) -> bytes:
    temp_whole = float(int(_direct_temp_c(temp_c)))
    temp_bits = struct.unpack("<I", struct.pack("<f", temp_whole * 10.0))[0]
    payload = struct.pack("<II", _direct_pattern_code(pattern), temp_bits)
    return xbloom_frame_1(CMD_BREWER_MODE, payload)

def build_brewer_exit() -> bytes:
    return xbloom_frame_1(CMD_BREWER_EXIT, b"")

def build_grinder_mode(grind_size: int = 50, rpm: int = 80) -> bytes:
    payload = struct.pack("<II", int(grind_size) & 0xFFFFFFFF, int(rpm) & 0xFFFFFFFF)
    return xbloom_frame_1(CMD_GRINDER_MODE, payload)

def build_grinder_start(rpm: int = 80) -> bytes:
    return xbloom_frame_1(CMD_GRINDER_START, b"")

def build_grinder_stop() -> bytes:
    return xbloom_frame_1(CMD_GRINDER_STOP, b"")

def build_grinder_exit() -> bytes:
    return xbloom_frame_1(CMD_GRINDER_EXIT, b"")

def build_scale_exit() -> bytes:
    return xbloom_frame_1(CMD_SCALE_EXIT, b"")
