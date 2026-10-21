# xBloom bleUI (v0.9.2)

<p align="center">
  <strong>Modern Local Web Dashboard & Real-Time Extraction Controller for xBloom Studio</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.9.2-orange.svg" alt="Version 0.9.2">
  <img src="https://img.shields.io/badge/i18n-7_Languages-brightgreen.svg" alt="i18n Multilingual">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Hardware-xBloom%20Studio-38bdf8.svg" alt="Hardware xBloom Studio">
  <img src="https://img.shields.io/badge/Interface-FastAPI%20%7C%20Web%20WebSocket-success.svg" alt="Interface Web">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
</p>

<p align="center">
  🌐 <strong>Language:</strong>
  <a href="README.md"><strong>한국어 (Korean)</strong></a> | 
  <a href="README.en.md"><strong>English</strong></a> | 
  <a href="README.ja.md"><strong>日本語</strong></a> | 
  <a href="README.zh-TW.md"><strong>繁體中文</strong></a>
</p>

<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI Real-Time Extraction Dashboard Dual Chart" width="850">
  <br>
  <em>Real-time Water Pour & Coffee Yield Dual Curve Chart with Smart Flow Detection Pour Markers</em>
</p>

---

## ☕ Introduction

**xBloom bleUI** connects your **xBloom Studio** coffee machine over Bluetooth Low Energy (BLE), allowing you to wirelessly control brewing recipes and visualize extraction telemetry (water temperature, pour volume, yield weight, ratio) in real time via a web browser on your PC, tablet, or smartphone.

It overcomes existing official mobile app limitations (such as lack of cumulative interval calculations, absence of web share URL parsing, unseparated grind/brew phases, etc.) and provides the ultimate pour-over coffee extraction experience.

---

## 👥 Contributors & Credits

This project thrives on the spirit of open-source sharing and community collaboration.

| Avatar | Contributor | Role & Contributions |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)**<br>*(Original Author)* | • Original **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** author<br>• xBloom Studio Bluetooth LE communication protocol reverse-engineering & core packet decoder design<br>• Machine communication framework & hardware slot control architecture |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate (xBloom bleUI Contributors)](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** web dashboard architecture & full-stack development<br>• Zero-dependency pure Python GitHub one-click auto-updater<br>• Dual live brewing curves (Chart.js) & smart flow detection pour markers<br>• 2-phase separation for Grinding and Brewing with timer synchronization<br>• Hand-drip cumulative interval timing overhead compensation<br>• Official xBloom cloud 2-way sync & web recipe link parser<br>• Permanent brew log archive & Windows Standalone Portable packaging |

> [!NOTE]
> Special thanks to **Janczykkkko** for pioneering the open-source BLE protocol implementation and core communication library that laid the foundation for this project.

---

## ⚡ Core Extensions & Dedicated Web Controller Features

This project adopts **Janczykkkko**'s foundational BLE communication library (`xbloom-ble`) as its core engine, while developing dedicated extensions to deliver an optimal web-based barista workflow and user experience:

| Feature & Domain | Underlying Library (`xbloom-ble`) | **xBloom bleUI (Web Controller Extensions)** |
| :--- | :--- | :--- |
| **Interface (UI)** | Terminal CLI and TUI (Textual) | **Modern responsive web dashboard (Dark/Light themes, custom wallpapers)** |
| **Extraction Phase Sync** | Raw machine telemetry streaming | **2-Phase separation: Grinding vs. Brewing (00:00 timer synced with water flow)** |
| **Flow Detection** | Scale raw weight readings | **Smart Flow Detection: real-time pin badges & dashed line markers** |
| **Pour Intervals** | Standard machine pause (`wait`) in seconds | **Cumulative interval calculation & automatic machine pause conversion** |
| **Cloud Integration** | Basic recipe push function | **Two-way sync + Web share URL generation + External URL import parsing** |
| **Pre-Ground Mode** | Standard recipe payload | **Official app compliance (`isSetGrinderSize: 2`, Grind OFF cleanly rendered)** |
| **Slot Memory** | CLI slot writing commands | **A / B / C physical button remote flash programming from browser** |
| **Brew Archive** | Real-time session monitoring | **Permanent local history, dual curve chart restore, and one-click re-brew** |
| **Auto Update** | Manual git pull or reinstall | **GitHub Releases-based one-click update (100% user data preserved)** |
| **Multilingual (i18n)** | English based | **7 Global languages supported with specialty barista terminology** |

---

### 1. 2-Phase Separation: Grinding vs. Actual Water Delivery
- **Implementation Context**: Recipes utilizing the built-in grinder involve a ~20-25s grinding phase before water begins flowing. bleUI intelligently separates bean grinding from active extraction so the 00:00 timer reflects actual water contact.
- **bleUI Behavior**: Detects the machine's `STARTING (0x22)` grinding state to display **`Grinding Beans ⚙️`**, synchronizing the `00:00` timer and 1st pour marker at the exact instant water begins spraying or the machine transitions to `BREWING`.

### 2. Smart Flow Detection Pour Markers
- Even if heating delays or pre-pour agitation (`agitation_before`) delay water delivery, real-time scale telemetry detects when water actually touches the coffee bed (`pour_weight >= 0.8g`), auto-aligning the 1st pour marker.
- Subsequent pours (2nd, 3rd...) are accurately detected right after scale stabilization plateaus, marked with vertical dashed lines and pin badges (`Pour 1 00:00`, `Pour 2 00:45`...).

### 3. Cumulative Hand-Drip Interval Calculation & Safe Synchronization
- Converts cumulative hand-drip intervals (e.g., 0s 1st, 40s 2nd, 70s 3rd) into machine pauses by automatically subtracting water flow duration and agitation overheads.
- When saving, only the calculated machine pauses are written, avoiding repetitive overhead subtraction when recipes are re-opened.

### 4. Official xBloom Cloud Two-Way Sync & Web URL Parsing
- **Official App Login**: Seamlessly log in with your xBloom email/password to sync custom recipes directly to the cloud.
- **Instant Web Share Link**: Automatically generates shareable URLs (`https://share-h5.xbloom.com/?id=...`) with one-click clipboard copy.
- **One-Click URL Import**: Paste any recipe link or ID to parse parameters (name, dose, grind size, RPM, all pour steps and agitation) into the studio.
- **Full Grind-OFF Support**: Correctly flags `isSetGrinderSize: 2` so cloud recipe pages display "Grind OFF" rather than size 0.

---

## 🌟 Screenshots & Feature Walkthrough

### 1. 📊 Real-Time Brewing Dashboard
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="Real-Time Brewing Dashboard" width="800">
</p>

- **8 Live Telemetry Metrics**: Water temperature, extraction time, water pour, coffee yield, flow rate, actual ratio, target ratio, and dose.
- **Dual Live Curve Chart**: Plots water pour vs. coffee yield with cubic spline smoothing.
- **Emergency Stop Safety**: One-click immediate machine shutdown while maintaining BLE connection.

---

### 2. 🎛️ Recipe Studio
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="Recipe Studio" width="800">
</p>

- **Precision Grinder Control**: Grind size (10~100) and motor RPM (60~120 in increments of 10).
- **Pour Patterns**: Center, Spiral, and Ring patterns fully supported.
- **Dual Agitation**: Independent pre-pour bed leveling and post-pour extraction agitation.
- **YAML Standards**: Export and import standard YAML recipe files.

---

### 3. 📋 Saved Recipes & Machine Slot Presets
<p align="center">
  <img src="docs/img/server-recipes.png" alt="Saved Recipes Modal" width="600">
</p>

- Manage and search local recipe files in `recipes/`.
- Wirelessly program machine physical buttons (**A, B, C**) with preset recipes.

---

### 4. ☁️ xBloom Cloud Sync & Share Links
<p align="center">
  <img src="docs/img/cloud-share.png" alt="Cloud Share Modal" width="600">
</p>

- Upload custom recipes to the official cloud.
- Open generated share URLs in a new browser tab or import recipes shared by other baristas.

---

### 5. 📜 Permanent Brew History & Chart Archiving
<p align="center">
  <img src="docs/img/brew-history.png" alt="Brew History Modal" width="800">
</p>

- Preserves completed and emergency-stopped brew sessions.
- Review past pour curves, markers, tasting notes, and click **[⚡ Load to Studio]** for one-click re-brewing.

---

### 6. 🚀 Pure Python One-Click Auto-Updater
<p align="center">
  <img src="docs/img/auto-update-badge.png" alt="Auto-Update Badge" width="750">
  <br>
  <em>Update notification badge in header (zero startup delay with asynchronous checking)</em>
</p>

<p align="center">
  <img src="docs/img/auto-update-modal.png" alt="Auto-Update Modal" width="550">
  <br>
  <em>One-click update modal with release notes and 100% data preservation</em>
</p>

- **Standalone Operation**: Runs purely on Python standard libraries without requiring Git.
- **100% User Data Protection**: Updates only code files, ensuring `recipes/`, `history.json`, and `config.json` remain untouched.

---

## 📦 Download & Releases

| Edition | Recommended For | Download Link |
| :--- | :--- | :--- |
| **🚀 Windows Standalone Portable** | **General Windows users (No Python installation required)**<br>• Bundles Embedded Python 3.10 and all dependencies<br>• Just extract and double-click `run.bat` | [⬇️ Latest Portable Release](https://github.com/ennemate/xBloom-bleUI/releases) |
| **💻 Source Code Package** | **Windows, macOS, Linux (Cross-Platform)**<br>• For users with Python 3.10+ already installed<br>• Clone or download source archive | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## 🚀 Quick Start

### Method A. Windows Standalone Portable (Recommended)
1. Download `xBloom-bleUI-v0.9.2-Windows-Portable.zip` from [Releases](https://github.com/ennemate/xBloom-bleUI/releases).
2. Extract the archive into any folder.
3. Double-click **`run.bat`**.
   - Starts the server and automatically opens `http://localhost:8000` in your default browser.

---

### Method B. Source Installation (Windows / macOS / Linux)
1. Clone the repository:
   ```bash
   git clone https://github.com/ennemate/xBloom-bleUI.git
   cd xBloom-bleUI
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python run.py
   ```

---

## 📁 Package Directory Structure

```text
xBloom-bleUI/
├── run.bat               # Windows one-click launcher
├── run.py                # Cross-platform auto-browser launcher
├── server.py             # Optimized FastAPI backend server (v0.9.2)
├── requirements.txt      # Python dependencies
├── config.example.json   # Configuration template
├── README.md             # Korean documentation
├── README.en.md          # English documentation
├── README.ja.md          # Japanese documentation
├── README.zh-TW.md       # Traditional Chinese documentation
├── docs/
│   └── img/              # Demonstration screenshots
├── static/
│   └── index.html        # Single-page modern frontend with i18n
├── recipes/              # Local recipe storage
└── xbloom_ble/           # BLE communication & control modules
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## ⚠️ Disclaimer

- This is an **unofficial open-source project** developed for research and hobby purposes. It is not affiliated with or endorsed by TBDx Inc. (xBloom).
- Always ensure safe coffee brewing conditions (adequate water supply, properly positioned cup, etc.) before initiating extraction.
