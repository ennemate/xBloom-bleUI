# Roadmap

Rough direction for `xbloom-ble` — not commitments, and PRs on any of these are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## 🚨 Top Priority (Next Focus)

- [x] **Wake-up Scheduled Auto-Brewing (아침 모닝콜 연동 자동 예약 브루잉) [완료]**:
  - **Auto Wake-up**: Automatic machine wake-up from low-power sleep via `0xA4` session start frame and automatic BLE reconnect pipeline.
  - **Pre-flight Tank Diagnosis**: Real-time water tank supply verification via static float switch (`0x56` query -> `0x0C NO_WATER` check) at scheduling time without running motors.
  - **Full Pipeline Execution**: Background async scheduler (`LocalNotifications` / `allowWhileIdle: true` on mobile, REST `/api/schedule` on server) executing 4-frame recipe staging (`0xA4` -> `0xA6` -> `0xA8` -> `0x41`), arming commit (`0x42`), and motor-load safety defense (`0x0F NO_BEANS` immediate abort).
  - **Morning Alert**: Sound effect / completion chime notification trigger upon `0x24` (Coffee Ready) state.

- [ ] **Complete Machine Control & Hardware Care Center (공식 앱 대체 완결판: 머신 제어 & 하드웨어 케어 센터) [기획 완료]**:
  - **기본 머신 설정 & 환경 제어 (Basic Device Control)**:
    - **모드 원격 전환**: 다이얼 조작 없이 자동 모드(A/B/C) vs 프로 모드 원클릭 토글 (`buildSetMode`).
    - **단위 설정 (Unit & Temp)**: 머신 전면 LED 디스플레이 및 수율 표시 단위(`g` / `ml` / `oz`) 및 수온 표시(`°C` / `°F`) 변경 (`DeviceUnitBleModel`).
    - **수원 전환 (Water Source)**: 후면 물탱크(Water Tank) vs 언더싱크 직수 튜브(Plumb-in Direct Tap) 유로 밸브 원격 전환 (`/app/device/postWaterFeed`).
    - **누적 사용 통계 & 정보**: 누적 사용 일수 표시 및 머신 3대 MCU(`HWWMCU`, `PannelMCU`, `PowerMCU`) 펌웨어 버전, MAC, 일련번호 조회.
    - **디스플레이 & 슬립**: 머신 전면 LED 도트 매트릭스 밝기 조절 및 대기 모드(Standby Sleep) 타이머 설정.
  - **고급 하드웨어 튜닝 & 영점 캘리브레이션 (Advanced Hardware Calibration)**:
    - **추출 반경 미세 조정 (Set Pouring Radius)**: 회전 노즐 모터의 반경 계수(Radius mm)를 보정하여 드리퍼 정중앙으로 물줄기 원점 튜닝 (`/app/device/setPouringRadius`).
    - **도크 암 진동 진폭 설정 (Dock Arm Vibration Amplitude)**: 드리퍼 거치대의 셰이킹 교반 모터 최소/최대 진폭 강도(Amplitude %) 세팅 (`/app/device/setVibrationAmplitude`).
    - **내장 저울 영점 보정 (Scale Calibrate)**: 드립 트레이 로드셀의 영점(Tare) 및 100g 분동 스팬(Span) 캘리브레이션 위저드 (`CalibrateScale`).
    - **그라인더 영점 보정 (Grinder Calibrate)**: 48mm 코니컬 버가 맞닿는 기계적 0점을 머신 모터가 스스로 탐색하여 분쇄 간극을 재정렬하는 시퀀스 (`CalibrateGrinderJ20`).
  - **유지보수 & 위생 관리 파이프라인 (Maintenance & Hygiene)**:
    - **탈수석 / 디스케일링 모드 (Descaling Pipeline)**: 구연산 세척액 투입 ➔ 고온 유로 순환 배출 ➔ 헹굼수 투입 ➔ 헹굼 배출의 3단계 안내 UI 및 머신 배관 스케일 제거 시퀀스 (`DescaleJ20Activity`).
    - **수동 온수 배출 탭 (Hot Water Tap / Manual Feed)**: 차(Tea) 추출이나 컵 예열, 물탱크 잔수 비우기를 위해 원하는 수온과 목표 용량으로 물만 즉시 배출하는 독립 출수 기능.
  - *안전 정책(Safety Guard): OTA 펌웨어 업데이트는 통신 단절로 인한 기기 브릭(벽돌) 방지를 위해 공식 앱 전용으로 격리.*


## Cross-platform

The library is developed and tested on **Linux (BlueZ)**. `bleak` also supports macOS
(CoreBluetooth) and Windows (WinRT), but those are unproven here.

- [x] Run the pure-Python test suite on **macOS + Windows** in CI (the `cross-platform`
      job — non-blocking for now).
- [ ] Make the cross-platform job **required** once it's reliably green.
- [ ] **Real hardware** brew tested on macOS and Windows (community help welcome — attach
      a scrubbed BLE capture; see [`docs/REVERSE-ENGINEERING.md`](docs/REVERSE-ENGINEERING.md)).
- [ ] Document any platform-specific BLE quirks (permissions, adapter selection).

## First-run experience

- [x] **Config file** (`config.yaml`): saved machine address, recipes-dir override, default
      scale-on. (`xbloom config show`/`path`.)
- [x] **Pair once:** `xbloom init` scans → pick machine → saves the address (later launches skip
      the scan).
- [x] **Cloud login in setup** — `xbloom init` (and `xbloom cloud login`) exchange email+password
      for a token cached `0600` in the state dir; the password is never stored.
- [x] **`xbloom doctor`** — checks config, dirs, deps, token perms (and `--scan` the machine).
- [ ] **Seed recipes** on first run — bundle a few starters, and/or offer "import from your
      xBloom app account" (the cloud client already exists).
- [ ] **Textual first-run wizard** — auto-offer `init` from the TUI when no config exists on a TTY
      (today `init` is CLI-only; the TUI runs zero-config). Friendly empty state ("`n` to create,
      `i` to import").
- [ ] **Polish the recipe editor** — the grid layout is cramped/rough (misaligned labels,
      tiny per-pour cells); make it a cleaner, more legible form.

## Persistence

- [x] **Hold the BLE connection open** for the TUI session (connect on launch + reuse across
      brews, transparent reconnect on drop, `o` connect/disconnect toggle, `auto_connect` config
      default + `--no-auto-connect`) — brews skip the per-brew connect + handshake.
- [x] Move recipes/history/slots/config/token to **stable per-user dirs** via `platformdirs`
      (config / data / state, `XBLOOM_*_DIR` overrides, XDG-on-macOS), instead of deriving from the
      recipes-dir parent. The cached cloud token migrates from the pre-2.2 `~/.config/xbloom-ble/`
      location. `--recipes DIR` still keeps slots/history adjacent (external-generator compat).

## Protocol / telemetry

- [x] Decode the live **water + coffee scale streams** (TYPE `0x4b` water / `0x15` coffee).
- [x] Complete a brew on the **`0x24` "coffee ready"** state (not cup-off).
- [ ] Confirm the finer pour phases from the command echoes (`0x3a`/`0x3b`/`0x3e`/`0x3f`/`0x40`)
      — e.g. surface "bloom / pour 1 / pour 2 / drain" from the `0x3e` pour counter.
- [ ] Captures/decodes for **other firmware versions** (this targets `V12.0D.500`).

## Nice-to-haves

- [ ] Home Assistant / ESPHome integration built on the pure `protocol`/`client` layers.
- [ ] Export brew history (CSV/JSON) and a per-brew extraction summary.
- [ ] **One-Click Brewing Report Card (Export Share Card as PNG)**: Render a specialty coffee style high-res summary card (bean name, recipe params, brew time, yield, mini flow curve) via HTML Canvas for instant clipboard copy and social sharing.
- [ ] **SCA Golden Cup Control Chart (Virtual TDS & Extraction Yield Calculator)**: Automatic calculation of estimated TDS and Extraction Yield (%) plotted on the 4-quadrant SCA matrix using real telemetry (dose, cup yield, retained water).
- [ ] **Brewing History A/B Overlay (Dialing-in Overlay)**: Multi-selection of history records to overlay real-time flow rate curves, parameter diffs, and sensory radar charts side-by-side.
- [ ] **Global Roastery Home Recipes Sync (`NoneAuthService`)**: Auto-sync curated recipes from global partner roasteries without login.
- [ ] **Tea Omni-Brewer Mode (`APP_TEA_RECIP_MAKE`)**: Dedicated full tea steeping editor supporting soak times and stepped temperatures.
- [ ] **Smart Home & Siri Integration (Local Webhook REST API)**: Lightweight local REST API endpoints (`/api/quick-brew`, `/api/machine/status`) in `server.py` enabling Apple Shortcuts ("Hey Siri, brew morning coffee"), Home Assistant, and Stream Deck one-touch brewing.
