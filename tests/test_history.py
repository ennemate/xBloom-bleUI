import pytest
import asyncio
import os
import json
from server import (
    app, HISTORY_FILE, server_config,
    load_brew_history, save_brew_history,
    get_history, add_history_record, update_history_notes,
    delete_history_record, clear_all_history,
    get_settings, update_settings,
    HistoryItemModel, HistoryUpdateNotesModel, SettingsUpdateModel
)

@pytest.fixture(autouse=True)
def clean_history_file():
    backup = None
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            backup = f.read()
    yield
    if backup is not None:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write(backup)
    elif os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except Exception:
            pass

@pytest.mark.anyio
async def test_history_crud_lifecycle():
    # 1. 초기 상태 조회
    res = await get_history(limit=100)
    initial_total = res["total"]

    # 2. 새 기록 추가 (정상 완료)
    new_record = HistoryItemModel(
        recipeName="Test Ethiopian",
        dose=16,
        totalWater=250.0,
        totalYield=215.5,
        duration="02:45",
        durationSec=165,
        status="completed",
        chartData=[{"time": 0, "pour": 0, "yield": 0}, {"time": 165, "pour": 250, "yield": 215.5}],
        recipe={
            "name": "Test Ethiopian",
            "dose": 16,
            "grind_size": 42,
            "grind_rpm": 90,
            "steps": [{"water": 50, "temp": 93, "wait": 15, "flow": 3.0, "pattern": "center"}]
        },
        beanName="Yirgacheffe G1",
        notes="밝은 산미와 재스민 향"
    )
    add_res = await add_history_record(new_record)
    assert add_res["status"] == "saved"
    created = add_res["record"]
    assert created["recipeName"] == "Test Ethiopian"
    assert created["beanName"] == "Yirgacheffe G1"
    record_id = created["id"]
    assert record_id.startswith("hist_")

    # 3. 목록 조회 검증
    res2 = await get_history(limit=100)
    records = res2["records"]
    assert len(records) == initial_total + 1
    assert records[0]["id"] == record_id

    # 4. 메모/노트 수정 (PUT)
    update_res = await update_history_notes(record_id, HistoryUpdateNotesModel(
        beanName="Yirgacheffe G1 Washed (Updated)",
        notes="단맛이 더 좋아짐"
    ))
    assert update_res["status"] == "updated"
    updated = update_res["record"]
    assert updated["beanName"] == "Yirgacheffe G1 Washed (Updated)"
    assert updated["notes"] == "단맛이 더 좋아짐"

    # 5. 비상정지 기록 추가 테스트
    aborted_record = HistoryItemModel(
        recipeName="Aborted Brew",
        dose=15,
        totalWater=80.0,
        totalYield=40.0,
        duration="00:45",
        status="aborted",
        chartData=[{"time": 0, "pour": 0, "yield": 0}, {"time": 45, "pour": 80, "yield": 40}]
    )
    aborted_res = await add_history_record(aborted_record)
    assert aborted_res["status"] == "saved"
    aborted_id = aborted_res["record"]["id"]

    # 6. 단일 삭제
    del_res = await delete_history_record(aborted_id)
    assert del_res["status"] == "deleted"
    assert del_res["id"] == aborted_id

    # 7. 전체 삭제
    clear_res = await clear_all_history()
    assert clear_res["status"] == "cleared"
    res_empty = await get_history()
    assert res_empty["total"] == 0

@pytest.mark.anyio
async def test_settings_record_aborted_brews_toggle():
    # 기본값 조회
    cfg = await get_settings()
    assert "record_aborted_brews" in cfg

    # 토글 ON
    res_on = await update_settings(SettingsUpdateModel(record_aborted_brews=True))
    assert res_on["status"] == "ok"
    assert res_on["config"]["record_aborted_brews"] is True

    # 토글 OFF
    res_off = await update_settings(SettingsUpdateModel(record_aborted_brews=False))
    assert res_off["status"] == "ok"
    assert res_off["config"]["record_aborted_brews"] is False
