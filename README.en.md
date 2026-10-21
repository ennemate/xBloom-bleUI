# xBloom bleUI (v0.9.0)

<p align="center">
  <strong>Modern Local Web Dashboard & Real-Time Extraction Controller for xBloom Studio</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.9.0-orange.svg" alt="Version 0.9.0">
  <img src="https://img.shields.io/badge/i18n-7_Languages-brightgreen.svg" alt="i18n Multilingual">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Hardware-xBloom%20Studio-38bdf8.svg" alt="Hardware xBloom Studio">
  <img src="https://img.shields.io/badge/Interface-FastAPI%20%7C%20Web%20WebSocket-success.svg" alt="Interface Web">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
</p>

<p align="center">
  🌐 <strong>Language:</strong>
  <a href="README.md"><strong>한국어 (Korean)</strong></a> | 
  <a href="README.en.md"><strong>English</strong></a>
</p>

<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI Real-Time Extraction Dashboard Dual Chart" width="850">
  <br>
  <em>Real-time Water Pour & Coffee Yield Dual Graph with Smart Flow Rate Detection Pour Markers</em>
</p>

---

## ☕ Introduction

**xBloom bleUI** connects your **xBloom Studio** coffee machine over Bluetooth Low Energy (BLE), allowing you to wirelessly control brewing recipes and visualize extraction telemetry (water temperature, pour volume, yield weight, ratio) in real time via a web browser on your PC, tablet, or smartphone.

---

## ⚡ Key Highlights & Differences from Original (`xbloom-ble`)

| Feature | Original (`xbloom-ble`) | **xBloom bleUI (This Project)** |
| :--- | :--- | :--- |
| **Auto Update** | Manual git pull or reinstall | **One-click GitHub Auto-Update with 100% user data protection** |
| **Interface** | Terminal CLI / TUI (Textual) | **Modern Responsive Web Dashboard (Dark/Light themes, Custom Wallpaper)** |
| **Extraction Sync** | Timer runs during bean grinding | **Grind & Brew 2-phase separation (00:00 timer starts upon water flow)** |
| **Pour Markers** | Fixed time offset estimate | **Smart Flow & Scale Detection (Real-time pin badges & dashed markers)** |
| **Hand-Drip Intervals** | Simple machine wait | **Automatic interval overhead calculation & duplicate deduction protection** |
| **Cloud Integration** | One-way recipe push | **Two-way sync, web share URL generation, & URL import parsing** |
| **Pre-Ground Mode** | Grind size 0 error prone | **Full official specification compliance (`isSetGrinderSize: 2`, Grind OFF)** |
| **Machine Slots** | CLI slot write | **A / B / C physical button remote flash programming** |
| **Brew Archive** | Session lost on exit | **Permanent local brew history, dual chart restore, & one-click re-brew** |
| **Multilingual (i18n)** | English only | **7 Languages (EN, KO, JA, ZH-TW, ZH-CN, DE, FR) with specialty barista terms** |

---

## 🌟 Screenshots & Features

### 1. 📊 Real-Time Brewing Dashboard
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="Dashboard Dual Chart" width="800">
</p>

- **8 Telemetry Metrics**: Live water temperature, extraction timer, water pour, coffee yield, flow rate, actual ratio, target ratio, and dose.
- **Dual Live Curve Chart**: Real-time water poured vs. liquid extracted with cubic spline smoothing and smart pour markers.

### 2. 🎛️ Recipe Studio
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="Recipe Studio" width="800">
</p>

- Full grinder control (grind size 10–100, motor 60–120 RPM).
- Pattern selection: Center, Spiral, Ring.
- Dual vibration agitation: Pre-pour bed leveling and post-pour extraction agitation.

### 3. 📋 Preset Slots & Local Recipe Management
<p align="center">
  <img src="docs/img/server-recipes.png" alt="Server Recipes" width="600">
</p>

- Browse, load, or delete recipes stored on the local server (`recipes/`).
- Flash program machine physical buttons (A, B, C) directly from the browser.

### 4. 📜 Permanent Brew History & Chart Archiving
<p align="center">
  <img src="docs/img/brew-history.png" alt="Brew History" width="800">
</p>

- Complete brewing history with tasting notes, bean details, and restored interactive dual charts.

---

## 📦 Quick Start

### Option A. Windows Standalone Portable (Recommended)
1. Download `xBloom-bleUI-v0.9.0-Windows-Portable.zip` from [Releases](https://github.com/ennemate/xBloom-bleUI/releases).
2. Extract the ZIP to your desired directory.
3. Double-click **`run.bat`** (Embedded Python 3.10 is pre-configured; no installation needed).

### Option B. Source Code (Cross-Platform)
```bash
git clone https://github.com/ennemate/xBloom-bleUI.git
cd xBloom-bleUI
pip install -r requirements.txt
python run.py
```
Open `http://localhost:8000` in your browser.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
