import shutil
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
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.parse
import uvicorn
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from bleak import BleakScanner
from xbloom_ble.client import XBloomClient
import xbloom_ble.recipe as recipe_module
RecipeClass = getattr(recipe_module, 'Recipe', None)
StepClass = None
for candidate in ['Step', 'PourStep', 'RecipeStep', 'Pour']:
    if hasattr(recipe_module, candidate):
        StepClass = getattr(recipe_module, candidate)
        break
try:
    import xbloom_ble.cloud as cloud_module
except Exception as ce:
    print(f'[WARN] xbloom_ble.cloud 임포트 실패: {ce}')
    cloud_module = None

def get_cloud_handler():
    if not cloud_module:
        return None
    if hasattr(cloud_module, 'login'):
        return cloud_module
    for attr_name in ['XBloomCloudClient', 'CloudClient', 'XBloomCloud', 'Cloud']:
        if hasattr(cloud_module, attr_name):
            cls = getattr(cloud_module, attr_name)
            if isinstance(cls, type):
                try:
                    return cls()
                except Exception:
                    pass
    return cloud_module
cloud_client = None
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
RECIPES_DIR = os.path.join(BASE_DIR, 'recipes')
SLOTS_DIR = os.path.join(RECIPES_DIR, 'slots')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'history.json')
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(RECIPES_DIR, exist_ok=True)
os.makedirs(SLOTS_DIR, exist_ok=True)

def normalize_pattern(pat: Optional[str]) -> str:
    p = str(pat or 'center').strip().lower()
    if p in ['ring', 'circle', 'circular']:
        return 'ring'
    if p in ['spiral']:
        return 'spiral'
    return 'center'

def load_server_config() -> Dict[str, Any]:
    default_config = {'theme': 'dark', 'wallpaper': None, 'cloud_user': None, 'record_aborted_brews': False, 'pour_marker_mode': 'weight', 'chart_smoothing': True, 'handdrip_interval_sync': False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**default_config, **json.load(f)}
        except Exception:
            return default_config
    return default_config

def save_server_config(cfg: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[WARN] 설정 저장 실패: {e}')
server_config = load_server_config()

def load_brew_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f'[WARN] 추출 히스토리 로드 실패: {e}')
    return []

def save_brew_history(records: List[Dict[str, Any]]):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(records[:500], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[WARN] 추출 히스토리 저장 실패: {e}')

def restore_cloud_session():
    global cloud_client
    if not cloud_client:
        cloud_client = get_cloud_handler()
    if not cloud_client or not server_config.get('cloud_user'):
        return
    token = server_config['cloud_user'].get('token')
    if token:
        for attr in ['token', 'access_token', '_token', '_access_token']:
            if hasattr(cloud_client, attr):
                try:
                    setattr(cloud_client, attr, token)
                except Exception:
                    pass
        for method in ['set_token', 'set_auth_token', 'authenticate_with_token']:
            if hasattr(cloud_client, method):
                try:
                    getattr(cloud_client, method)(token)
                except Exception:
                    pass
ble_client: Optional[XBloomClient] = None
connected_websockets = set()
main_loop: Optional[asyncio.AbstractEventLoop] = None
ble_lock = asyncio.Lock()
latest_telemetry: Dict[str, Any] = {'temperature': 0, 'pour_weight': 0.0, 'yield_weight': 0.0, 'state': 'IDLE', 'elapsed_time': 0, 'step_index': 0}
ble_connection_status = 'DISCONNECTED'
discovered_device_address = None

class StepModel(BaseModel):
    temp: int = 93
    water: int = 50
    wait: int = 15
    flow: float = 3.2
    pattern: str = 'center'
    agitation_before: bool = False
    agitation_after: bool = False

class RecipeModel(BaseModel):
    name: str = 'Custom Brew'
    dose: int = 15
    grind_size: int = 45
    grind_enabled: bool = True
    grind_rpm: int = 80
    interval_sync: bool = False
    steps: List[StepModel] = Field(default_factory=list)

class CloudLoginModel(BaseModel):
    email: str
    password: str

class FetchSharedRecipeRequest(BaseModel):
    url: str

class SettingsUpdateModel(BaseModel):
    theme: Optional[str] = None
    wallpaper: Optional[str] = None
    record_aborted_brews: Optional[bool] = None
    pour_marker_mode: Optional[str] = None
    chart_smoothing: Optional[bool] = None
    handdrip_interval_sync: Optional[bool] = None

class HistoryItemModel(BaseModel):
    id: Optional[str] = None
    date: Optional[str] = None
    recipeName: str = 'Custom Brew'
    dose: int = 15
    totalWater: float = 0.0
    totalYield: float = 0.0
    duration: str = '00:00'
    durationSec: Optional[int] = 0
    status: str = 'completed'
    chartData: Optional[List[Dict[str, Any]]] = None
    markers: Optional[List[Dict[str, Any]]] = None
    recipe: Optional[Dict[str, Any]] = None
    beanName: Optional[str] = ''
    notes: Optional[str] = ''

class HistoryUpdateNotesModel(BaseModel):
    beanName: Optional[str] = None
    notes: Optional[str] = None

async def broadcast_msg(data: Dict[str, Any]):
    for ws in list(connected_websockets):
        try:
            await ws.send_json(data)
        except Exception:
            connected_websockets.discard(ws)

def on_machine_telemetry(telemetry_data):
    global latest_telemetry, main_loop
    try:
        for attr in ['temp_c', 'current_temperature', 'temperature', 'temp']:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) > 0:
                    latest_telemetry['temperature'] = int(round(float(v)))
                    break
        for attr in ['water_g', 'water_volume', 'pour_weight', 'pour', 'water']:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) >= 0:
                    latest_telemetry['pour_weight'] = round(float(v), 1)
                    break
        for attr in ['coffee_g', 'weight_g', 'scale_weight', 'yield_weight', 'weight']:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and float(v) >= 0:
                    latest_telemetry['yield_weight'] = round(float(v), 1)
                    break
        st_val = None
        for attr in ['status_name', 'state_name', 'status', 'state']:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None:
                    st_val = str(v)
                    break
        if st_val and st_val != 'scale' and (not st_val.startswith('ack_')):
            latest_telemetry['state'] = st_val.upper()
        for attr in ['current_step', 'step_index', 'step']:
            if hasattr(telemetry_data, attr):
                v = getattr(telemetry_data, attr)
                if v is not None and int(v) > 0:
                    latest_telemetry['step_index'] = int(v)
                    break
        payload = {'type': 'telemetry', **latest_telemetry}
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_msg(payload), main_loop)
    except Exception as e:
        print(f'[WARN] 텔레메트리 파싱 실패: {e}')

async def connect_ble_task():
    global ble_client, ble_connection_status, discovered_device_address
    ble_connection_status = 'SCANNING'
    print('\n[BLE] 주변의 xBloom 기기를 블루투스로 검색 중입니다...')
    await broadcast_msg({'type': 'log', 'msg': '[BLE] 주변 xBloom 기기 탐색 중...'})
    await broadcast_msg({'type': 'status', 'ble_status': 'SCANNING'})
    target_address = None
    try:
        devices = await BleakScanner.discover(timeout=6.0)
        for d in devices:
            d_name = (d.name or '').lower()
            if 'xbloom' in d_name or 'bloom' in d_name:
                target_address = d.address
                print(f'[BLE] 기기 발견: {d.name} ({d.address})')
                await broadcast_msg({'type': 'log', 'msg': f'[BLE] 기기 발견: {d.name} ({d.address})'})
                break
        if not target_address:
            raise RuntimeError('주변에서 xBloom 기기를 찾지 못했습니다. 전원을 확인해주세요.')
        discovered_device_address = target_address
        print(f'[BLE] 기기({target_address})에 연결 시도...')
        await broadcast_msg({'type': 'log', 'msg': '[BLE] 페어링 연결 시도 중...'})
        ble_client = XBloomClient(target_address)
        if hasattr(ble_client, 'connect'):
            await ble_client.connect()
        if hasattr(ble_client, 'open_session'):
            res = ble_client.open_session()
            if asyncio.iscoroutine(res):
                await res
            print('[BLE] open_session 완료 (기기 연결 표시 활성화)')
        if hasattr(ble_client, 'add_telemetry_listener'):
            ble_client.add_telemetry_listener(on_machine_telemetry)
            print('[BLE] 실시간 텔레메트리 팬아웃 리스너 등록 완료')
        ble_connection_status = 'CONNECTED'
        print('[BLE] xBloom 머신 정상 연결 및 제어 준비 완료!')
        await broadcast_msg({'type': 'log', 'msg': '[BLE] 머신 연결 성공! 제어 준비 완료.'})
        await broadcast_msg({'type': 'status', 'ble_status': 'CONNECTED'})
    except Exception as e:
        ble_connection_status = 'ERROR'
        err_msg = f'[BLE ERROR] {str(e)}'
        print(f'\n{err_msg}')
        await broadcast_msg({'type': 'log', 'msg': err_msg})
        await broadcast_msg({'type': 'status', 'ble_status': 'ERROR'})

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cloud_client, main_loop
    main_loop = asyncio.get_running_loop()
    cloud_client = get_cloud_handler()
    if cloud_client:
        restore_cloud_session()
        print(f'[CLOUD] 클라우드 모듈 로드 완료: {type(cloud_client).__name__}')
    ble_init_task = asyncio.create_task(connect_ble_task())
    yield
    if ble_init_task and (not ble_init_task.done()):
        ble_init_task.cancel()
app = FastAPI(title='xBloom bleUI Server', version='0.8.1', lifespan=lifespan)

class ProtocolCompliantPour:

    def __init__(self, water: int, temp: int, wait: int, flow: float, pattern: str='center', agitation_before: bool=False, agitation_after: bool=False, rpm: int=0):
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
        self.rpm = 0 if self.pattern == 'center' else int(rpm or 80)
        self.agitation_before = bool(agitation_before)
        self.agitation_after = bool(agitation_after)
        self.agitation = bool(agitation_after or agitation_before)
        self.vibration = bool(agitation_after or agitation_before)
        self.isEnableVibrationBefore = bool(agitation_before)
        self.isEnableVibrationAfter = bool(agitation_after)

    def __getattr__(self, item):
        if item == 'rpm':
            return self.rpm
        return False

    def ble_omissions(self) -> list[str]:
        return []

    def to_dict(self):
        return {'ml': self.ml, 'water': self.water, 'water_ml': self.water_ml, 'water_g': self.water_g, 'weight_g': self.weight_g, 'temp': self.temp, 'temp_c': self.temp_c, 'temperature': self.temperature, 'wait': self.wait, 'wait_s': self.wait_s, 'pause': self.pause, 'pause_s': self.pause_s, 'pause_time': self.pause_time, 'flow': self.flow, 'flow_rate': self.flow_rate, 'flow_rate_ml_s': self.flow_rate_ml_s, 'flow_ml_s': self.flow_ml_s, 'pattern': self.pattern, 'rpm': self.rpm, 'agitation': self.agitation_after, 'agitation_before': self.agitation_before, 'agitation_after': self.agitation_after, 'isEnableVibrationBefore': self.isEnableVibrationBefore, 'isEnableVibrationAfter': self.isEnableVibrationAfter, 'vibration': self.vibration}

    def __getitem__(self, item):
        return self.to_dict().get(item, False)

    def get(self, item, default=None):
        return self.to_dict().get(item, default)

class ProtocolCompliantRecipe:

    def __init__(self, name: str, dose: int, grind_size: int, grind_enabled: bool, grind_rpm: int, pours: list):
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
        self.total_water = sum((getattr(p, 'water', 0) for p in pours))
        self.total_water_g = self.total_water
        self.total_water_ml = self.total_water
        calc_ratio = self.total_water / self.dose if self.dose > 0 else 0.0
        self.effective_ratio = float(calc_ratio)
        self.ratio = float(calc_ratio)
        self.brew_ratio = float(calc_ratio)

    def __getattr__(self, item):
        if item == 'no_grind':
            return not self.grind_enabled or int(self.grind) == 0
        if item in ['effective_ratio', 'ratio', 'brew_ratio']:
            return float(self.total_water / self.dose) if self.dose > 0 else 15.0
        if item in ['total_water', 'total_water_g', 'grand_water', 'grandWater']:
            return float(self.total_water)
        if item in ['rpm', 'grinder_rpm']:
            return self.rpm
        return 0.0

    def validate(self):
        return True

    def ble_warnings(self) -> list[str]:
        out = []
        for i, p in enumerate(self.pours, start=1):
            if hasattr(p, 'ble_omissions'):
                omitted = p.ble_omissions()
                if omitted:
                    out.append(f"푸어 #{i}: {', '.join(omitted)}은 머신 BLE 프로토콜 제약으로 생략됩니다 (클라우드 전송 시 동작).")
        return out

    def to_protocol_dict(self):
        return {'name': self.name, 'dose': self.dose, 'dose_g': self.dose_g, 'grind': self.grind, 'grind_size': self.grind_size, 'grind_enabled': self.grind_enabled, 'enable_grind': self.enable_grind, 'rpm': self.rpm, 'grind_rpm': self.grind_rpm, 'effective_ratio': self.effective_ratio, 'ratio': self.ratio, 'total_water': self.total_water, 'pours': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.pours], 'steps': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.steps]}

    def __getitem__(self, item):
        return self.to_protocol_dict().get(item, 0.0)

    def get(self, item, default=None):
        return self.to_protocol_dict().get(item, default)

def build_official_recipe_object(recipe_data: Any):
    if isinstance(recipe_data, dict):
        rec_name = recipe_data.get('name', 'Custom Brew')
        rec_dose = int(recipe_data.get('dose', 15))
        rec_grind = int(recipe_data.get('grind_size', 45))
        rec_grind_on = bool(recipe_data.get('grind_enabled', True))
        rec_rpm = int(recipe_data.get('grind_rpm', 80))
        raw_steps = recipe_data.get('steps') or recipe_data.get('pours') or []
    else:
        rec_name = getattr(recipe_data, 'name', 'Custom Brew')
        rec_dose = int(getattr(recipe_data, 'dose', 15))
        rec_grind = int(getattr(recipe_data, 'grind_size', 45))
        rec_grind_on = bool(getattr(recipe_data, 'grind_enabled', True))
        rec_rpm = int(getattr(recipe_data, 'grind_rpm', 80))
        raw_steps = getattr(recipe_data, 'steps', None) or getattr(recipe_data, 'pours', None) or []
    rec_rpm = max(60, min(120, round(rec_rpm / 10) * 10))
    pours = []
    for s in raw_steps:
        s_water = getattr(s, 'water', None) if hasattr(s, 'water') else s.get('water', 50)
        s_temp = getattr(s, 'temp', None) if hasattr(s, 'temp') else s.get('temp', s.get('temperature', 93))
        s_wait = getattr(s, 'wait', None) if hasattr(s, 'wait') else s.get('wait', s.get('pause', 15))
        s_flow = getattr(s, 'flow', None) if hasattr(s, 'flow') else s.get('flow', s.get('flow_rate', 3.2))
        s_pattern = getattr(s, 'pattern', None) if hasattr(s, 'pattern') else s.get('pattern', 'center')
        s_before = getattr(s, 'agitation_before', None) if hasattr(s, 'agitation_before') else s.get('agitation_before', False)
        s_after = getattr(s, 'agitation_after', None) if hasattr(s, 'agitation_after') else s.get('agitation_after', s.get('agitation', False))
        pat = normalize_pattern(s_pattern)
        step_rpm = 0 if pat == 'center' else max(60, min(120, rec_rpm))
        if StepClass:
            try:
                step_obj = StepClass(ml=int(s_water), temp_c=int(s_temp), pattern=pat, agitation=bool(s_after), pause_s=int(s_wait), rpm=step_rpm, flow_ml_s=float(s_flow), agitation_before=bool(s_before))
                for attr, val in [('water', int(s_water)), ('water_ml', int(s_water)), ('water_g', int(s_water)), ('temp', int(s_temp)), ('temperature', int(s_temp)), ('temperature_c', int(s_temp)), ('wait', int(s_wait)), ('wait_s', int(s_wait)), ('pause', int(s_wait)), ('flow', float(s_flow)), ('flow_rate', float(s_flow)), ('rpm', step_rpm), ('agitation_after', bool(s_after)), ('agitation_before', bool(s_before)), ('isEnableVibrationBefore', bool(s_before)), ('isEnableVibrationAfter', bool(s_after)), ('vibration', bool(s_after or s_before))]:
                    try:
                        setattr(step_obj, attr, val)
                    except Exception:
                        pass
                pours.append(step_obj)
                continue
            except Exception:
                pass
        pours.append(ProtocolCompliantPour(water=int(s_water), temp=int(s_temp), wait=int(s_wait), flow=float(s_flow), pattern=pat, agitation_before=bool(s_before), agitation_after=bool(s_after), rpm=step_rpm))
    effective_grind = rec_grind if rec_grind_on else 0
    total_w = sum((getattr(p, 'water', 0) for p in pours))
    calc_ratio = float(total_w / rec_dose) if rec_dose > 0 else 0.0
    is_no_grind = not rec_grind_on or effective_grind == 0
    if RecipeClass:
        try:
            rec_obj = RecipeClass(name=rec_name, dose_g=rec_dose, grind=effective_grind, pours=pours)
            for attr, val in [('dose', rec_dose), ('dose_g', rec_dose), ('grind_size', effective_grind), ('grind_enabled', rec_grind_on), ('enable_grind', rec_grind_on), ('rpm', rec_rpm if rec_grind_on else 0), ('grind_rpm', rec_rpm if rec_grind_on else 0), ('no_grind', is_no_grind), ('effective_ratio', calc_ratio), ('ratio', calc_ratio), ('total_water', total_w), ('total_water_g', total_w)]:
                try:
                    setattr(rec_obj, attr, val)
                except Exception:
                    pass
            return rec_obj
        except Exception:
            pass
    return ProtocolCompliantRecipe(name=rec_name, dose=rec_dose, grind_size=effective_grind, grind_enabled=rec_grind_on, grind_rpm=rec_rpm, pours=pours)

def get_default_fallback_recipe(name: str):
    return build_official_recipe_object({'name': name, 'dose': 15, 'grind_size': 45, 'grind_enabled': True, 'grind_rpm': 80, 'steps': [{'temp': 93, 'water': 45, 'wait': 30, 'flow': 3.2, 'pattern': 'center', 'agitation_before': False, 'agitation_after': True}, {'temp': 93, 'water': 180, 'wait': 15, 'flow': 3.2, 'pattern': 'spiral', 'agitation_before': False, 'agitation_after': False}]})
SLOT_KEY_MAP = {1: 'A', 2: 'B', 3: 'C'}

@app.websocket('/ws/telemetry')
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        await websocket.send_json({'type': 'status', 'ble_status': ble_connection_status, 'telemetry': latest_telemetry})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)

@app.get('/api/status')
async def get_status():
    is_conn = ble_connection_status == 'CONNECTED'
    return {'ble_connected': is_conn, 'ble_status': ble_connection_status, 'device_address': discovered_device_address, 'telemetry': latest_telemetry}

@app.get('/api/settings')
async def get_settings():
    return server_config

@app.post('/api/settings')
async def update_settings(cfg_update: SettingsUpdateModel):
    global server_config
    if cfg_update.theme is not None:
        server_config['theme'] = cfg_update.theme
    if cfg_update.wallpaper is not None:
        server_config['wallpaper'] = cfg_update.wallpaper if cfg_update.wallpaper != '' else None
    if cfg_update.record_aborted_brews is not None:
        server_config['record_aborted_brews'] = bool(cfg_update.record_aborted_brews)
    if cfg_update.pour_marker_mode is not None:
        server_config['pour_marker_mode'] = str(cfg_update.pour_marker_mode)
    if cfg_update.chart_smoothing is not None:
        server_config['chart_smoothing'] = bool(cfg_update.chart_smoothing)
    if cfg_update.handdrip_interval_sync is not None:
        server_config['handdrip_interval_sync'] = bool(cfg_update.handdrip_interval_sync)
    save_server_config(server_config)
    return {'status': 'ok', 'config': server_config}

@app.get('/api/history')
async def get_history(limit: int=100):
    records = load_brew_history()
    return {'records': records[:limit], 'total': len(records)}

@app.post('/api/history')
async def add_history_record(record: HistoryItemModel):
    records = load_brew_history()
    rec_dict = record.model_dump() if hasattr(record, 'model_dump') else record.dict()
    if not rec_dict.get('id'):
        rec_dict['id'] = f'hist_{int(time.time() * 1000)}'
    if not rec_dict.get('date'):
        rec_dict['date'] = time.strftime('%m. %d. %H:%M')
    records.insert(0, rec_dict)
    save_brew_history(records)
    print(f"[HISTORY] 새 추출 기록 저장: {rec_dict['recipeName']} ({rec_dict.get('status', 'completed')}) - {rec_dict['totalYield']}g / {rec_dict['duration']}")
    return {'status': 'saved', 'record': rec_dict}

@app.put('/api/history/{record_id}')
async def update_history_notes(record_id: str, update_data: HistoryUpdateNotesModel):
    records = load_brew_history()
    target = None
    for r in records:
        if r.get('id') == record_id:
            target = r
            if update_data.beanName is not None:
                target['beanName'] = update_data.beanName
            if update_data.notes is not None:
                target['notes'] = update_data.notes
            break
    if not target:
        raise HTTPException(status_code=404, detail='해당 추출 기록을 찾을 수 없습니다.')
    save_brew_history(records)
    return {'status': 'updated', 'record': target}

@app.delete('/api/history/{record_id}')
async def delete_history_record(record_id: str):
    records = load_brew_history()
    new_records = [r for r in records if r.get('id') != record_id]
    if len(new_records) == len(records):
        raise HTTPException(status_code=404, detail='해당 추출 기록을 찾을 수 없습니다.')
    save_brew_history(new_records)
    print(f'[HISTORY] 추출 기록 삭제: ID {record_id}')
    return {'status': 'deleted', 'id': record_id, 'remaining': len(new_records)}

@app.delete('/api/history')
async def clear_all_history():
    save_brew_history([])
    print('[HISTORY] 전체 추출 기록 일괄 삭제 완료')
    return {'status': 'cleared'}

@app.post('/api/ble/reconnect')
async def trigger_reconnect():
    global ble_connection_status
    if ble_connection_status == 'SCANNING':
        return {'status': 'already_scanning'}
    asyncio.create_task(connect_ble_task())
    return {'status': 'reconnecting'}

@app.post('/api/ble/disconnect')
async def trigger_disconnect():
    global ble_client, ble_connection_status
    print('\n[BLE] 머신 연결 해제 요청 수신...')
    if ble_client:
        try:
            if hasattr(ble_client, 'close_session'):
                res = ble_client.close_session()
                if asyncio.iscoroutine(res):
                    await res
            if hasattr(ble_client, 'disconnect'):
                res = ble_client.disconnect()
                if asyncio.iscoroutine(res):
                    await res
        except Exception as e:
            print(f'[WARN] 연결 해제 중 예외: {e}')
    ble_connection_status = 'DISCONNECTED'
    print('[BLE] 머신과의 연결이 해제되었습니다.')
    await broadcast_msg({'type': 'log', 'msg': '[BLE] 머신과의 연결이 해제되었습니다.'})
    await broadcast_msg({'type': 'status', 'ble_status': 'DISCONNECTED'})
    return {'status': 'disconnected'}

@app.get('/api/recipes/local')
async def get_local_recipes():
    recipe_files = glob.glob(os.path.join(RECIPES_DIR, '*.yaml')) + glob.glob(os.path.join(RECIPES_DIR, '*.yml'))
    recipes_list = []
    for fpath in recipe_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if not data:
                    continue
                steps_data = []
                raw_steps = data.get('steps') or data.get('pours') or []
                for s in raw_steps:
                    steps_data.append({'temp': int(s.get('temp') or s.get('temperature', 92)), 'water': int(s.get('water') or s.get('pour') or s.get('ml', 50)), 'wait': int(s.get('wait') or s.get('pause_time') or s.get('pause', 15)), 'flow': float(s.get('flow_rate') or s.get('flow', 3.2)), 'pattern': normalize_pattern(s.get('pattern', 'center')), 'agitation_before': bool(s.get('agitation_before', False)), 'agitation_after': bool(s.get('agitation_after', s.get('agitation', False)))})
                grind_val = int(data.get('grind_size') or data.get('grind', 45))
                grind_on = data.get('grind_enabled', data.get('enable_grind', grind_val > 0))
                grind_rpm = int(data.get('grind_rpm', data.get('rpm', 80)))
                grind_rpm = max(60, min(120, round(grind_rpm / 10) * 10))
                total_water_ml = sum((s['water'] for s in steps_data))
                recipes_list.append({'filename': os.path.basename(fpath), 'name': data.get('name', os.path.splitext(os.path.basename(fpath))[0]), 'dose': int(data.get('dose', 15)), 'grind_size': grind_val if grind_val > 0 else 45, 'grind_enabled': bool(grind_on), 'grind_rpm': grind_rpm, 'interval_sync': False, 'total_water': total_water_ml, 'pour_count': len(steps_data), 'steps': steps_data})
        except Exception as e:
            print(f'[WARN] 레시피 파일 로드 실패 ({fpath}): {e}')
    recipes_list.sort(key=lambda x: x.get('name', '').lower())
    return {'recipes': recipes_list}

@app.delete('/api/recipes/local/{filename}')
async def delete_local_recipe(filename: str):
    clean_name = os.path.basename(filename)
    if clean_name != filename or not filename.endswith(('.yaml', '.yml')):
        raise HTTPException(status_code=400, detail='유효하지 않은 레시피 파일명입니다.')
    file_path = os.path.join(RECIPES_DIR, clean_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='해당 레시피 파일을 찾을 수 없습니다.')
    try:
        os.remove(file_path)
        print(f'[RECIPE] 서버 레시피 파일 삭제 완료: {clean_name}')
        return {'status': 'deleted', 'filename': clean_name}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'파일 삭제 실패: {str(e)}')

@app.post('/api/recipes/save')
async def save_recipe_to_server(recipe_data: RecipeModel):
    try:
        safe_name = re.sub('[\\\\/*?:"<>|]', '', recipe_data.name).strip()
        if not safe_name:
            safe_name = 'custom_recipe'
        filename = f'{safe_name}.yaml'
        file_path = os.path.join(RECIPES_DIR, filename)
        yaml_content = {'name': recipe_data.name, 'dose': int(recipe_data.dose), 'grind_size': int(recipe_data.grind_size), 'grind_enabled': bool(recipe_data.grind_enabled), 'grind_rpm': int(recipe_data.grind_rpm), 'steps': [{'temp': int(s.temp), 'pour': int(s.water), 'wait': int(s.wait), 'flow_rate': float(s.flow), 'pattern': normalize_pattern(s.pattern), 'agitation_before': bool(s.agitation_before), 'agitation_after': bool(s.agitation_after)} for s in recipe_data.steps]}
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_content, f, allow_unicode=True, sort_keys=False)
        print(f'[RECIPE] 서버에 레시피 파일 저장 완료: {file_path}')
        return {'status': 'saved', 'filename': filename, 'name': recipe_data.name}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'서버 저장 실패: {str(e)}')

@app.post('/api/machine/slot/{slot_id}')
async def write_slot(slot_id: int, recipe_data: RecipeModel):
    global ble_client
    if not 1 <= slot_id <= 3:
        raise HTTPException(status_code=400, detail='슬롯 번호는 1~3번만 지원합니다.')
    if not ble_client or ble_connection_status != 'CONNECTED':
        raise HTTPException(status_code=503, detail='머신이 연결되어 있지 않습니다.')
    target_slot_file = os.path.join(SLOTS_DIR, f'slot_{slot_id}.json')
    try:
        with open(target_slot_file, 'w', encoding='utf-8') as f:
            json.dump(recipe_data.dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[WARN] 슬롯 캐시 저장 경고: {e}')
    all_slots_payload = {}
    for sid in [1, 2, 3]:
        key_name = SLOT_KEY_MAP[sid]
        if sid == slot_id:
            all_slots_payload[key_name] = build_official_recipe_object(recipe_data)
        else:
            s_file = os.path.join(SLOTS_DIR, f'slot_{sid}.json')
            if os.path.exists(s_file):
                try:
                    with open(s_file, 'r', encoding='utf-8') as f:
                        saved_json = json.load(f)
                        all_slots_payload[key_name] = build_official_recipe_object(saved_json)
                except Exception:
                    all_slots_payload[key_name] = get_default_fallback_recipe(f'Slot {key_name} Default')
            else:
                all_slots_payload[key_name] = get_default_fallback_recipe(f'Slot {key_name} Default')
    async with ble_lock:
        try:
            if hasattr(ble_client, 'save_slots'):
                target_key = SLOT_KEY_MAP[slot_id]
                print(f"[SLOT] xBloom 슬롯 매핑 전송: 슬롯 {target_key}({slot_id}번) 갱신 -> '{recipe_data.name}'")
                res = ble_client.save_slots(all_slots_payload)
                if asyncio.iscoroutine(res):
                    await res
                print(f'[SLOT] xBloom 머신 메모리 슬롯 저장 성공!')
            else:
                raise RuntimeError('클라이언트에 save_slots 메서드가 없습니다.')
        except Exception as e:
            print(f'[WARN] save_slots BLE 전송 오류: {e}')
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f'슬롯 저장 실패: {str(e)}')
    return {'status': 'saved', 'slot': slot_id, 'key': SLOT_KEY_MAP[slot_id], 'name': recipe_data.name}

@app.post('/api/brew/start')
async def start_brew(recipe_data: RecipeModel):
    global ble_client, ble_connection_status, latest_telemetry
    if not ble_client or ble_connection_status != 'CONNECTED':
        raise HTTPException(status_code=503, detail='머신이 BLE로 연결되어 있지 않습니다.')
    initial_temp = recipe_data.steps[0].temp if recipe_data.steps else 93
    latest_telemetry['pour_weight'] = 0.0
    latest_telemetry['yield_weight'] = 0.0
    latest_telemetry['temperature'] = int(round(float(initial_temp)))
    latest_telemetry['state'] = 'ARMING'
    latest_telemetry['step_index'] = 1
    latest_telemetry['elapsed_time'] = 0
    recipe_obj = build_official_recipe_object(recipe_data)
    print(f'\n[BREW] 공식 추출 루틴 실행: {recipe_data.name} (Dose: {recipe_data.dose}g)')
    if hasattr(recipe_obj, 'ble_warnings'):
        warnings = recipe_obj.ble_warnings()
        for w in warnings:
            print(f'[BREW NOTICE] {w}')
            await broadcast_msg({'type': 'log', 'msg': f'[안내] {w}'})
    async with ble_lock:
        try:
            await broadcast_msg({'type': 'log', 'msg': f"[BREW] '{recipe_data.name}' 레시피 전송 중..."})
            if hasattr(ble_client, 'load_recipe'):
                res = ble_client.load_recipe(recipe_obj)
                if asyncio.iscoroutine(res):
                    await res
            latest_telemetry['state'] = 'ARMED'
            await broadcast_msg({'type': 'log', 'msg': '[BREW] 머신 준비 완료 (ARMED), 추출을 시작합니다...'})
            start_event = None
            if hasattr(ble_client, 'start'):
                res = ble_client.start()
                if asyncio.iscoroutine(res):
                    res = await res
                start_event = res
                if res and hasattr(res, 'state_name') and (res.state_name in ('no_beans', 'no_water')):
                    what = '원두가' if res.state_name == 'no_beans' else '물이'
                    err_msg = f'[BREW] 머신 거부: {what} 부족합니다. 추출이 취소되었습니다.'
                    await broadcast_msg({'type': 'log', 'msg': err_msg})
                    if hasattr(ble_client, 'cancel_brew'):
                        res_c = ble_client.cancel_brew()
                        if asyncio.iscoroutine(res_c):
                            await res_c
                    latest_telemetry['state'] = 'CANCELLED'
                    raise RuntimeError(err_msg)
            elif hasattr(ble_client, 'brew'):
                res = ble_client.brew(recipe_obj)
                if asyncio.iscoroutine(res):
                    res = await res
                start_event = res
            is_grind_active = not getattr(recipe_obj, 'no_grind', False) and bool(recipe_data.grind_enabled)
            is_machine_starting = bool(start_event and getattr(start_event, 'state_name', '') == 'starting')
            if is_grind_active or is_machine_starting:
                latest_telemetry['state'] = 'STARTING'
                await broadcast_msg({'type': 'log', 'msg': f"[BREW] ⚙️ '{recipe_data.name}' 원두 분쇄 중 (Grind)... 분쇄 완료 후 추출이 시작됩니다."})
            else:
                latest_telemetry['state'] = 'BREWING'
                await broadcast_msg({'type': 'log', 'msg': f"[BREW] 🚀 '{recipe_data.name}' 실제 추출 진행 중..."})
            await broadcast_msg({'type': 'telemetry', **latest_telemetry})
        except Exception as e:
            traceback.print_exc()
            latest_telemetry['state'] = 'ERROR'
            await broadcast_msg({'type': 'log', 'msg': f'[BREW ERROR] {str(e)}'})
            raise HTTPException(status_code=500, detail=f'추출 실패: {str(e)}')
    return {'status': 'started', 'recipe': recipe_data.name, 'grind_enabled': bool(recipe_data.grind_enabled)}

@app.post('/api/brew/stop')
async def stop_brew():
    global ble_client
    async with ble_lock:
        if ble_client and hasattr(ble_client, 'cancel_brew'):
            res = ble_client.cancel_brew()
            if asyncio.iscoroutine(res):
                await res
        elif ble_client and hasattr(ble_client, 'stop'):
            res = ble_client.stop()
            if asyncio.iscoroutine(res):
                await res
    return {'status': 'stopped'}

@app.post('/api/cloud/login')
async def cloud_login(creds: CloudLoginModel):
    global cloud_client, server_config
    if not cloud_module:
        raise HTTPException(status_code=500, detail='xbloom_ble.cloud 모듈이 로드되지 않았습니다.')
    login_func = None
    if cloud_client and hasattr(cloud_client, 'login'):
        login_func = getattr(cloud_client, 'login')
    elif hasattr(cloud_module, 'login'):
        login_func = getattr(cloud_module, 'login')
    else:
        for attr in [a for a in dir(cloud_module) if not a.startswith('_')]:
            obj = getattr(cloud_module, attr)
            if hasattr(obj, 'login'):
                login_func = getattr(obj, 'login')
                cloud_client = obj
                break
    if not login_func:
        attrs = [a for a in dir(cloud_module) if not a.startswith('_')]
        raise HTTPException(status_code=500, detail=f'cloud 모듈에 login 함수를 찾을 수 없습니다. (속성: {attrs})')
    try:
        res = login_func(creds.email, creds.password)
        token = await res if asyncio.iscoroutine(res) else res
        token_str = str(token)
        if isinstance(token, dict):
            token_str = str(token.get('token') or token.get('access_token') or token)
        server_config['cloud_user'] = {'email': creds.email, 'token': token_str}
        save_server_config(server_config)
        restore_cloud_session()
        print(f'[CLOUD] 로그인 성공: {creds.email}')
        return {'success': True, 'token': token_str, 'email': creds.email}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=f'로그인 실패: {str(e)}')

@app.post('/api/cloud/logout')
async def cloud_logout():
    global server_config
    server_config['cloud_user'] = None
    save_server_config(server_config)
    return {'status': 'logged_out'}

@app.post('/api/cloud/upload')
async def cloud_upload(recipe_data: RecipeModel):
    global cloud_client
    if not cloud_module:
        raise HTTPException(status_code=500, detail='cloud 모듈이 로드되지 않았습니다.')
    if not server_config.get('cloud_user') or not server_config['cloud_user'].get('token'):
        raise HTTPException(status_code=401, detail='클라우드 로그인이 필요합니다. 설정 메뉴에서 먼저 로그인해주세요.')
    restore_cloud_session()
    candidate_names = ['add_recipe', 'upload_recipe', 'create_recipe', 'save_recipe', 'upload', 'publish_recipe']
    upload_func = None
    target_obj = cloud_client if cloud_client else cloud_module
    for cname in candidate_names:
        if hasattr(target_obj, cname):
            upload_func = getattr(target_obj, cname)
            break
    if not upload_func:
        available = [a for a in dir(target_obj) if not a.startswith('_')]
        raise HTTPException(status_code=500, detail=f'업로드 메서드를 찾지 못했습니다. 속성 목록: {available}')
    recipe_obj = build_official_recipe_object(recipe_data)
    try:
        res = upload_func(recipe_obj)
        resp_data = await res if asyncio.iscoroutine(res) else res
        print(f'[CLOUD] 레시피 업로드 원본 응답: {resp_data}')
        table_id = None
        share_url = None
        if isinstance(resp_data, dict):
            table_id = resp_data.get('tableId') or (resp_data.get('recipeVo') or {}).get('tableId')
            share_url = resp_data.get('shareRecipeLink') or (resp_data.get('recipeVo') or {}).get('shareRecipeLink')
        elif isinstance(resp_data, (int, str)):
            table_id = resp_data
        if not share_url and target_obj:
            list_func = getattr(target_obj, 'recipe_items', None) or getattr(target_obj, 'list_recipes', None)
            if list_func:
                for _ in range(2):
                    try:
                        items_res = list_func()
                        if asyncio.iscoroutine(items_res):
                            items_res = await items_res
                        items = items_res if isinstance(items_res, list) else items_res.get('list', []) if isinstance(items_res, dict) else []
                        for item in items:
                            if table_id is not None and str(item.get('tableId')) == str(table_id):
                                share_url = item.get('shareRecipeLink')
                                break
                            elif not table_id and item.get('theName') == recipe_data.name:
                                share_url = item.get('shareRecipeLink')
                                table_id = item.get('tableId')
                                break
                        if share_url:
                            break
                        await asyncio.sleep(0.4)
                    except Exception as fe:
                        print(f'[WARN] 레시피 공유 URL 조회 중 경고: {fe}')
                        break
        print(f'[CLOUD] 레시피 업로드 완료: ID = {table_id or resp_data}, ShareURL = {share_url}')
        return {'success': True, 'recipe_id': str(table_id or resp_data or 'OK'), 'share_url': share_url}
    except Exception as e:
        print('[WARN] 레시피 업로드 예외 발생:')
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'업로드 실패 원인: {str(e)}')

def extract_share_id(url_or_id: str) -> str:
    s = url_or_id.strip()
    if 'id=' in s:
        parsed = urllib.parse.urlparse(s)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'id' in qs and len(qs['id']) > 0:
            return qs['id'][0]
    return urllib.parse.unquote(s)

def fetch_xbloom_shared_recipe(url_or_id: str) -> Dict[str, Any]:
    share_id = extract_share_id(url_or_id)
    if not share_id:
        raise ValueError('유효한 xBloom 공유 ID 또는 URL이 아닙니다.')
    api_url = 'https://client-api.xbloom.com/RecipeDetail.html'
    payload = {'tableIdOfRSA': share_id, 'interfaceVersion': 19700101, 'skey': 'testskey'}
    headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        raise RuntimeError(f'xBloom 클라우드 서버 통신 오류: {str(e)}')
    if data.get('result') != 'success' or not data.get('recipeVo'):
        err_info = data.get('info') or '레시피를 찾을 수 없습니다.'
        raise ValueError(f'클라우드 레시피 조회 실패: {err_info}')
    vo = data['recipeVo']
    raw_pours = vo.get('pourList', [])
    sorted_pours = sorted(raw_pours, key=lambda p: p.get('tableId', 0))
    steps = []
    for p in sorted_pours:
        pat_code = p.get('pattern', 1)
        if pat_code == 2:
            pattern = 'spiral'
        elif pat_code == 3:
            pattern = 'ring'
        else:
            pattern = 'center'
        raw_temp = p.get('temperature', 93)
        try:
            temp_val = int(round(float(raw_temp)))
        except Exception:
            temp_val = 93
        raw_vol = p.get('volume', 50)
        try:
            water_val = int(round(float(raw_vol)))
        except Exception:
            water_val = 50
        raw_wait = p.get('pausing', 15)
        try:
            wait_val = int(round(float(raw_wait)))
        except Exception:
            wait_val = 15
        raw_flow = p.get('flowRate', 3.0)
        try:
            flow_val = round(float(raw_flow), 1)
        except Exception:
            flow_val = 3.0
        vib_before = p.get('isEnableVibrationBefore') == 1
        vib_after = p.get('isEnableVibrationAfter') == 1
        steps.append({'temp': temp_val, 'water': water_val, 'wait': wait_val, 'flow': flow_val, 'pattern': pattern, 'agitation_before': vib_before, 'agitation_after': vib_after})
    try:
        dose_val = int(round(float(vo.get('dose', 15))))
    except Exception:
        dose_val = 15
    try:
        grind_val = int(round(float(vo.get('grinderSize', 45))))
    except Exception:
        grind_val = 45
    grind_enabled = vo.get('isSetGrinderSize') == 1
    raw_rpm = vo.get('rpm', 80)
    try:
        rpm_val = int(raw_rpm)
        if rpm_val not in [60, 70, 80, 90, 100, 110, 120]:
            rpm_val = 80
    except Exception:
        rpm_val = 80
    return {'name': vo.get('theName') or 'Shared Brew', 'dose': dose_val, 'grind_size': grind_val, 'grind_enabled': grind_enabled, 'grind_rpm': rpm_val, 'interval_sync': False, 'steps': steps, 'share_member_name': data.get('shareMemberName') or '', 'share_member_head': data.get('shareMemberHead') or '', 'share_recipe_link': vo.get('shareRecipeLink') or url_or_id}

@app.post('/api/cloud/fetch-shared-recipe')
async def api_fetch_shared_recipe(req: FetchSharedRecipeRequest):
    try:
        recipe_data = fetch_xbloom_shared_recipe(req.url)
        print(f"[CLOUD SHARE] 공유 레시피 성공적으로 파싱: '{recipe_data['name']}' (공유자: {recipe_data.get('share_member_name')})")
        return {'success': True, 'recipe': recipe_data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'공유 레시피 가져오기 실패: {str(e)}')

@app.get('/')
async def serve_index():
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={'message': 'static/index.html 파일을 찾을 수 없습니다.'})
app.mount('/', StaticFiles(directory=STATIC_DIR), name='static')
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='xBloom bleUI Web Server')
    parser.add_argument('-p', '--port', type=int, default=8000, help='서버 포트 번호')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='호스트 주소')
    args = parser.parse_args()
    print(f'\n========================================================')
    print(f'  xBloom bleUI v0.8.1 Server Started')
    print(f'  - Local URL:   http://localhost:{args.port}')
    print(f'  - Network URL: http://0.0.0.0:{args.port}')
    print(f'========================================================\n')
    uvicorn.run('server:app', host=args.host, port=args.port, reload=True)
