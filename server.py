import shutil
import ai_service

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import asyncio
import json
import re
import time
import glob
import argparse
import traceback
import zipfile
import subprocess
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import urllib.request
import urllib.parse

CURRENT_VERSION = "2.0.1"
GITHUB_REPO = "ennemate/xBloom-bleUI"

import uvicorn
import yaml
from xbloom_ble.protocol import build_set_pour_radius
from xbloom_ble.v2_engine import AdvancedRecipeOrchestrator, OrchestratorState, StepProgress
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from bleak import BleakScanner

from xbloom_ble.client import XBloomClient
import xbloom_ble.recipe as recipe_module

RecipeClass = getattr(recipe_module, "Recipe", None)
StepClass = None
for candidate in ["Step", "PourStep", "RecipeStep", "Pour"]:
    if hasattr(recipe_module, candidate):
        StepClass = getattr(recipe_module, candidate)
        break

try:
    import xbloom_ble.cloud as cloud_module
except Exception as ce:
    print(f"[WARN] Failed to import xbloom_ble.cloud: {ce}")
    cloud_module = None

def get_cloud_handler():
    if not cloud_module:
        return None
    if hasattr(cloud_module, "login"):
        return cloud_module
    for attr_name in ["XBloomCloudClient", "CloudClient", "XBloomCloud", "Cloud"]:
        if hasattr(cloud_module, attr_name):
            cls = getattr(cloud_module, attr_name)
            if isinstance(cls, type):
                try:
                    return cls()
                except Exception:
                    pass
    return cloud_module

cloud_client = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
RECIPES_DIR = os.path.join(BASE_DIR, "recipes")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(RECIPES_DIR, exist_ok=True)

def normalize_pattern(pat: Optional[str]) -> str:
    p = str(pat or "center").strip().lower()
    if p in ["ring", "circle", "circular"]:
        return "ring"
    if p in ["spiral"]:
        return "spiral"
    return "center"

def load_server_config() -> Dict[str, Any]:
    default_config = {
        "theme": "dark",
        "wallpaper": None,
        "language": "auto",
        "cloud_user": None,
        "record_aborted_brews": False,
        "pour_marker_mode": "weight",
        "chart_smoothing": True,
        "handdrip_interval_sync": False,
        "enable_advanced_recipe": False,
        "default_radius": "L3"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if isinstance(cfg, dict):
                    try:
                        shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".bak")
                    except Exception:
                        pass
                    return {**default_config, **cfg}
        except Exception as e:
            print(f"[WARN] Failed to load config.json: {e}")
            return default_config
    else:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            print("[INIT] First run: config.json default configuration file created.")
        except Exception as e:
            print(f"[WARN] Failed to create config.json: {e}")
    return default_config

def save_server_config(cfg: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")

server_config = load_server_config()

def load_brew_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    if len(data) > 0:
                        try:
                            shutil.copy2(HISTORY_FILE, HISTORY_FILE + ".bak")
                        except Exception:
                            pass
                    return data
        except Exception as e:
            print(f"[WARN] Failed to load history.json: {e}")
            bak_file = HISTORY_FILE + ".bak"
            if os.path.exists(bak_file):
                try:
                    with open(bak_file, "r", encoding="utf-8") as bf:
                        bak_data = json.load(bf)
                        if isinstance(bak_data, list):
                            print("[HIST] Corrupted history.json automatically restored from backup (.bak).")
                            return bak_data
                except Exception:
                    pass
    else:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print("[INIT] First run: history.json brew history file created.")
        except Exception as e:
            print(f"[WARN] Failed to create history.json: {e}")
    return []

initial_history = load_brew_history()

def save_brew_history(records: List[Dict[str, Any]]):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(records[:500], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save history.json: {e}")

def restore_cloud_session():
    global cloud_client
    if not cloud_client:
        cloud_client = get_cloud_handler()
    if not cloud_client or not server_config.get("cloud_user"):
        return
    token = server_config["cloud_user"].get("token")
    if token:
        for attr in ["token", "access_token", "_token", "_access_token"]:
            if hasattr(cloud_client, attr):
                try:
                    setattr(cloud_client, attr, token)
                except Exception:
                    pass
        for method in ["set_token", "set_auth_token", "authenticate_with_token"]:
            if hasattr(cloud_client, method):
                try:
                    getattr(cloud_client, method)(token)
                except Exception:
                    pass

ble_client: Optional[XBloomClient] = None
connected_websockets = set()
main_loop: Optional[asyncio.AbstractEventLoop] = None
ble_lock = asyncio.Lock()

latest_telemetry: Dict[str, Any] = {
    "temperature": 0,
    "pour_weight": 0.0,
    "yield_weight": 0.0,
    "state": "IDLE",
    "elapsed_time": 0,
    "step_index": 0
}
ble_connection_status = "DISCONNECTED"
discovered_device_address = None
v2_orchestrator: Optional[AdvancedRecipeOrchestrator] = None

class StepModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    temp: Optional[Union[int, float]] = 93
    water: Optional[Union[int, float]] = None
    pour: Optional[Union[int, float]] = None
    ml: Optional[Union[int, float]] = None
    wait: Optional[Union[int, float]] = 15
    flow: Optional[Union[int, float]] = 3.2
    pattern: Optional[str] = "center"
    agitation_before: Optional[bool] = False
    agitation_after: Optional[bool] = False
    radius: Optional[str] = "L3"
    step_time: Optional[Union[int, float]] = 0

class RecipeModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "Custom Brew"
    dose: Union[int, float] = 15
    grind_size: Union[int, float] = 45
    grind_enabled: Optional[bool] = True
    grind_rpm: int = 80
    interval_sync: Optional[bool] = False
    bypass_enabled: Optional[bool] = False
    bypass_volume: float = 0.0
    bypass_temp: float = 85.0
    is_advanced: Optional[bool] = False
    schema_version: Optional[int] = 1
    auto_grind: Optional[bool] = True
    mode: str = "coffee"
    beverage_type: Optional[str] = "coffee"
    tea_type: Optional[str] = None
    tea_cups: Optional[List[Any]] = None
    steps: List[StepModel] = Field(default_factory=list)

class CloudLoginModel(BaseModel):
    email: str
    password: str

class FetchSharedRecipeRequest(BaseModel):
    url: str

class SettingsUpdateModel(BaseModel):
    theme: Optional[str] = None
    wallpaper: Optional[str] = None
    language: Optional[str] = None
    record_aborted_brews: Optional[bool] = None
    pour_marker_mode: Optional[str] = None
    chart_smoothing: Optional[bool] = None
    handdrip_interval_sync: Optional[bool] = None
    show_micron: Optional[bool] = None
    enable_advanced_recipe: Optional[bool] = None
    default_radius: Optional[str] = None

class AISettingsUpdateModel(BaseModel):
    provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    model: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_model: Optional[str] = None

class AITestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None

class AIExtractRecipeRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    lang: Optional[str] = "ko"
    images: Optional[List[Dict[str, Any]]] = None

class AIBaristaChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    telemetry: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    lang: Optional[str] = "ko"
    personality: Optional[str] = "balanced"

class HistoryItemModel(BaseModel):
    id: Optional[str] = None
    date: Optional[str] = None
    recipeName: str = "Custom Brew"
    dose: int = 15
    totalWater: float = 0.0
    totalYield: float = 0.0
    duration: str = "00:00"
    durationSec: Optional[int] = 0
    status: str = "completed"
    chartData: Optional[List[Dict[str, Any]]] = None
    markers: Optional[List[Dict[str, Any]]] = None
    recipe: Optional[Dict[str, Any]] = None
    beanName: Optional[str] = ""
    notes: Optional[str] = ""

class HistoryUpdateNotesModel(BaseModel):
    beanName: Optional[str] = None
    notes: Optional[str] = None
    roastery: Optional[str] = None
    flavorTags: Optional[List[str]] = None

async def broadcast_msg(data: Dict[str, Any]):
    for ws in list(connected_websockets):
        try:
            await ws.send_json(data)
        except Exception:
            connected_websockets.discard(ws)

def on_machine_telemetry(telemetry_data):
    global latest_telemetry, main_loop
    try:
        for attr in ["temp_c", "current_temperature", "temperature", "temp"]:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) > 0:
                    latest_telemetry["temperature"] = int(round(float(v)))
                    break

        for attr in ["water_g", "water_volume", "pour_weight", "pour", "water"]:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) >= 0:
                    latest_telemetry["pour_weight"] = round(float(v), 1)
                    break

        for attr in ["coffee_g", "weight_g", "scale_weight", "yield_weight", "weight"]:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) >= 0:
                    latest_telemetry["yield_weight"] = round(float(v), 1)
                    break

        st_val = None
        for attr in ["status_name", "state_name", "status", "state"]:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None:
                    st_val = str(v)
                    break

        if st_val and st_val != "scale" and not st_val.startswith("ack_"):
            upper_st = st_val.upper()
            if "BYPASS" in upper_st:
                latest_telemetry["state"] = "BYPASS"
            else:
                latest_telemetry["state"] = upper_st

        for attr in ["current_step", "step_index", "step"]:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and int(v) > 0:
                    latest_telemetry["step_index"] = int(v)
                    break

        payload = {
            "type": "telemetry",
            **latest_telemetry
        }

        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_msg(payload), main_loop)
    except Exception as e:
        print(f"[WARN] Telemetry parse error: {e}")

async def _announce_ble_disconnected(log_msg: str) -> None:
    if active_radius_task and not active_radius_task.done():
        active_radius_task.cancel()
    await broadcast_msg({"type": "log", "msg": log_msg})
    await broadcast_msg({"type": "status", "ble_status": "DISCONNECTED"})

def mark_ble_disconnected(log_msg: str) -> None:
    global ble_connection_status
    if ble_connection_status != "CONNECTED":
        return
    ble_connection_status = "DISCONNECTED"
    print(log_msg)
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_announce_ble_disconnected(log_msg), main_loop)

def handle_ble_link_lost(client: XBloomClient) -> None:
    if client is ble_client:
        mark_ble_disconnected("[BLE] ⚠️ 머신과의 연결이 끊어졌습니다.")

async def connect_ble_task():
    global ble_client, ble_connection_status, discovered_device_address
    ble_connection_status = "SCANNING"
    print("\n[BLE] Scanning for nearby xBloom machines via Bluetooth...")
    await broadcast_msg({"type": "log", "msg": "[BLE] 주변 xBloom 기기 탐색 중..."})
    await broadcast_msg({"type": "status", "ble_status": "SCANNING"})

    target_address = None
    try:
        devices = await BleakScanner.discover(timeout=6.0)
        for d in devices:
            d_name = (d.name or "").lower()
            if "xbloom" in d_name or "bloom" in d_name:
                target_address = d.address
                print(f"[BLE] Device found: {d.name} ({d.address})")
                break

        if not target_address:
            raise RuntimeError("주변에서 xBloom 기기를 찾지 못했습니다. 전원을 확인해주세요.")

        discovered_device_address = target_address
        print(f"[BLE] Connecting to device ({target_address})...")

        new_client = XBloomClient(target_address)
        new_client.on_link_lost = lambda: handle_ble_link_lost(new_client)
        ble_client = new_client

        if hasattr(ble_client, "connect"):
            await ble_client.connect()

        if hasattr(ble_client, "open_session"):
            res = ble_client.open_session()
            if asyncio.iscoroutine(res):
                await res
            print("[BLE] open_session completed (device connection marked active)")

        if hasattr(ble_client, "add_telemetry_listener"):
            ble_client.add_telemetry_listener(on_machine_telemetry)
            print("[BLE] Real-time telemetry fanout listener registered")

        ble_connection_status = "CONNECTED"
        print(f"[BLE] xBloom machine connected and ready for control! ({d.name})")
        await broadcast_msg({"type": "log", "msg": f"[BLE] 머신 연결 성공! ({d.name})"})
        await broadcast_msg({"type": "status", "ble_status": "CONNECTED"})

    except Exception as e:
        ble_connection_status = "ERROR"
        err_msg = f"[BLE ERROR] {str(e)}"
        print(f"\n{err_msg}")
        await broadcast_msg({"type": "log", "msg": err_msg})
        await broadcast_msg({"type": "status", "ble_status": "ERROR"})

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cloud_client, main_loop
    main_loop = asyncio.get_running_loop()

    cloud_client = get_cloud_handler()
    if cloud_client:
        restore_cloud_session()
        print(f"[CLOUD] Cloud module loaded: {type(cloud_client).__name__}")

    ble_init_task = asyncio.create_task(connect_ble_task())
    schedule_daemon_task = asyncio.create_task(scheduled_brew_daemon_loop())
    yield
    if schedule_daemon_task and not schedule_daemon_task.done():
        schedule_daemon_task.cancel()
    if ble_init_task and not ble_init_task.done():
        ble_init_task.cancel()

app = FastAPI(title="xBloom bleUI Server", version=CURRENT_VERSION, lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"\n[422 VALIDATION ERROR] URL: {request.method} {request.url.path}")
    print(f"[422 DETAILS] {exc.errors()}")
    try:
        body = await request.body()
        print(f"[422 RAW BODY] {body.decode('utf-8', errors='replace')}\n")
    except Exception:
        pass
    err_msgs = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        err_msgs.append(f"{loc}: {msg}")
    detail_str = "; ".join(err_msgs) if err_msgs else "요청 데이터 유효성 검증 실패"
    return JSONResponse(status_code=422, content={"detail": detail_str, "errors": exc.errors()})

class ProtocolCompliantPour:
    def __init__(self, water: int, temp: int, wait: int, flow: float, pattern: str = "center",
                 agitation_before: bool = False, agitation_after: bool = False, rpm: int = 0,
                 radius: str = "L3", step_time: int = 0):
        self.water = int(water)
        self.ml = int(water)
        self.water_ml = int(water)
        self.water_g = int(water)
        self.weight_g = int(water)

        self.temp = int(temp)
        self.temp_c = int(temp)
        self.temperature = int(temp)
        self.temperature_c = int(temp)

        self.wait = int(wait)
        self.wait_s = int(wait)
        self.pause = int(wait)
        self.pause_s = int(wait)
        self.pause_time = int(wait)

        self.flow = float(flow)
        self.flow_rate = float(flow)
        self.flow_rate_ml_s = float(flow)
        self.flow_ml_s = float(flow)

        self.pattern = normalize_pattern(pattern)
        self.rpm = 0 if self.pattern == "center" else int(rpm or 80)
        self.agitation_before = bool(agitation_before)
        self.agitation_after = bool(agitation_after)
        self.agitation = bool(agitation_after or agitation_before)
        self.vibration = bool(agitation_after or agitation_before)
        self.isEnableVibrationBefore = bool(agitation_before)
        self.isEnableVibrationAfter = bool(agitation_after)
        self.radius = str(radius or "L3").upper()
        self.step_time = int(step_time or 0)

    def to_protocol_dict(self) -> dict:
        return {
            "ml": self.ml,
            "temp": self.temp_c,
            "pattern": self.pattern,
            "agitation": self.agitation_after,
            "agitation_before": self.agitation_before,
            "agitation_after": self.agitation_after,
            "pause": self.pause_s,
            "rpm": self.rpm,
            "flow": self.flow_ml_s,
            "radius": self.radius,
            "step_time": self.step_time,
        }

    def ble_omissions(self) -> list[str]:
        return []

    def to_dict(self):
        return {
            "ml": self.ml,
            "water": self.water,
            "water_ml": self.water_ml,
            "water_g": self.water_g,
            "weight_g": self.weight_g,
            "temp": self.temp,
            "temp_c": self.temp_c,
            "temperature": self.temperature,
            "wait": self.wait,
            "wait_s": self.wait_s,
            "pause": self.pause,
            "pause_s": self.pause_s,
            "pause_time": self.pause_time,
            "flow": self.flow,
            "flow_rate": self.flow_rate,
            "flow_rate_ml_s": self.flow_rate_ml_s,
            "flow_ml_s": self.flow_ml_s,
            "pattern": self.pattern,
            "rpm": self.rpm,
            "agitation": self.agitation_after,
            "agitation_before": self.agitation_before,
            "agitation_after": self.agitation_after,
            "isEnableVibrationBefore": self.isEnableVibrationBefore,
            "isEnableVibrationAfter": self.isEnableVibrationAfter,
            "vibration": self.vibration,
            "radius": self.radius,
            "step_time": self.step_time,
        }

    def __getitem__(self, item):
        return self.to_dict().get(item, False)

    def get(self, item, default=None):
        return self.to_dict().get(item, default)

class ProtocolCompliantRecipe:
    def __init__(self, name: str, dose: int, grind_size: int, grind_enabled: bool, grind_rpm: int, pours: list,
                 bypass_enabled: bool = False, bypass_volume: float = 0.0, bypass_temp: float = 85.0):
        self.name = name
        self.dose = int(dose)
        self.dose_g = int(dose)
        self.grind = int(grind_size) if grind_enabled else 0
        self.grind_size = int(grind_size) if grind_enabled else 0
        self.grind_enabled = bool(grind_enabled)
        self.enable_grind = bool(grind_enabled)
        self.rpm = int(grind_rpm) if grind_enabled else 0
        self.grind_rpm = int(grind_rpm) if grind_enabled else 0
        self.no_grind = not bool(grind_enabled) or int(self.grind) == 0
        self.pours = pours
        self.steps = pours

        self.bypass_enabled = bool(bypass_enabled) and float(bypass_volume or 0.0) > 0
        self.bypass_volume = float(bypass_volume or 0.0) if self.bypass_enabled else 0.0
        self.bypass_temp = float(bypass_temp or 85.0) if self.bypass_enabled else 85.0

        self.total_water = sum(getattr(p, "water", 0) for p in pours)
        self.total_water_g = self.total_water
        self.total_water_ml = self.total_water

        calc_ratio = (self.total_water / self.dose) if self.dose > 0 else 0.0
        self.effective_ratio = float(calc_ratio)
        self.ratio = float(calc_ratio)
        self.brew_ratio = float(calc_ratio)

    def __getattr__(self, item):
        if item == "no_grind":
            return not self.grind_enabled or int(self.grind) == 0
        if item in ["effective_ratio", "ratio", "brew_ratio"]:
            return float(self.total_water / self.dose) if self.dose > 0 else 15.0
        if item in ["total_water", "total_water_g", "grand_water", "grandWater"]:
            return float(self.total_water)
        if item in ["rpm", "grinder_rpm"]:
            return self.rpm
        if item in ["bypass_enabled", "isEnableBypassWater"]:
            return self.bypass_enabled
        if item in ["bypass_volume", "bypassVolume"]:
            return self.bypass_volume
        if item in ["bypass_temp", "bypassTemp"]:
            return self.bypass_temp
        return 0.0

    def validate(self):
        return True

    def ble_warnings(self) -> list[str]:
        out = []
        for i, p in enumerate(self.pours, start=1):
            if hasattr(p, "ble_omissions"):
                omitted = p.ble_omissions()
                if omitted:
                    out.append(f"푸어 #{i}: {', '.join(omitted)}은 머신 BLE 프로토콜 제약으로 생략됩니다 (클라우드 전송 시 동작).")
        return out

    def to_protocol_dict(self):
        d = {
            "name": self.name,
            "dose": self.dose,
            "dose_g": self.dose_g,
            "grind": self.grind,
            "grind_size": self.grind_size,
            "grind_enabled": self.grind_enabled,
            "enable_grind": self.enable_grind,
            "rpm": self.rpm,
            "grind_rpm": self.grind_rpm,
            "effective_ratio": self.effective_ratio,
            "ratio": self.ratio,
            "total_water": self.total_water,
            "pours": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.pours],
            "steps": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.steps]
        }
        if self.bypass_enabled and self.bypass_volume > 0:
            d["bypass_enabled"] = True
            d["bypass_volume"] = float(self.bypass_volume)
            d["bypass_temp"] = float(self.bypass_temp)
        else:
            d["bypass_enabled"] = False
            d["bypass_volume"] = 0.0
            d["bypass_temp"] = 85.0
        return d

    def __getitem__(self, item):
        return self.to_protocol_dict().get(item, 0.0)

    def get(self, item, default=None):
        return self.to_protocol_dict().get(item, default)

AGITATION_SECONDS = 8

def build_official_recipe_object(recipe_data: Any):
    if isinstance(recipe_data, dict):
        rec_name = recipe_data.get("name", "Custom Brew")
        rec_dose = int(recipe_data.get("dose", 15))
        rec_grind = int(recipe_data.get("grind_size", 45))
        rec_grind_on = bool(recipe_data.get("grind_enabled", True))
        rec_rpm = int(recipe_data.get("grind_rpm", 80))
        rec_bypass_on = bool(recipe_data.get("bypass_enabled", False)) and float(recipe_data.get("bypass_volume", 0.0) or 0.0) > 0
        rec_bypass_vol = float(recipe_data.get("bypass_volume", 0.0) or 0.0) if rec_bypass_on else 0.0
        rec_bypass_temp = float(recipe_data.get("bypass_temp", 85.0) or 85.0) if rec_bypass_on else 85.0
        raw_steps = recipe_data.get("steps") or recipe_data.get("pours") or []
    else:
        rec_name = getattr(recipe_data, "name", "Custom Brew")
        rec_dose = int(getattr(recipe_data, "dose", 15))
        rec_grind = int(getattr(recipe_data, "grind_size", 45))
        rec_grind_on = bool(getattr(recipe_data, "grind_enabled", True))
        rec_rpm = int(getattr(recipe_data, "grind_rpm", 80))
        rec_bypass_on = bool(getattr(recipe_data, "bypass_enabled", False)) and float(getattr(recipe_data, "bypass_volume", 0.0) or 0.0) > 0
        rec_bypass_vol = float(getattr(recipe_data, "bypass_volume", 0.0) or 0.0) if rec_bypass_on else 0.0
        rec_bypass_temp = float(getattr(recipe_data, "bypass_temp", 85.0) or 85.0) if rec_bypass_on else 85.0
        raw_steps = getattr(recipe_data, "steps", None) or getattr(recipe_data, "pours", None) or []

    rec_is_advanced = bool(getattr(recipe_data, "is_advanced", False) if hasattr(recipe_data, "is_advanced") else (recipe_data.get("is_advanced", False) if isinstance(recipe_data, dict) else False))
    rec_schema_v = int(getattr(recipe_data, "schema_version", 2 if rec_is_advanced else 1) if hasattr(recipe_data, "schema_version") else (recipe_data.get("schema_version", 2 if rec_is_advanced else 1) if isinstance(recipe_data, dict) else 1))
    rec_auto_grind = bool(getattr(recipe_data, "auto_grind", True) if hasattr(recipe_data, "auto_grind") else (recipe_data.get("auto_grind", True) if isinstance(recipe_data, dict) else True))

    rec_rpm = max(60, min(120, round(rec_rpm / 10) * 10))

    pours = []
    for step_index, s in enumerate(raw_steps):
        if hasattr(s, "water") and getattr(s, "water") is not None:
            s_water = getattr(s, "water")
        elif hasattr(s, "pour") and getattr(s, "pour") is not None:
            s_water = getattr(s, "pour")
        elif hasattr(s, "ml") and getattr(s, "ml") is not None:
            s_water = getattr(s, "ml")
        elif isinstance(s, dict):
            s_water = s.get("water") if s.get("water") is not None else (s.get("pour") if s.get("pour") is not None else s.get("ml", 50))
        else:
            s_water = 50
        s_temp = getattr(s, "temp", None) if hasattr(s, "temp") else s.get("temp", s.get("temperature", 93))
        s_wait = getattr(s, "wait", None) if hasattr(s, "wait") else s.get("wait", s.get("pause", 15))
        s_flow = getattr(s, "flow", None) if hasattr(s, "flow") else s.get("flow", s.get("flow_rate", 3.2))
        s_pattern = getattr(s, "pattern", None) if hasattr(s, "pattern") else s.get("pattern", "center")
        s_before = getattr(s, "agitation_before", None) if hasattr(s, "agitation_before") else s.get("agitation_before", False)
        s_after = getattr(s, "agitation_after", None) if hasattr(s, "agitation_after") else s.get("agitation_after", s.get("agitation", False))
        s_radius = getattr(s, "radius", None) if hasattr(s, "radius") else s.get("radius", "L3")
        s_step_time = getattr(s, "step_time", None) if hasattr(s, "step_time") else s.get("step_time", 0)

        pat = normalize_pattern(s_pattern)
        step_rpm = 0 if pat == "center" else max(60, min(120, rec_rpm))
        norm_radius = str(s_radius or "L3").upper()
        norm_step_time = int(s_step_time or 0)

        final_wait = int(s_wait or 0)
        if final_wait == 0 and norm_step_time > 0:
            fl_val = float(s_flow) if float(s_flow) > 0 else 3.2
            pour_dur = round(float(s_water) / fl_val)
            after_sec = AGITATION_SECONDS if s_after else 0
            next_step = raw_steps[step_index + 1] if step_index + 1 < len(raw_steps) else None
            next_before = getattr(next_step, "agitation_before", False) if hasattr(next_step, "agitation_before") else (next_step.get("agitation_before", False) if isinstance(next_step, dict) else False)
            next_before_sec = AGITATION_SECONDS if next_before else 0
            final_wait = max(0, norm_step_time - pour_dur - after_sec - next_before_sec)

        if StepClass:
            try:
                step_obj = StepClass(
                    ml=int(s_water),
                    temp_c=int(s_temp),
                    pattern=pat,
                    agitation=bool(s_after),
                    pause_s=final_wait,
                    rpm=step_rpm,
                    flow_ml_s=float(s_flow),
                    agitation_before=bool(s_before),
                    radius=norm_radius,
                    step_time=norm_step_time
                )
                for attr, val in [
                    ("water", int(s_water)),
                    ("water_ml", int(s_water)),
                    ("water_g", int(s_water)),
                    ("temp", int(s_temp)),
                    ("temperature", int(s_temp)),
                    ("temperature_c", int(s_temp)),
                    ("wait", final_wait),
                    ("wait_s", final_wait),
                    ("pause", final_wait),
                    ("flow", float(s_flow)),
                    ("flow_rate", float(s_flow)),
                    ("rpm", step_rpm),
                    ("agitation_after", bool(s_after)),
                    ("agitation_before", bool(s_before)),
                    ("isEnableVibrationBefore", bool(s_before)),
                    ("isEnableVibrationAfter", bool(s_after)),
                    ("vibration", bool(s_after or s_before)),
                    ("radius", norm_radius),
                    ("step_time", norm_step_time),
                ]:
                    try:
                        setattr(step_obj, attr, val)
                    except Exception:
                        pass
                pours.append(step_obj)
                continue
            except Exception:
                pass

        pours.append(ProtocolCompliantPour(
            water=int(s_water),
            temp=int(s_temp),
            wait=final_wait,
            flow=float(s_flow),
            pattern=pat,
            agitation_before=bool(s_before),
            agitation_after=bool(s_after),
            rpm=step_rpm,
            radius=norm_radius,
            step_time=norm_step_time
        ))

    effective_grind = rec_grind if rec_grind_on else 0
    total_w = sum(int(getattr(p, "water", None) or getattr(p, "ml", 0) or 0) for p in pours)
    calc_ratio = float(total_w / rec_dose) if rec_dose > 0 else 0.0

    norm_pours = pours
    is_no_grind = (not rec_grind_on) or (effective_grind == 0)

    if RecipeClass:
        try:
            rec_obj = RecipeClass(
                name=rec_name,
                dose_g=rec_dose,
                grind=effective_grind,
                pours=norm_pours,
                is_advanced=rec_is_advanced,
                schema_version=rec_schema_v,
                grind_rpm=rec_rpm,
                auto_grind=rec_auto_grind
            )
            for attr, val in [
                ("dose", rec_dose),
                ("dose_g", rec_dose),
                ("grind_size", effective_grind),
                ("grind_enabled", rec_grind_on),
                ("enable_grind", rec_grind_on),
                ("rpm", rec_rpm if rec_grind_on else 0),
                ("grind_rpm", rec_rpm if rec_grind_on else 0),
                ("no_grind", is_no_grind),
                ("effective_ratio", calc_ratio),
                ("ratio", calc_ratio),
                ("total_water", total_w),
                ("total_water_g", total_w),
                ("bypass_enabled", rec_bypass_on),
                ("bypass_volume", rec_bypass_vol),
                ("bypass_temp", rec_bypass_temp),
                ("is_advanced", rec_is_advanced),
                ("schema_version", rec_schema_v),
                ("auto_grind", rec_auto_grind),
            ]:
                try:
                    setattr(rec_obj, attr, val)
                except Exception:
                    pass
            return rec_obj
        except Exception:
            pass

    return ProtocolCompliantRecipe(
        name=rec_name,
        dose=rec_dose,
        grind_size=effective_grind,
        grind_enabled=rec_grind_on,
        grind_rpm=rec_rpm,
        pours=norm_pours,
        bypass_enabled=rec_bypass_on,
        bypass_volume=rec_bypass_vol,
        bypass_temp=rec_bypass_temp
    )

SLOT_KEY_MAP = { 1: "A", 2: "B", 3: "C" }

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        await websocket.send_json({
            "type": "status",
            "ble_status": ble_connection_status,
            "telemetry": latest_telemetry
        })
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg_data = json.loads(raw_text)
                if msg_data.get("action") == "abort" or msg_data.get("type") == "abort":
                    asyncio.create_task(stop_brew())
            except Exception:
                pass
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)

@app.get("/api/status")
async def get_status():
    is_conn = (ble_connection_status == "CONNECTED")
    return {
        "ble_connected": is_conn,
        "ble_status": ble_connection_status,
        "device_address": discovered_device_address,
        "telemetry": latest_telemetry
    }

@app.get("/api/settings")
async def get_settings():
    return server_config

@app.post("/api/settings")
async def update_settings(cfg_update: SettingsUpdateModel):
    global server_config
    if cfg_update.theme is not None:
        server_config["theme"] = cfg_update.theme
    if cfg_update.wallpaper is not None:
        server_config["wallpaper"] = cfg_update.wallpaper if cfg_update.wallpaper != "" else None
    if cfg_update.language is not None:
        server_config["language"] = str(cfg_update.language)
    if cfg_update.record_aborted_brews is not None:
        server_config["record_aborted_brews"] = bool(cfg_update.record_aborted_brews)
    if cfg_update.pour_marker_mode is not None:
        server_config["pour_marker_mode"] = str(cfg_update.pour_marker_mode)
    if cfg_update.chart_smoothing is not None:
        server_config["chart_smoothing"] = bool(cfg_update.chart_smoothing)
    if cfg_update.handdrip_interval_sync is not None:
        server_config["handdrip_interval_sync"] = bool(cfg_update.handdrip_interval_sync)
    if cfg_update.show_micron is not None:
        server_config["show_micron"] = bool(cfg_update.show_micron)
    if cfg_update.enable_advanced_recipe is not None:
        server_config["enable_advanced_recipe"] = bool(cfg_update.enable_advanced_recipe)
    if cfg_update.default_radius is not None:
        new_rad = str(cfg_update.default_radius).strip().upper()
        server_config["default_radius"] = new_rad
        if ble_client and ble_connection_status == "CONNECTED":
            try:
                rad_frame = build_set_pour_radius(new_rad)
                if hasattr(ble_client, "write_frame"):
                    res = ble_client.write_frame(rad_frame)
                    if asyncio.iscoroutine(res):
                        await res
                await broadcast_msg({
                    "type": "log",
                    "msg": f"[BLE] 🎯 머신 추출 반경 실시간 적용: {new_rad}"
                })
            except Exception as e:
                print(f"[WARN] Failed to apply live pour radius to machine: {e}")
    save_server_config(server_config)
    return {"status": "ok", "config": server_config}

def mask_api_key(key: Optional[str]) -> str:
    if not key or len(key) < 8:
        return ""
    return f"{key[:4]}...{key[-4:]}"

@app.get("/api/settings/ai")
async def get_ai_settings():
    provider = server_config.get("ai_provider", "gemini")
    gemini_key = server_config.get("ai_gemini_key", "")
    openai_key = server_config.get("ai_openai_key", "")
    gemini_model = server_config.get("ai_gemini_model", "gemini-3.5-flash-lite")
    openai_model = server_config.get("ai_openai_model", "gpt-4o")

    active_key = gemini_key if provider == "gemini" else openai_key
    active_model = gemini_model if provider == "gemini" else openai_model
    gem_ver = server_config.get("ai_gemini_verified", False)
    oai_ver = server_config.get("ai_openai_verified", False)
    is_active_verified = gem_ver if provider == "gemini" else oai_ver

    return {
        "status": "ok",
        "provider": provider,
        "has_gemini": bool(gemini_key and gemini_key.strip()),
        "has_openai": bool(openai_key and openai_key.strip()),
        "gemini_key_masked": mask_api_key(gemini_key) if (gem_ver and gemini_key) else "",
        "openai_key_masked": mask_api_key(openai_key) if (oai_ver and openai_key) else "",
        "gemini_model": gemini_model,
        "openai_model": openai_model,
        "model": active_model,
        "is_configured": bool(is_active_verified and active_key and active_key.strip()),
        "is_verified": bool(is_active_verified and active_key and active_key.strip()),
        "has_saved_key": bool(active_key and active_key.strip())
    }

@app.post("/api/settings/ai")
async def save_ai_settings(req: AISettingsUpdateModel):
    global server_config
    if req.provider is not None:
        server_config["ai_provider"] = req.provider.strip().lower()
    if req.gemini_api_key is not None:
        new_gem_key = req.gemini_api_key.strip()
        if new_gem_key != server_config.get("ai_gemini_key"):
            server_config["ai_gemini_key"] = new_gem_key
            server_config["ai_gemini_verified"] = False
    if req.openai_api_key is not None:
        new_oai_key = req.openai_api_key.strip()
        if new_oai_key != server_config.get("ai_openai_key"):
            server_config["ai_openai_key"] = new_oai_key
            server_config["ai_openai_verified"] = False
    if req.gemini_model is not None and req.gemini_model.strip():
        server_config["ai_gemini_model"] = req.gemini_model.strip()
    if req.openai_model is not None and req.openai_model.strip():
        server_config["ai_openai_model"] = req.openai_model.strip()
    if req.model is not None and req.model.strip():
        prov = req.provider.strip().lower() if req.provider else server_config.get("ai_provider", "gemini")
        if prov == "gemini":
            server_config["ai_gemini_model"] = req.model.strip()
        else:
            server_config["ai_openai_model"] = req.model.strip()

    save_server_config(server_config)
    return await get_ai_settings()

@app.post("/api/ai/test-connection")
async def test_ai_connection(req: AITestConnectionRequest):
    global server_config
    provider = req.provider.strip().lower()
    key = req.api_key.strip() if req.api_key else ""
    if key == "USING_SAVED" or not key:
        key = server_config.get("ai_gemini_key" if provider == "gemini" else "ai_openai_key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key is required for testing. Please enter a key.")

    target_model = req.model or server_config.get("ai_gemini_model" if provider == "gemini" else "ai_openai_model", "gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o")
    try:
        res = ai_service.dispatch_llm(provider, key, "You are a connectivity test ping. Reply with 'OK'.", "ping", model=target_model)
        server_config[f"ai_{provider}_verified"] = True
        save_server_config(server_config)
        return {"status": "ok", "message": f"Connection verified successfully! ({target_model})", "sample": res[:30], "model": target_model}
    except Exception as e:
        server_config[f"ai_{provider}_verified"] = False
        save_server_config(server_config)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/ai/extract-recipe")
async def extract_recipe_endpoint(req: AIExtractRecipeRequest):
    global server_config
    provider = (req.provider or server_config.get("ai_provider", "gemini")).strip().lower()
    key = req.api_key or (server_config.get("ai_gemini_key") if provider == "gemini" else server_config.get("ai_openai_key"))

    if not key:
        server_config[f"ai_{provider}_verified"] = False
        save_server_config(server_config)
        raise HTTPException(
            status_code=400, 
            detail=f"{'Google Gemini' if provider == 'gemini' else 'OpenAI ChatGPT'} API 키가 설정되지 않았습니다. 환경 설정(⚙️)에서 키를 입력하고 [연결 테스트]를 완료해주세요."
        )

    try:
        lang = req.lang or server_config.get("language", "ko")
        target_model = req.model or server_config.get("ai_gemini_model" if provider == "gemini" else "ai_openai_model", "gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o")
        result = ai_service.extract_recipe(provider, key, url=req.url, text=req.text, model=target_model, lang=lang, images=req.images)
        if not server_config.get(f"ai_{provider}_verified"):
            server_config[f"ai_{provider}_verified"] = True
            save_server_config(server_config)
        return result
    except Exception as e:
        err_str = str(e)
        if any(w in err_str.lower() for w in ["api_key_invalid", "api key not valid", "unauthorized"]):
            server_config[f"ai_{provider}_verified"] = False
            save_server_config(server_config)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=err_str)

@app.post("/api/ai/barista-chat")
async def barista_chat_endpoint(req: AIBaristaChatRequest):
    global server_config
    provider = (req.provider or server_config.get("ai_provider", "gemini")).strip().lower()
    key = req.api_key or (server_config.get("ai_gemini_key") if provider == "gemini" else server_config.get("ai_openai_key"))

    if not key:
        server_config[f"ai_{provider}_verified"] = False
        save_server_config(server_config)
        raise HTTPException(
            status_code=400, 
            detail=f"{'Google Gemini' if provider == 'gemini' else 'OpenAI ChatGPT'} API 키가 설정되지 않았습니다. 환경 설정(⚙️)에서 키를 입력하고 [연결 테스트]를 완료해주세요."
        )

    try:
        lang = req.lang or server_config.get("language", "ko")
        target_model = req.model or server_config.get("ai_gemini_model" if provider == "gemini" else "ai_openai_model", "gemini-3.5-flash-lite" if provider == "gemini" else "gpt-4o")
        result = ai_service.barista_chat_service(
            provider, key, 
            message=req.message, 
            history=req.history or [], 
            telemetry=req.telemetry,
            model=target_model,
            lang=lang,
            personality=req.personality or "balanced"
        )
        if not server_config.get(f"ai_{provider}_verified"):
            server_config[f"ai_{provider}_verified"] = True
            save_server_config(server_config)
        return result
    except Exception as e:
        err_str = str(e)
        if any(w in err_str.lower() for w in ["api_key_invalid", "api key not valid", "unauthorized"]):
            server_config[f"ai_{provider}_verified"] = False
            save_server_config(server_config)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=err_str)

def _history_record_time(record: Dict[str, Any]) -> float:
    id_match = re.search(r"(\d{11,})$", str(record.get("id") or ""))
    if id_match:
        return float(id_match.group(1))
    m = re.search(
        r"(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후|AM|PM)?\s*(\d{1,2}):(\d{2})",
        str(record.get("date") or ""),
    )
    if not m:
        return 0.0
    hour = int(m.group(4)) % (12 if m.group(3) else 24)
    if m.group(3) in ("오후", "PM"):
        hour += 12
    now = datetime.now()
    try:
        when = datetime(now.year, int(m.group(1)), int(m.group(2)), hour, int(m.group(5)))
        if when > now + timedelta(days=1):
            when = when.replace(year=now.year - 1)
    except ValueError:
        return 0.0
    return when.timestamp() * 1000

@app.get("/api/history")
async def get_history(limit: int = 100):
    records = sorted(load_brew_history(), key=_history_record_time, reverse=True)
    return {"records": records[:limit], "total": len(records)}

@app.post("/api/history")
async def add_history_record(record: HistoryItemModel):
    records = load_brew_history()
    rec_dict = record.model_dump() if hasattr(record, "model_dump") else record.dict()
    if not rec_dict.get("id"):
        rec_dict["id"] = f"hist_{int(time.time() * 1000)}"
    if not rec_dict.get("date"):
        rec_dict["date"] = time.strftime("%m. %d. %H:%M")

    records.insert(0, rec_dict)
    save_brew_history(records)
    print(f"[HISTORY] New brew record saved: {rec_dict['recipeName']} ({rec_dict.get('status', 'completed')}) - {rec_dict['totalYield']}g / {rec_dict['duration']}")
    return {"status": "saved", "record": rec_dict}

@app.put("/api/history/{record_id}")
async def update_history_notes(record_id: str, update_data: HistoryUpdateNotesModel):
    records = load_brew_history()
    target = None
    for r in records:
        if r.get("id") == record_id:
            target = r
            if update_data.beanName is not None:
                target["beanName"] = update_data.beanName
            if update_data.notes is not None:
                target["notes"] = update_data.notes
            if update_data.roastery is not None:
                target["roastery"] = update_data.roastery
            if update_data.flavorTags is not None:
                target["flavorTags"] = update_data.flavorTags
            break
    if not target:
        raise HTTPException(status_code=404, detail="해당 추출 기록을 찾을 수 없습니다.")
    save_brew_history(records)
    return {"status": "updated", "record": target}

@app.delete("/api/history/{record_id}")
async def delete_history_record(record_id: str):
    records = load_brew_history()
    new_records = [r for r in records if r.get("id") != record_id]
    if len(new_records) == len(records):
        raise HTTPException(status_code=404, detail="해당 추출 기록을 찾을 수 없습니다.")
    save_brew_history(new_records)
    print(f"[HISTORY] Brew record deleted: ID {record_id}")
    return {"status": "deleted", "id": record_id, "remaining": len(new_records)}

@app.delete("/api/history")
async def clear_all_history():
    save_brew_history([])
    print("[HISTORY] All brew records cleared successfully")
    return {"status": "cleared"}

@app.post("/api/ble/reconnect")
async def trigger_reconnect():
    global ble_connection_status
    if ble_connection_status == "SCANNING":
        return {"status": "already_scanning"}
    asyncio.create_task(connect_ble_task())
    return {"status": "reconnecting"}

@app.post("/api/ble/disconnect")
async def trigger_disconnect():
    global ble_client, ble_connection_status
    print("\n[BLE] Disconnection request received...")
    if ble_client:
        try:
            if hasattr(ble_client, "close_session"):
                res = ble_client.close_session()
                if asyncio.iscoroutine(res):
                    await res
            if hasattr(ble_client, "disconnect"):
                res = ble_client.disconnect()
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            print(f"[WARN] Exception during disconnect: {e}")

    ble_connection_status = "DISCONNECTED"
    print("[BLE] Machine disconnected successfully.")
    await broadcast_msg({"type": "log", "msg": "[BLE] 머신과의 연결이 해제되었습니다."})
    await broadcast_msg({"type": "status", "ble_status": "DISCONNECTED"})
    return {"status": "disconnected"}

@app.get("/api/recipes/local")
async def get_local_recipes():
    recipe_files = glob.glob(os.path.join(RECIPES_DIR, "*.yaml")) + glob.glob(os.path.join(RECIPES_DIR, "*.yml"))
    recipes_list = []

    for fpath in recipe_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue

                steps_data = []
                raw_steps = data.get("steps") or data.get("pours") or []
                def first_set(step, keys, default):
                    for key in keys:
                        if step.get(key) is not None:
                            return step[key]
                    return default

                for s in raw_steps:
                    steps_data.append({
                        "temp": int(first_set(s, ("temp", "temperature"), 92)),
                        "water": int(s.get("water") or s.get("pour") or s.get("ml", 50)),
                        "wait": int(first_set(s, ("wait", "pause_time", "pause"), 15)),
                        "flow": float(s.get("flow_rate") or s.get("flow", 3.2)),
                        "pattern": normalize_pattern(s.get("pattern", "center")),
                        "agitation_before": bool(s.get("agitation_before", False)),
                        "agitation_after": bool(s.get("agitation_after", s.get("agitation", False))),
                        "radius": str(s.get("radius", "L3")).upper(),
                        "step_time": int(s.get("step_time", 0))
                    })

                grind_val = int(data.get("grind_size") or data.get("grind", 45))
                grind_on = data.get("grind_enabled", data.get("enable_grind", grind_val > 0))
                grind_rpm = int(data.get("grind_rpm", data.get("rpm", 80)))
                grind_rpm = max(60, min(120, round(grind_rpm / 10) * 10))

                bp_on = bool(data.get("bypass_enabled", False)) and float(data.get("bypass_volume", 0.0) or 0.0) > 0
                bp_vol = float(data.get("bypass_volume", 0.0) or 0.0) if bp_on else 0.0
                bp_temp = float(data.get("bypass_temp", 85.0) or 85.0) if bp_on else 85.0
                is_adv = bool(data.get("is_advanced", False) or data.get("schema_version") == 2)

                mode_val = str(data.get("mode", "coffee"))
                tea_type_val = data.get("tea_type")

                total_water_ml = sum(s["water"] for s in steps_data)
                recipes_list.append({
                    "filename": os.path.basename(fpath),
                    "name": data.get("name", os.path.splitext(os.path.basename(fpath))[0]),
                    "dose": int(data.get("dose", 15)),
                    "grind_size": grind_val if grind_val > 0 else 45,
                    "grind_enabled": bool(grind_on),
                    "grind_rpm": grind_rpm,
                    "interval_sync": bool(data.get("interval_sync", False)),
                    "bypass_enabled": bp_on,
                    "bypass_volume": bp_vol,
                    "bypass_temp": bp_temp,
                    "is_advanced": is_adv,
                    "schema_version": int(data.get("schema_version", 2 if is_adv else 1)),
                    "auto_grind": bool(data.get("auto_grind", True)),
                    "mode": mode_val,
                    "tea_type": tea_type_val,
                    "total_water": total_water_ml,
                    "pour_count": len(steps_data),
                    "steps": steps_data
                })
        except Exception as e:
            print(f"[WARN] Failed to load recipe file ({fpath}): {e}")

    recipes_list.sort(key=lambda x: x.get("name", "").lower())
    return {"recipes": recipes_list}

@app.delete("/api/recipes/local/{filename}")
async def delete_local_recipe(filename: str):
    clean_name = os.path.basename(filename)
    if clean_name != filename or not filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="유효하지 않은 레시피 파일명입니다.")

    file_path = os.path.join(RECIPES_DIR, clean_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="해당 레시피 파일을 찾을 수 없습니다.")

    try:
        os.remove(file_path)
        print(f"[RECIPE] Deleted server recipe: {clean_name}")
        return {"status": "deleted", "filename": clean_name}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {str(e)}")

@app.post("/api/recipes/save")
async def save_recipe_to_server(recipe_data: RecipeModel):
    try:
        safe_name = re.sub(r'[\\/*?:"<>|]', "", recipe_data.name).strip()
        if not safe_name:
            safe_name = "custom_recipe"

        filename = f"{safe_name}.yaml"
        file_path = os.path.join(RECIPES_DIR, filename)

        is_tea_recipe = (getattr(recipe_data, "mode", "coffee") == "tea")
        yaml_content = {
            "name": recipe_data.name,
            "dose": int(recipe_data.dose),
            "grind_size": 0 if is_tea_recipe else int(recipe_data.grind_size),
            "grind_enabled": False if is_tea_recipe else bool(recipe_data.grind_enabled),
            "grind_rpm": int(recipe_data.grind_rpm),
            "bypass_enabled": False if is_tea_recipe else bool(recipe_data.bypass_enabled),
            "bypass_volume": 0.0 if is_tea_recipe else float(recipe_data.bypass_volume),
            "bypass_temp": float(recipe_data.bypass_temp),
            "is_advanced": bool(recipe_data.is_advanced),
            "schema_version": 2 if recipe_data.is_advanced else 1,
            "auto_grind": bool(recipe_data.auto_grind),
            "mode": recipe_data.mode or "coffee",
            "steps": [
                {
                    "temp": int(s.temp),
                    "pour": int(s.water),
                    "wait": int(s.wait),
                    "flow_rate": float(s.flow),
                    "pattern": normalize_pattern(s.pattern),
                    "agitation_before": bool(s.agitation_before),
                    "agitation_after": bool(s.agitation_after),
                    "radius": str(s.radius or "L3").upper(),
                    "step_time": int(s.step_time or 0)
                }
                for s in recipe_data.steps
            ]
        }
        if is_tea_recipe and recipe_data.tea_type:
            yaml_content["tea_type"] = recipe_data.tea_type

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_content, f, allow_unicode=True, sort_keys=False)

        print(f"[RECIPE] Saved recipe to server: {file_path}")
        return {"status": "saved", "filename": filename, "name": recipe_data.name}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"서버 저장 실패: {str(e)}")

@app.post("/api/machine/slot/{slot_id}")
async def write_slot(slot_id: int, recipe_data: RecipeModel):
    global ble_client
    if not (1 <= slot_id <= 3):
        raise HTTPException(status_code=400, detail="슬롯 번호는 1~3번만 지원합니다.")
    if getattr(recipe_data, "is_advanced", False):
        raise HTTPException(
            status_code=400,
            detail="고급 레시피는 동적 반경 및 실시간 앱 오케스트레이션 전용으로 머신 하드웨어 슬롯 저장을 지원하지 않습니다."
        )
    if not ble_client or ble_connection_status != "CONNECTED":
        raise HTTPException(status_code=503, detail="머신이 연결되어 있지 않습니다.")

    async with ble_lock:
        try:
            print(f"[SLOT] Hardware slot update: Slot {SLOT_KEY_MAP[slot_id]} (#{slot_id}) -> '{recipe_data.name}'")
            await ble_client.save_slot(build_official_recipe_object(recipe_data), slot_id - 1)
        except Exception as e:
            print(f"[WARN] save_slot BLE transfer error: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"슬롯 저장 실패: {str(e)}")

    return {"status": "saved", "slot": slot_id, "key": SLOT_KEY_MAP[slot_id], "name": recipe_data.name}

async def monitor_grind_and_return_arm(client):
    from xbloom_ble.client import CHAR_COMMAND
    from xbloom_ble.protocol import build_grinder_exit
    print("[BREW] ⏳ 원두 분쇄 모니터링 시작... (출수 감지 시 드리퍼 암 중앙 복귀)")
    for _ in range(60):
        await asyncio.sleep(1.0)
        st = latest_telemetry.get("state", "").upper()
        if st in ("BREWING", "POURING", "READY"):
            print(f"[BREW] 🎯 출수 단계 진입 감지 ({st})! 드리퍼 크래들 암을 샤워헤드 아래(중앙)로 복귀시킵니다.")
            if hasattr(client, "_client") and client._client:
                try:
                    await client._client.write_gatt_char(CHAR_COMMAND, build_grinder_exit(), response=False)
                except Exception as e:
                    print(f"[WARN] Grinder exit frame send failed: {e}")
            break
        elif st in ("IDLE", "STANDBY", "CANCELLED", "ERROR"):
            break

active_radius_task: Optional[asyncio.Task] = None
app_radius_active = False

def _default_radius() -> str:
    return str(server_config.get("default_radius") or "L3").strip().upper()

async def _restore_default_radius(client) -> None:
    global app_radius_active
    if not app_radius_active:
        return
    app_radius_active = False
    try:
        await client.write_frame(build_set_pour_radius(_default_radius()))
    except Exception as e:
        print(f"[WARN] Radius restore failed: {e}")

async def monitor_and_apply_dynamic_radius(client, steps: List[StepModel]):
    from xbloom_ble.client import CHAR_COMMAND
    from xbloom_ble.protocol import build_set_pour_radius, build_grinder_exit

    if not steps or len(steps) == 0:
        return

    print(f"[RADIUS CONTROLLER] 🚀 실시간 가변 반경 오케스트레이터 시작 (총 {len(steps)}단계)")

    cum_targets = []
    running_tot = 0
    for s in steps:
        w = int(getattr(s, "water", None) or getattr(s, "pour", 0) or 50)
        running_tot += w
        cum_targets.append(running_tot)

    for _ in range(240):
        st = latest_telemetry.get("state", "").upper()
        if st in ("BREWING", "POURING"):
            break
        elif st in ("CANCELLED", "ERROR", "IDLE"):
            await _restore_default_radius(client)
            return
        await asyncio.sleep(0.5)

    print(f"[RADIUS CONTROLLER] 🚀 실물 출수 감지! 실시간 단계별 가변 반경 추적 시작")

    current_applied_step = 1

    while True:
        await asyncio.sleep(0.3)
        st = latest_telemetry.get("state", "").upper()
        cur_water = float(latest_telemetry.get("pour_weight", 0.0) or 0.0)

        total_target_water = float(cum_targets[-1]) if cum_targets else 200.0
        is_completed = st in ("READY", "COMPLETE", "CANCELLED", "ERROR") or (cur_water >= total_target_water * 0.9 and st in ("IDLE", "STANDBY"))
        if is_completed:
            print(f"[RADIUS CONTROLLER] 🏁 추출 종료 감지 ({st}, 총 출수: {cur_water:.1f}g/{total_target_water:.1f}g). 크래들 암 중앙 원점 복귀.")
            if hasattr(client, "_client") and client._client:
                try:
                    await client._client.write_gatt_char(CHAR_COMMAND, build_grinder_exit(), response=False)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            await _restore_default_radius(client)
            for _ in range(600):
                await asyncio.sleep(1.0)
                if latest_telemetry.get("state", "").upper() in ("IDLE", "STANDBY"):
                    try:
                        await client.write_frame(build_set_pour_radius(_default_radius()))
                    except Exception as e:
                        print(f"[WARN] Radius restore failed: {e}")
                    break
            break

        rep_step = int(latest_telemetry.get("step_index", 0) or 0)

        target_step = 1
        for idx, target_w in enumerate(cum_targets, start=1):
            if cur_water >= (target_w - 2.0) and idx < len(steps):
                target_step = idx + 1
            else:
                break

        if rep_step > target_step:
            target_step = min(rep_step, len(steps))

        if target_step > current_applied_step and target_step <= len(steps):
            step_info = steps[target_step - 1]
            target_radius = str(getattr(step_info, "radius", "L3") or "L3").upper()
            print(f"[RADIUS CONTROLLER] 🎯 {target_step}차 푸어 전환 감지 (누적 출수: {cur_water:.1f}g) ➔ 반경 '{target_radius}' 이동")
            await broadcast_msg({
                "type": "log",
                "msg": f"[RADIUS] 🎯 {target_step}차 푸어 반경 '{target_radius}' 적용"
            })
            if hasattr(client, "_client") and client._client:
                try:
                    f = build_set_pour_radius(target_radius)
                    await client._client.write_gatt_char(CHAR_COMMAND, f, response=False)
                except Exception as e:
                    print(f"[WARN] Radius switch frame error: {e}")
            current_applied_step = target_step

@app.post("/api/brew/start")
async def start_brew(recipe_data: RecipeModel):
    global ble_client, ble_connection_status, latest_telemetry, v2_orchestrator, active_radius_task, app_radius_active

    if not ble_client or ble_connection_status != "CONNECTED":
        raise HTTPException(status_code=503, detail="머신이 BLE로 연결되어 있지 않습니다.")

    initial_temp = recipe_data.steps[0].temp if recipe_data.steps else 93
    latest_telemetry["pour_weight"] = 0.0
    latest_telemetry["yield_weight"] = 0.0
    latest_telemetry["temperature"] = int(round(float(initial_temp)))
    latest_telemetry["state"] = "ARMING"
    latest_telemetry["step_index"] = 1
    latest_telemetry["elapsed_time"] = 0

    recipe_obj = build_official_recipe_object(recipe_data)
    from xbloom_ble.protocol import build_load_frames
    proto_dict = recipe_obj.to_protocol_dict()
    load_frames = build_load_frames(proto_dict)

    dbg_pours_cmd = hex(load_frames[3][3])
    dbg_grind_byte = hex(load_frames[3][-4])
    dbg_msg = f"[BREW DEBUG] 레시피: {recipe_data.name} | Dose: {recipe_data.dose}g | grind_size: {recipe_data.grind_size} | grind_enabled: {recipe_data.grind_enabled} | is_adv: {getattr(recipe_data, 'is_advanced', False)} | pours_cmd: {dbg_pours_cmd} | grind_byte: {dbg_grind_byte} | steps: {len(recipe_data.steps)}"
    print(f"\n=======================================================")
    print(dbg_msg)
    for idx, fr in enumerate(load_frames):
        print(f"  [BLE FRAME {idx}] CMD 0x{fr[3]:02x} ({len(fr)}B): {fr.hex()}")
    print(f"=======================================================\n")
    await broadcast_msg({"type": "log", "msg": dbg_msg})

    if hasattr(recipe_obj, "ble_warnings"):
        warnings = recipe_obj.ble_warnings()
        for w in warnings:
            print(f"[BREW NOTICE] {w}")
            await broadcast_msg({"type": "log", "msg": f"[안내] {w}"})

    rec_bp_vol = float(getattr(recipe_obj, "bypass_volume", 0.0) or 0.0)
    rec_bp_temp = float(getattr(recipe_obj, "bypass_temp", 85.0) or 85.0)
    rec_bp_on = bool(getattr(recipe_obj, "bypass_enabled", False)) and rec_bp_vol > 0
    if rec_bp_on and rec_bp_vol > 0:
        bp_msg = f"[BREW] 🚀 바이패스(Bypass) 활성화: 본 추출 완료 후 드리퍼 자동 이동 & {rec_bp_vol}ml ({rec_bp_temp}℃) 가수 진행"
        print(bp_msg)
        await broadcast_msg({"type": "log", "msg": bp_msg})

    is_adv_recipe = bool(getattr(recipe_data, "is_advanced", False))
    default_radius = _default_radius()
    has_custom_radius = any(str(s.radius or "L3").upper() != default_radius for s in (recipe_data.steps or []))
    use_app_radius = bool(is_adv_recipe and has_custom_radius and recipe_data.steps)

    async with ble_lock:
        try:
            if use_app_radius:
                first_radius = str(recipe_data.steps[0].radius or "L3").upper()
                await ble_client.write_frame(build_set_pour_radius(first_radius))
                app_radius_active = True
                await broadcast_msg({"type": "log", "msg": f"[RADIUS] 🎯 1차 푸어 반경 '{first_radius}' 적용"})
                await asyncio.sleep(0.3)

            grind_label = f"분쇄도 {recipe_obj.grind}" if recipe_obj.grind > 0 else "분쇄 미사용(사전 분쇄)"
            print(f"[BREW] Loading recipe to machine: {recipe_data.name} ({grind_label})")
            load_res = None
            if hasattr(ble_client, "load_recipe"):
                res = ble_client.load_recipe(recipe_obj)
                if asyncio.iscoroutine(res):
                    load_res = await res
                else:
                    load_res = res
            load_state_name = getattr(load_res, "state_name", "armed") if load_res else "unknown"
            load_log = f"[BREW] ✅ 레시피 로드 완료 (머신 상태: {load_state_name}) -> Commit & Start 진행"
            print(load_log)
            await broadcast_msg({"type": "log", "msg": load_log})

            start_event = None
            if hasattr(ble_client, "start"):
                res = ble_client.start()
                if asyncio.iscoroutine(res):
                    res = await res
                start_event = res
                st_name = getattr(start_event, "state_name", "started") if start_event else "started"
                start_log = f"[BREW] 🚀 머신 시동(Start) 완료 -> 응답 상태: {st_name}"
                print(start_log)
                await broadcast_msg({"type": "log", "msg": start_log})

                if res and hasattr(res, "state_name") and res.state_name in ("no_beans", "no_water"):
                    what = "원두가" if res.state_name == "no_beans" else "물이"
                    err_msg = f"[BREW] 머신 거부: {what} 부족합니다. 추출이 취소되었습니다."
                    await broadcast_msg({"type": "log", "msg": err_msg})
                    if hasattr(ble_client, "cancel_brew"):
                        res_c = ble_client.cancel_brew()
                        if asyncio.iscoroutine(res_c):
                            await res_c
                    latest_telemetry["state"] = "CANCELLED"
                    raise RuntimeError(err_msg)
            elif hasattr(ble_client, "brew"):
                res = ble_client.brew(recipe_obj)
                if asyncio.iscoroutine(res):
                    res = await res
                start_event = res

            print(f"[BREW] Hardware session active for '{recipe_data.name}'")

            has_grind_phase = bool(recipe_obj.grind > 0 and recipe_obj.grind_enabled)
            latest_telemetry["state"] = "STARTING" if has_grind_phase else "BREWING"

            if use_app_radius:
                if active_radius_task and not active_radius_task.done():
                    active_radius_task.cancel()
                active_radius_task = asyncio.create_task(monitor_and_apply_dynamic_radius(ble_client, recipe_data.steps))
                print(f"[BREW] 고급 가변 반경 오케스트레이터 기동 (커스텀 반경 감지)")
            else:
                if active_radius_task and not active_radius_task.done():
                    active_radius_task.cancel()
                print(f"[BREW] 온디바이스 순정 시퀀서 단독 제어 (가변 반경 간섭 없음)")

            await broadcast_msg({"type": "telemetry", **latest_telemetry})
        except Exception as e:
            traceback.print_exc()
            latest_telemetry["state"] = "ERROR"
            await broadcast_msg({"type": "log", "msg": f"[BREW ERROR] {str(e)}"})
            await _restore_default_radius(ble_client)
            raise HTTPException(status_code=500, detail=f"추출 실패: {str(e)}")

    return {"status": "started", "recipe": recipe_data.name, "grind_enabled": bool(recipe_obj.grind > 0)}

@app.post("/api/brew/stop")
async def stop_brew():
    global ble_client, v2_orchestrator, active_radius_task
    print("[BREW] 🛑 비상 정지(Emergency Stop) 요청 수신")

    if active_radius_task and not active_radius_task.done():
        try:
            active_radius_task.cancel()
            print("[BREW] 🛑 가변 반경 오케스트레이터 태스크 취소 완료")
        except Exception as te:
            print(f"[WARN] Cancel radius task error: {te}")

    if ble_client and hasattr(ble_client, "_client") and ble_client._client:
        from xbloom_ble.client import CHAR_COMMAND
        from xbloom_ble.protocol import (
            build_cancel,
            build_grinder_stop,
            build_grinder_exit,
            build_water_stop,
        )
        try:
            await ble_client._client.write_gatt_char(CHAR_COMMAND, build_cancel(), response=False)
            await ble_client._client.write_gatt_char(CHAR_COMMAND, build_water_stop(), response=False)
            await ble_client._client.write_gatt_char(CHAR_COMMAND, build_grinder_stop(), response=False)
            await ble_client._client.write_gatt_char(CHAR_COMMAND, build_grinder_exit(), response=False)
            await _restore_default_radius(ble_client)
            print("[BREW] 🛑 하드웨어 강제 정지 패킷 즉시 전송 완료")
        except Exception as he:
            print(f"[WARN] Hardware emergency stop exception: {he}")

    if ble_client and hasattr(ble_client, "cancel_brew"):
        try:
            res = ble_client.cancel_brew()
            if asyncio.iscoroutine(res):
                await res
        except Exception as ce:
            print(f"[WARN] cancel_brew exception: {ce}")
    elif ble_client and hasattr(ble_client, "stop"):
        try:
            res = ble_client.stop()
            if asyncio.iscoroutine(res):
                await res
        except Exception as se:
            print(f"[WARN] stop exception: {se}")

    latest_telemetry["state"] = "CANCELLED"
    await broadcast_msg({"type": "telemetry", **latest_telemetry})
    await broadcast_msg({"type": "log", "msg": "[BREW] 🛑 머신 추출 긴급 중단 및 원점 복귀 완료"})
    return {"status": "stopped"}

@app.post("/api/v2/brew/start")
async def api_v2_brew_start(recipe_data: RecipeModel):
    return await start_brew(recipe_data)

@app.post("/api/v2/brew/abort")
async def api_v2_brew_abort():
    return await stop_brew()

@app.post("/api/v2/brew/pause")
async def api_v2_brew_pause():
    global v2_orchestrator
    if not v2_orchestrator or not v2_orchestrator.is_running:
        return {"status": "not_running"}
    await v2_orchestrator.pause()
    return {"status": "paused"}

@app.post("/api/v2/brew/resume")
async def api_v2_brew_resume():
    global v2_orchestrator
    if not v2_orchestrator or not v2_orchestrator.is_running:
        return {"status": "not_running"}
    await v2_orchestrator.resume()
    return {"status": "resumed"}

@app.get("/api/v2/brew/status")
async def api_v2_brew_status():
    global v2_orchestrator
    if not v2_orchestrator:
        return {"is_running": False, "state": "IDLE"}
    prog = v2_orchestrator.get_progress().to_dict()
    prog["is_running"] = v2_orchestrator.is_running
    return prog

@app.post("/api/machine/radius/{level}")
async def set_machine_radius(level: str):
    global ble_client, ble_connection_status
    if not ble_client or ble_connection_status != "CONNECTED":
        raise HTTPException(status_code=503, detail="머신이 연결되어 있지 않습니다.")
    from xbloom_ble.protocol import build_set_pour_radius
    from xbloom_ble.client import CHAR_COMMAND
    frame = build_set_pour_radius(level)
    print(f"[RADIUS] 🎯 Setting pour radius to '{level}' (Frame: {frame.hex()})")
    await broadcast_msg({"type": "log", "msg": f"[RADIUS] 🎯 반경 설정: {level}"})
    if hasattr(ble_client, "_client") and ble_client._client:
        await ble_client._client.write_gatt_char(CHAR_COMMAND, frame, response=False)
        return {"status": "ok", "level": level, "frame": frame.hex()}
    raise HTTPException(status_code=500, detail="BLE 클라이언트 에러")

@app.post("/api/cloud/login")
async def cloud_login(creds: CloudLoginModel):
    global cloud_client, server_config
    if not cloud_module:
        raise HTTPException(status_code=500, detail="xbloom_ble.cloud 모듈이 로드되지 않았습니다.")

    login_func = None
    if cloud_client and hasattr(cloud_client, "login"):
        login_func = getattr(cloud_client, "login")
    elif hasattr(cloud_module, "login"):
        login_func = getattr(cloud_module, "login")
    else:
        for attr in [a for a in dir(cloud_module) if not a.startswith("_")]:
            obj = getattr(cloud_module, attr)
            if hasattr(obj, "login"):
                login_func = getattr(obj, "login")
                cloud_client = obj
                break

    if not login_func:
        attrs = [a for a in dir(cloud_module) if not a.startswith("_")]
        raise HTTPException(status_code=500, detail=f"cloud 모듈에 login 함수를 찾을 수 없습니다. (속성: {attrs})")

    try:
        res = login_func(creds.email, creds.password)
        token = await res if asyncio.iscoroutine(res) else res

        token_str = str(token)
        if isinstance(token, dict):
            token_str = str(token.get("token") or token.get("access_token") or token)

        server_config["cloud_user"] = {"email": creds.email, "token": token_str}
        save_server_config(server_config)
        restore_cloud_session()

        print(f"[CLOUD] Login successful: {creds.email}")
        return {"success": True, "token": token_str, "email": creds.email}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=f"로그인 실패: {str(e)}")

@app.post("/api/cloud/logout")
async def cloud_logout():
    global server_config
    server_config["cloud_user"] = None
    save_server_config(server_config)
    return {"status": "logged_out"}

@app.post("/api/cloud/upload")
async def cloud_upload(recipe_data: RecipeModel):
    global cloud_client
    if not cloud_module:
        raise HTTPException(status_code=500, detail="cloud 모듈이 로드되지 않았습니다.")

    if not server_config.get("cloud_user") or not server_config["cloud_user"].get("token"):
        raise HTTPException(status_code=401, detail="클라우드 로그인이 필요합니다. 설정 메뉴에서 먼저 로그인해주세요.")

    restore_cloud_session()

    candidate_names = ["add_recipe", "upload_recipe", "create_recipe", "save_recipe", "upload", "publish_recipe"]
    upload_func = None

    target_obj = cloud_client if cloud_client else cloud_module
    for cname in candidate_names:
        if hasattr(target_obj, cname):
            upload_func = getattr(target_obj, cname)
            break

    if not upload_func:
        available = [a for a in dir(target_obj) if not a.startswith("_")]
        raise HTTPException(status_code=500, detail=f"업로드 메서드를 찾지 못했습니다. 속성 목록: {available}")

    recipe_obj = build_official_recipe_object(recipe_data)

    try:
        res = upload_func(recipe_obj)
        resp_data = await res if asyncio.iscoroutine(res) else res
        print(f"[CLOUD] Recipe upload raw response: {resp_data}")

        table_id = None
        share_url = None

        if isinstance(resp_data, dict):
            table_id = resp_data.get("tableId") or (resp_data.get("recipeVo") or {}).get("tableId")
            share_url = resp_data.get("shareRecipeLink") or (resp_data.get("recipeVo") or {}).get("shareRecipeLink")
        elif isinstance(resp_data, (int, str)):
            table_id = resp_data

        if not share_url and target_obj:
            list_func = getattr(target_obj, "recipe_items", None) or getattr(target_obj, "list_recipes", None)
            if list_func:
                for _ in range(2):
                    try:
                        items_res = list_func()
                        if asyncio.iscoroutine(items_res):
                            items_res = await items_res
                        items = items_res if isinstance(items_res, list) else (items_res.get("list", []) if isinstance(items_res, dict) else [])
                        for item in items:
                            if table_id is not None and str(item.get("tableId")) == str(table_id):
                                share_url = item.get("shareRecipeLink")
                                break
                            elif not table_id and item.get("theName") == recipe_data.name:
                                share_url = item.get("shareRecipeLink")
                                table_id = item.get("tableId")
                                break
                        if share_url:
                            break
                        await asyncio.sleep(0.4)
                    except Exception as fe:
                        print(f"[WARN] Warning during recipe share URL query: {fe}")
                        break

        print(f"[CLOUD] Recipe upload complete: ID = {table_id or resp_data}, ShareURL = {share_url}")
        return {
            "success": True,
            "recipe_id": str(table_id or resp_data or "OK"),
            "share_url": share_url
        }
    except Exception as e:
        print("[WARN] Recipe upload exception occurred:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"업로드 실패 원인: {str(e)}")

def extract_share_id(url_or_id: str) -> str:
    s = url_or_id.strip()
    if "id=" in s:
        parsed = urllib.parse.urlparse(s)
        qs = urllib.parse.parse_qs(parsed.query)
        if "id" in qs and len(qs["id"]) > 0:
            return qs["id"][0]
    return urllib.parse.unquote(s)

def fetch_xbloom_shared_recipe(url_or_id: str) -> Dict[str, Any]:
    share_id = extract_share_id(url_or_id)
    if not share_id:
        raise ValueError("유효한 xBloom 공유 ID 또는 URL이 아닙니다.")

    api_url = "https://client-api.xbloom.com/RecipeDetail.html"
    payload = {
        "tableIdOfRSA": share_id,
        "interfaceVersion": 19700101,
        "skey": "testskey"
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"xBloom 클라우드 서버 통신 오류: {str(e)}")

    if data.get("result") != "success" or not data.get("recipeVo"):
        err_info = data.get("info") or "레시피를 찾을 수 없습니다."
        raise ValueError(f"클라우드 레시피 조회 실패: {err_info}")

    vo = data["recipeVo"]
    raw_pours = vo.get("pourList", [])

    sorted_pours = sorted(raw_pours, key=lambda p: p.get("tableId", 0))

    steps = []
    for p in sorted_pours:
        pat_code = p.get("pattern", 1)
        if pat_code == 2:
            pattern = "spiral"
        elif pat_code == 3:
            pattern = "ring"
        else:
            pattern = "center"

        raw_temp = p.get("temperature", 93)
        try:
            temp_val = int(round(float(raw_temp)))
        except Exception:
            temp_val = 93

        raw_vol = p.get("volume", 50)
        try:
            water_val = int(round(float(raw_vol)))
        except Exception:
            water_val = 50

        raw_wait = p.get("pausing", 15)
        try:
            wait_val = int(round(float(raw_wait)))
        except Exception:
            wait_val = 15

        raw_flow = p.get("flowRate", 3.0)
        try:
            flow_val = round(float(raw_flow), 1)
        except Exception:
            flow_val = 3.0

        vib_before = (p.get("isEnableVibrationBefore") == 1)
        vib_after = (p.get("isEnableVibrationAfter") == 1)

        steps.append({
            "temp": temp_val,
            "water": water_val,
            "wait": wait_val,
            "flow": flow_val,
            "pattern": pattern,
            "agitation_before": vib_before,
            "agitation_after": vib_after
        })

    try:
        dose_val = int(round(float(vo.get("dose", 15))))
    except Exception:
        dose_val = 15

    try:
        grind_val = int(round(float(vo.get("grinderSize", 45))))
    except Exception:
        grind_val = 45

    grind_enabled = (vo.get("isSetGrinderSize") == 1)

    raw_rpm = vo.get("rpm", 80)
    try:
        rpm_val = int(raw_rpm)
        if rpm_val not in [60, 70, 80, 90, 100, 110, 120]:
            rpm_val = 80
    except Exception:
        rpm_val = 80

    return {
        "name": vo.get("theName") or "Shared Brew",
        "dose": dose_val,
        "grind_size": grind_val,
        "grind_enabled": grind_enabled,
        "grind_rpm": rpm_val,
        "interval_sync": False,
        "steps": steps,
        "share_member_name": data.get("shareMemberName") or "",
        "share_member_head": data.get("shareMemberHead") or "",
        "share_recipe_link": vo.get("shareRecipeLink") or url_or_id
    }

@app.post("/api/cloud/fetch-shared-recipe")
async def api_fetch_shared_recipe(req: FetchSharedRecipeRequest):
    try:
        recipe_data = fetch_xbloom_shared_recipe(req.url)
        print(f"[CLOUD SHARE] Successfully parsed shared recipe: '{recipe_data['name']}' (Author: {recipe_data.get('share_member_name')})")
        return {"success": True, "recipe": recipe_data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"공유 레시피 가져오기 실패: {str(e)}")

_update_cache: Dict[str, Any] = {
    "last_check": 0,
    "data": None
}

def parse_version_tuple(v_str: str) -> tuple:
    nums = re.findall(r'\d+', str(v_str or ""))
    return tuple(map(int, nums)) if nums else (0, 0, 0)

def fetch_latest_release(force: bool = False) -> Dict[str, Any]:
    global _update_cache
    now = time.time()
    if not force and _update_cache["data"] and (now - _update_cache["last_check"] < 43200):
        return _update_cache["data"]

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"xBloom-bleUI-Updater/{CURRENT_VERSION}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=3.5) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                tag = data.get("tag_name", "").strip()
                remote_ver = tag.lstrip("vV")
                remote_tuple = parse_version_tuple(remote_ver)
                local_tuple = parse_version_tuple(CURRENT_VERSION)

                is_newer = remote_tuple > local_tuple

                result = {
                    "current_version": CURRENT_VERSION,
                    "latest_version": remote_ver,
                    "tag_name": tag,
                    "update_available": is_newer,
                    "release_name": data.get("name") or f"xBloom bleUI {tag}",
                    "release_notes": data.get("body") or "",
                    "published_at": data.get("published_at") or "",
                    "html_url": data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases",
                    "zip_url": data.get("zipball_url") or f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.zip",
                    "checked_at": int(now)
                }
                _update_cache["last_check"] = now
                _update_cache["data"] = result
                return result
    except Exception as e:
        return {
            "current_version": CURRENT_VERSION,
            "latest_version": CURRENT_VERSION,
            "update_available": False,
            "error": str(e),
            "checked_at": int(now)
        }
    return {
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "update_available": False,
        "checked_at": int(now)
    }

def apply_update_from_zip(zip_url: str) -> Dict[str, Any]:
    tmp_dir = os.path.join(BASE_DIR, ".update_tmp")
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)

    zip_path = os.path.join(tmp_dir, "release.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        req = urllib.request.Request(
            zip_url,
            headers={"User-Agent": f"xBloom-bleUI-Updater/{CURRENT_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=45.0) as resp, open(zip_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        extracted_items = os.listdir(extract_dir)
        source_root = extract_dir
        if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
            source_root = os.path.join(extract_dir, extracted_items[0])

        PROTECTED_ITEMS = {
            "recipes", "history.json", "history.json.bak",
            "config.json", "config.json.bak", "python",
            "runtime", ".git", ".gitignore", "scratch",
            "dist", "dist_portable", ".update_tmp"
        }

        copied_files = []
        for root, dirs, files in os.walk(source_root):
            rel_path = os.path.relpath(root, source_root)
            rel_parts = [] if rel_path == "." else rel_path.split(os.sep)

            if rel_parts and rel_parts[0] in PROTECTED_ITEMS:
                continue

            target_dir = os.path.join(BASE_DIR, rel_path) if rel_path != "." else BASE_DIR
            os.makedirs(target_dir, exist_ok=True)

            for file_name in files:
                if file_name in PROTECTED_ITEMS:
                    continue
                if file_name.endswith(".zip") or file_name.endswith(".tar.gz"):
                    continue

                src_file = os.path.join(root, file_name)
                dst_file = os.path.join(target_dir, file_name)

                try:
                    shutil.copy2(src_file, dst_file)
                    copied_files.append(os.path.relpath(dst_file, BASE_DIR))
                except Exception as ce:
                    print(f"[UPDATE WARN] Skipped file copy ({file_name}): {ce}")

        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[UPDATE] Replaced {len(copied_files)} files cleanly (user data preserved)")

        def delayed_restart():
            time.sleep(1.5)
            try:
                cmd = [sys.executable, os.path.join(BASE_DIR, "server.py")]
                if len(sys.argv) > 1:
                    cmd = [sys.executable] + sys.argv
                flags = 0
                if sys.platform == "win32":
                    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                subprocess.Popen(cmd, cwd=BASE_DIR, creationflags=flags)
                print("[UPDATE] Successfully started new server process.")
            except Exception as re:
                print(f"[UPDATE RESTART ERROR] {re}")
            finally:
                os._exit(0)

        threading.Thread(target=delayed_restart, daemon=True).start()

        return {
            "success": True,
            "message": "업데이트가 성공적으로 적용되었습니다. 잠시 후 서버가 재기동됩니다.",
            "copied_count": len(copied_files)
        }
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"업데이트 적용 실패: {str(e)}")

@app.get("/api/update/check")
async def api_check_update(force: bool = False):
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, fetch_latest_release, force)
    return res

@app.post("/api/update/apply")
async def api_apply_update():
    loop = asyncio.get_running_loop()
    release_info = await loop.run_in_executor(None, fetch_latest_release, True)
    zip_url = release_info.get("zip_url")
    if not zip_url:
        raise HTTPException(status_code=400, detail="다운로드할 최신 릴리즈 ZIP URL을 찾을 수 없습니다.")

    try:
        res = await loop.run_in_executor(None, apply_update_from_zip, zip_url)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json") if 'DATA_DIR' in globals() else "schedule.json"

def calculate_next_trigger_datetime(time_str: str, repeat_mode: str, base_time: Optional[datetime] = None) -> datetime:
    if base_time is None:
        base_time = datetime.now()
    parts = time_str.split(":")
    h, m = int(parts[0]), int(parts[1])
    next_dt = base_time.replace(hour=h, minute=m, second=0, microsecond=0)
    if next_dt <= base_time:
        next_dt += timedelta(days=1)

    if repeat_mode == "weekdays":
        while next_dt.weekday() in (5, 6):
            next_dt += timedelta(days=1)
    elif repeat_mode == "weekends":
        while next_dt.weekday() not in (5, 6):
            next_dt += timedelta(days=1)
    return next_dt

def dict_to_recipe_model(data: dict) -> RecipeModel:
    steps_raw = data.get("steps") or data.get("pours") or []
    step_models = []
    for s in steps_raw:
        step_models.append(
            StepModel(
                temp=int(s.get("temp", s.get("temperature", 93))),
                water=int(s.get("water", s.get("ml", 50))),
                wait=int(s.get("wait", s.get("pause", 15))),
                flow=float(s.get("flow", 3.2)),
                pattern=str(s.get("pattern", "center")),
                agitation_before=bool(s.get("agitation_before", False)),
                agitation_after=bool(s.get("agitation_after", s.get("agitation", False)))
            )
        )
    return RecipeModel(
        name=str(data.get("name", "Scheduled Brew")),
        dose=int(data.get("dose", 15)),
        grind_size=int(data.get("grind_size", data.get("grind", 45))),
        grind_enabled=bool(data.get("grind_enabled", True) if "grind_enabled" in data else (int(data.get("grind", 45)) > 0)),
        grind_rpm=int(data.get("grind_rpm", data.get("rpm", 80))),
        bypass_enabled=bool(data.get("bypass_enabled", False)),
        bypass_volume=float(data.get("bypass_volume", 0.0)),
        bypass_temp=float(data.get("bypass_temp", 85.0)),
        steps=step_models
    )

async def scheduled_brew_daemon_loop():
    print("[SCHEDULE DAEMON] ⏰ Background Scheduled Brew Watcher Started.")
    pre_staged_schedule_id = None

    while True:
        try:
            await asyncio.sleep(5)
            if not os.path.exists(SCHEDULE_FILE):
                continue

            try:
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                    schedules = json.load(f)
            except Exception:
                continue

            if not schedules or not isinstance(schedules, list):
                continue

            schedule = schedules[0]
            if not schedule or not schedule.get("enabled"):
                pre_staged_schedule_id = None
                continue

            now_ts = time.time() * 1000
            target_ts = schedule.get("next_timestamp")
            time_val = schedule.get("time", "07:30")
            repeat_val = schedule.get("repeat", "once")

            if not target_ts or target_ts < now_ts - 60000:
                if target_ts and target_ts < now_ts - 60000:
                    schedule["enabled"] = False
                    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                        json.dump(schedules, f, ensure_ascii=False, indent=2)
                    continue
                else:
                    next_dt = calculate_next_trigger_datetime(time_val, "once")
                    schedule["next_timestamp"] = int(next_dt.timestamp() * 1000)
                    target_ts = schedule["next_timestamp"]
                    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                        json.dump(schedules, f, ensure_ascii=False, indent=2)

            diff_sec = (target_ts - now_ts) / 1000.0

            if 0 < diff_sec <= 35:
                if pre_staged_schedule_id != schedule.get("id"):
                    pre_staged_schedule_id = schedule.get("id")
                    msg = f"[SCHEDULE] ⏳ (T-{int(diff_sec)}초) 파이썬 백엔드: 머신 사전 예열 연결 및 레시피 무장 시작..."
                    print(msg)
                    await broadcast_msg({"type": "log", "msg": msg})

                    if not ble_client or ble_connection_status != "CONNECTED":
                        try:
                            await connect_ble_task()
                        except Exception as e:
                            print(f"[SCHEDULE] Pre-connect error: {e}")

                    if ble_client and ble_connection_status == "CONNECTED":
                        raw_recipe = schedule.get("recipe") or {}
                        recipe_model = dict_to_recipe_model(raw_recipe)
                        recipe_obj = build_official_recipe_object(recipe_model)
                        try:
                            if hasattr(ble_client, "load_recipe"):
                                res = ble_client.load_recipe(recipe_obj)
                                if asyncio.iscoroutine(res):
                                    await res
                                latest_telemetry["state"] = "ARMED"
                                await broadcast_msg({"type": "telemetry", **latest_telemetry})
                                print(f"[SCHEDULE] ✅ 30초 전 머신 기상 및 레시피 무장 완료! (정각 즉시 시동 대기)")
                        except Exception as e:
                            print(f"[SCHEDULE] Staging error: {e}")

            if -15 <= diff_sec <= 0:
                if not schedule.get("_triggered"):
                    schedule["_triggered"] = True
                    msg = f"[SCHEDULE] ⏰ {time_val} 정각 도달! 파이썬 백엔드: 지연 시간 0초 즉시 추출 시동!"
                    print(msg)
                    await broadcast_msg({"type": "log", "msg": msg})

                    raw_recipe = schedule.get("recipe") or {}
                    recipe_model = dict_to_recipe_model(raw_recipe)

                    asyncio.create_task(start_brew(recipe_model))

                    schedule["enabled"] = False
                    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                        json.dump(schedules, f, ensure_ascii=False, indent=2)
                    pre_staged_schedule_id = None

        except asyncio.CancelledError:
            print("[SCHEDULE DAEMON] Watcher task cancelled.")
            break
        except Exception as e:
            print(f"[SCHEDULE DAEMON ERROR] {e}")

@app.get("/api/schedule")
async def api_get_schedule():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"schedules": data if isinstance(data, list) else [data]}
        except Exception:
            pass
    return {"schedules": []}

@app.post("/api/schedule")
async def api_save_schedule(request: Request):
    data = await request.json()
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump([data], f, ensure_ascii=False, indent=2)
        return {"success": True, "schedule": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/schedule")
async def api_delete_schedule():
    if os.path.exists(SCHEDULE_FILE):
        try:
            os.remove(SCHEDULE_FILE)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}

@app.post("/api/schedule/check-supply")
async def api_check_supply():
    global ble_client, ble_connection_status, latest_telemetry
    if not ble_client or ble_connection_status != "CONNECTED":
        return {
            "success": False,
            "reason": "NOT_CONNECTED",
            "message": "머신 BLE가 연결되어 있지 않습니다. 머신 전원을 확인해주세요."
        }

    current_state = str(latest_telemetry.get("state", "")).lower()
    if current_state in ("no_water", "0x0c", "12"):
        return {
            "success": False,
            "reason": "NO_WATER",
            "message": "물탱크에 물이 부족합니다. 물을 채운 후 다시 예약해주세요."
        }

    return {
        "success": True,
        "state": current_state.upper() or "IDLE",
        "message": "물탱크 수위 정상 감지됨"
    }

@app.post("/api/schedule/test-run")
async def api_schedule_test_run(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    raw_recipe = data.get("recipe") or {}
    recipe_model = dict_to_recipe_model(raw_recipe)
    msg = f"[SCHEDULE TEST] 🧪 파이썬 백엔드: '{recipe_model.name}' 모의 무인 추출 테스트 가동"
    print(msg)
    await broadcast_msg({"type": "log", "msg": msg})
    asyncio.create_task(start_brew(recipe_model))
    return {"success": True, "message": "테스트 실행 명령 접수 완료"}

@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse(status_code=404, content={"message": "static/index.html 파일을 찾을 수 없습니다."})

app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="xBloom bleUI Web Server")
    parser.add_argument("-p", "--port", type=int, default=8000, help="서버 포트 번호")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="호스트 주소")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="개발용: 코드 저장 시 서버 자동 재시작. 추출 중에도 BLE가 끊기므로 평소에는 쓰지 마세요.",
    )
    args = parser.parse_args()

    print(f"\n========================================================")
    print(f"  xBloom bleUI v{CURRENT_VERSION} Server Started")
    print(f"  - Local URL:   http://localhost:{args.port}")
    print(f"  - Network URL: http://0.0.0.0:{args.port}")
    print(f"========================================================\n")

    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)