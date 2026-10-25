import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from xbloom_ble.client import (
    XBloomClient,
    STATE_POURING,
    STATE_POURING_MID,
    STATE_BREWING,
    STATE_STARTING,
    STATE_ARMED,
    STATE_NO_WATER,
    STATE_NO_BEANS,
)
from xbloom_ble.telemetry import StatusEvent, parse_notification
from server import on_machine_telemetry, latest_telemetry


def test_telemetry_listener_fanout():
    """add_telemetry_listener로 등록된 콜백이 _on_notify 시 정상 호출되는지 검증"""
    client = XBloomClient("00:11:22:33:44:55")
    received_events = []

    def my_listener(ev):
        received_events.append(ev)

    client.add_telemetry_listener(my_listener)

    # water scale notification: 35.0g
    water_raw = bytes.fromhex("5802074b9e10000000c100b808470000")
    client._on_notify(None, bytearray(water_raw))

    assert len(received_events) == 1
    assert received_events[0].water_g == 35.0

    # coffee scale notification: 12.12g
    coffee_raw = bytes.fromhex("580207155010000000c19eef41410000")
    client._on_notify(None, bytearray(coffee_raw))

    assert len(received_events) == 2
    assert received_events[1].coffee_g == 12.12

    # Unregister listener
    client.remove_telemetry_listener(my_listener)
    client._on_notify(None, bytearray(water_raw))
    assert len(received_events) == 2  # 더 이상 수신되지 않음


def test_start_acted_states_include_pouring():
    """commit 후 머신이 0x10(POURING) 또는 0x23(POURING_MID)을 보냈을 때 0x46 재전송 없이 바로 반환하는지 검증"""
    async def _run():
        client = XBloomClient("00:11:22:33:44:55")
        client._client = AsyncMock()
        client._client.is_connected = True

        # 1. 머신이 0x10 (POURING)을 보고하는 경우
        ev_10 = StatusEvent(state=STATE_POURING, state_name="brewing", raw=b"mock_10")
        
        # _drain_for_any가 ev_10을 반환하도록 설정
        async def mock_drain(states, timeout):
            assert STATE_POURING in states
            assert STATE_POURING_MID in states
            return ev_10

        client._drain_for_any = mock_drain

        res = await client.start(settle=1.0)
        assert res.state == STATE_POURING
        # write_gatt_char는 build_commit() 한 번만 호출되어야 함 (0x46 start는 호출되지 않아야 함!)
        assert client._client.write_gatt_char.call_count == 1
        written_cmd = client._client.write_gatt_char.call_args[0][1]
        assert written_cmd[3] == 0x42  # 0x42 commit

    asyncio.run(_run())


def test_server_on_machine_telemetry_persistence():
    """server.py의 on_machine_telemetry가 water_g와 coffee_g를 독립적으로 보존하고 상태를 정상 반영하는지 검증"""
    # 초기 상태
    latest_telemetry["pour_weight"] = 0.0
    latest_telemetry["yield_weight"] = 0.0
    latest_telemetry["state"] = "IDLE"

    # 1. water_g 수신
    ev_water = StatusEvent(state=None, state_name="scale", raw=b"", water_g=45.5, coffee_g=None)
    on_machine_telemetry(ev_water)

    assert latest_telemetry["pour_weight"] == 45.5
    assert latest_telemetry["yield_weight"] == 0.0
    assert latest_telemetry["state"] == "IDLE"  # 'scale'은 기존 상태 유지

    # 2. coffee_g 수신
    ev_coffee = StatusEvent(state=None, state_name="scale", raw=b"", water_g=None, coffee_g=18.2)
    on_machine_telemetry(ev_coffee)

    assert latest_telemetry["pour_weight"] == 45.5  # 물 무게 보존!
    assert latest_telemetry["yield_weight"] == 18.2  # 커피 무게 갱신!
    assert latest_telemetry["state"] == "IDLE"

    # 3. 상태 변경 이벤트 수신 (0x10 brewing)
    ev_brew = StatusEvent(state=0x10, state_name="brewing", raw=b"")
    on_machine_telemetry(ev_brew)

    assert latest_telemetry["state"] == "BREWING"
    assert latest_telemetry["pour_weight"] == 45.5
    assert latest_telemetry["yield_weight"] == 18.2


def test_build_load_frames_center_and_ring_agitation_no_keyerror():
    """푸어 패턴이 center거나 ring일 때 agitation: True여도 KeyError 없이 4개 프레임을 안전하게 생성하는지 검증"""
    from xbloom_ble.protocol import build_load_frames

    recipe_dict = {
        "dose": 15,
        "grind": 45,
        "pours": [
            {"ml": 40, "temp": 93, "pattern": "center", "agitation": True, "pause": 30, "rpm": 0, "flow": 3.0},
            {"ml": 100, "temp": 92, "pattern": "ring", "agitation": True, "pause": 10, "rpm": 90, "flow": 3.2},
            {"ml": 60, "temp": 90, "pattern": "spiral", "agitation": True, "pause": 0, "rpm": 100, "flow": 3.2},
        ]
    }

    # KeyError: ('center', True) 또는 ('ring', True)가 발생하지 않고 정상 생성되어야 함
    frames = build_load_frames(recipe_dict)
    assert len(frames) == 4
    # 4개 프레임 opcodes: 0xa4 (start), 0xa6 (dose), 0xa8 (temps), 0x41 (pours)
    assert [f[3] for f in frames] == [0xA4, 0xA6, 0xA8, 0x41]


def test_recipe_model_dual_agitation_validation_and_omissions():
    """Recipe 모델이 ring 교반 및 agitation_before를 정상 수용하고 to_protocol_dict가 필드를 보존하는지 검증"""
    from xbloom_ble.recipe import Recipe, MODEL_PATTERN_COMBOS

    assert ("ring", True) in MODEL_PATTERN_COMBOS

    rec = Recipe.from_dict({
        "name": "Ring Agitation & Before Test",
        "dose_g": 16,
        "grind": 50,
        "pours": [
            {"ml": 40, "temp_c": 92, "pattern": "center", "agitation": False, "agitation_before": True, "rpm": 0},
            {"ml": 100, "temp_c": 92, "pattern": "ring", "agitation": True, "agitation_before": True, "rpm": 80},
            {"ml": 60, "temp_c": 90, "pattern": "spiral", "agitation": True, "agitation_before": False, "rpm": 100},
        ]
    })

    # validate()가 예외 없이 통과해야 함
    rec.validate()

    # to_protocol_dict()가 agitation_before와 agitation_after를 프로토콜 빌더로 온전히 전달하는지 확인
    proto = rec.to_protocol_dict()
    assert proto["pours"][0]["agitation_before"] is True
    assert proto["pours"][1]["agitation_before"] is True
    assert proto["pours"][1]["agitation"] is True
    assert proto["pours"][2]["agitation"] is True


def test_server_build_official_recipe_object_with_dual_agitation():
    """server.py의 build_official_recipe_object가 듀얼 교반 및 center/ring을 안전하게 변환하는지 검증"""
    from server import RecipeModel, StepModel, build_official_recipe_object
    from xbloom_ble.protocol import build_load_frames

    recipe_model = RecipeModel(
        name="UI Recipe",
        dose=16,
        grind_size=40,
        grind_enabled=True,
        grind_rpm=80,
        steps=[
            StepModel(temp=93, water=50, wait=30, flow=3.0, pattern="center", agitation_before=True, agitation_after=True),
            StepModel(temp=92, water=100, wait=15, flow=3.2, pattern="ring", agitation_before=True, agitation_after=True),
            StepModel(temp=90, water=100, wait=0, flow=3.5, pattern="spiral", agitation_before=False, agitation_after=True),
        ]
    )

    rec_obj = build_official_recipe_object(recipe_model)
    # load_frames 생성 시 KeyError 없이 정상 바이트 생성 확인
    frames = build_load_frames(rec_obj.to_protocol_dict())
    assert len(frames) == 4


def test_all_patterns_agitation_bitmask_verification():
    """모든 패턴(Center, Ring, Spiral)에서 추출 전(0x01) 및 추출 후(0x02) 교반 비트마스크 검증"""
    from xbloom_ble.protocol import _pour_segments

    # 1. Center (pat = 0x00)
    assert _pour_segments({"ml": 40, "temp": 93, "pattern": "center", "agitation_before": False, "agitation_after": False})[0][2:4] == bytes([0x00, 0x00])
    assert _pour_segments({"ml": 40, "temp": 93, "pattern": "center", "agitation_before": True, "agitation_after": False})[0][2:4] == bytes([0x00, 0x01])  # 전 진동 ON
    assert _pour_segments({"ml": 40, "temp": 93, "pattern": "center", "agitation_before": False, "agitation_after": True})[0][2:4] == bytes([0x00, 0x02])  # 후 진동 ON
    assert _pour_segments({"ml": 40, "temp": 93, "pattern": "center", "agitation_before": True, "agitation_after": True})[0][2:4] == bytes([0x00, 0x03])   # 둘 다 ON

    # 2. Ring (pat = 0x01)
    assert _pour_segments({"ml": 50, "temp": 92, "pattern": "ring", "agitation_before": False, "agitation_after": False})[0][2:4] == bytes([0x01, 0x00])
    assert _pour_segments({"ml": 50, "temp": 92, "pattern": "ring", "agitation_before": True, "agitation_after": False})[0][2:4] == bytes([0x01, 0x01])    # 전 진동 ON
    assert _pour_segments({"ml": 50, "temp": 92, "pattern": "ring", "agitation_before": False, "agitation_after": True})[0][2:4] == bytes([0x01, 0x02])    # 후 진동 ON
    assert _pour_segments({"ml": 50, "temp": 92, "pattern": "ring", "agitation_before": True, "agitation_after": True})[0][2:4] == bytes([0x01, 0x03])     # 둘 다 ON

    # 3. Spiral (pat = 0x02)
    assert _pour_segments({"ml": 60, "temp": 90, "pattern": "spiral", "agitation_before": False, "agitation_after": False})[0][2:4] == bytes([0x02, 0x00])
    assert _pour_segments({"ml": 60, "temp": 90, "pattern": "spiral", "agitation_before": True, "agitation_after": False})[0][2:4] == bytes([0x02, 0x01])  # 전 진동 ON
    assert _pour_segments({"ml": 60, "temp": 90, "pattern": "spiral", "agitation_before": False, "agitation_after": True})[0][2:4] == bytes([0x02, 0x02])  # 후 진동 ON
    assert _pour_segments({"ml": 60, "temp": 90, "pattern": "spiral", "agitation_before": True, "agitation_after": True})[0][2:4] == bytes([0x02, 0x03])   # 둘 다 ON


