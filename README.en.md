# xBloom bleUI (v1.0.1)

<p align="center">
  <strong>Standalone Android App & Local Web Controller for xBloom Studio Coffee Machines</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.1-orange.svg" alt="Version 1.0.1">
  <img src="https://img.shields.io/badge/Platform-Android%20APK%20%7C%20Web-blue.svg" alt="Platform Android and Web">
  <img src="https://img.shields.io/badge/Hardware-xBloom%20Studio-38bdf8.svg" alt="Hardware xBloom Studio">
  <img src="https://img.shields.io/badge/i18n-7_Languages-brightgreen.svg" alt="i18n Multilingual">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License GPLv3">
</p>

<p align="center">
  🌐 <strong>Language:</strong>
  <a href="README.md"><strong>한국어 (Korean)</strong></a> | 
  <a href="README.en.md"><strong>English</strong></a> | 
  <a href="README.ja.md"><strong>日本語</strong></a> | 
  <a href="README.zh-TW.md"><strong>繁體中文</strong></a>
</p>

<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI Real-time Brewing Dashboard Dual Chart" width="850">
  <br>
  <em>Real-time Water Pour & Coffee Yield Dual Curve Chart with Smart Flow Detection Pour Markers</em>
</p>

---

## Introduction

**xBloom bleUI** connects your **xBloom Studio** coffee machine over Bluetooth Low Energy (BLE), allowing you to precisely control machine operations from your smartphone or PC and visualize real-time extraction telemetry (water temperature, water pour, coffee yield, extraction ratio) with dual live curves.

Starting with **v1.0.1**, it supports a **Standalone Android App (APK)** for direct control without a computer, alongside **Scheduled Auto-Brew**, **Bypass Water Control**, and **AI Recipe Extraction & Barista Tuning Guide**.

---

## Contributors & Credits

This project is built upon open-source community contributions.

| Profile | Contributor | Roles & Contributions |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)** | • Creator of the foundational **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** library & core BLE communication protocol |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** Standalone Android App (APK) & web UI development, scheduled brewing & AI recipe features |

---

## Features

### 1. 📱 Standalone Android Native App (APK)

<p align="center">
  <img src="docs/img/mobile-app-preview.png" alt="xBloom bleUI Standalone Android App Screen" width="380">
  <br>
  <em>Standalone Android Native App directly controlling the machine over BLE without a PC</em>
</p>

A dedicated native Android application (`APK`) that eliminates the need to turn on a PC, allowing you to control your xBloom Studio directly from your smartphone.

* **Complete PC Independence & Direct BLE Pairing**:
  * Powered by an embedded pure JavaScript xBloom BLE binary protocol engine (`protocol.js`) and mobile local backend.
  * Connects directly to your machine via Bluetooth upon opening the app—no Python server or PC relay required.
* **Official Cloud Account Sync**:
  * Log in with your official xBloom credentials directly inside the app to load personal cloud recipes or upload new creations.
* **Permanent Developer Signing**:
  * Pre-signed with an official developer key (`bleui-release.jks`) using Android APK Signature Scheme v2 for secure, hassle-free installation.
* **Mobile-Optimized Responsive UX**:
  * Single-row compact header, quick-glance status badges, and safe-area padding avoiding gesture bar interference.
* **Seamless Desktop Companion**:
  * Desktop users can continue enjoying the wide-screen experience via Windows Standalone Portable or standard web browsers.

---

### 2. ⏰ Wake-up Scheduled Auto-Brew

<p align="center">
  <img src="docs/img/auto-brew-modal.png" alt="Wake-up Scheduled Auto-Brew Modal" width="700">
  <br>
  <em>Scheduled time picker and morning brew pre-flight checklist</em>
</p>

An automated morning brew pipeline that wakes the machine up at your designated time to brew fresh specialty coffee.

* **Android Doze-Bypass Alarm & Screen Wake**:
  * Even in deep sleep (Doze mode) or with the screen locked, the native `AlarmManager` wakes the device on the exact second.
  * `BrewForegroundService` guarantees uninterruptible Bluetooth telemetry recording throughout the entire extraction.
* **Pre-flight Preparation Checklist**:
  * Provides an intuitive checklist reminder for coffee beans, cup placement, and water tank fill to ensure safe, unattended morning brewing.
* **One-shot Safety & History Archiving**:
  * Triggers once at the scheduled time and safely disarms upon completion.
  * Brew records automatically receive a `[⏰ Scheduled]` badge with full dual-curve graph data.
* **Desktop Background Scheduler**:
  * PC users running local home servers benefit from an automatic background scheduler executing at the scheduled time.

---

### 3. 🧊 Bypass Water Control & Dose Limit Removal

<p align="center">
  <img src="docs/img/bypass-water-studio.png" alt="Recipe Studio Bypass Water and Dose Settings" width="800">
  <br>
  <em>Bypass toggle dispensing water directly into carafe and large-dose 20g brewing settings</em>
</p>

Expands hardware motor control capabilities for advanced specialty coffee brewing recipes.

* **Hardware Bypass Water Delivery**:
  * Moves the dispenser off-center to deliver pure hot water straight into the server without passing through the coffee bed.
  * Perfect for concentration adjustment (clean cup), iced pour-overs, and Americano-style recipes.
* **Dose Limit Removal (20g / 40g Capacity)**:
  * Overcomes the traditional 18g limitation, enabling full-ratio recipes for 20g, 40g, and multi-cup brewing.

---

### 4. 🧠 Intelligent AI Recipe Extraction & Real-time AI Barista Lab

<p align="center">
  <img src="docs/img/ai-recipe-extract.png" alt="AI Recipe Extraction Modal" width="700">
  <br>
  <em>Auto-converts video links or recipe text into exact machine parameters</em>
</p>

<p align="center">
  <img src="docs/img/ai-barista-lab.png" alt="Real-time AI Barista Lab Modal" width="700">
  <br>
  <em>Evaluates extraction telemetry to diagnose flavor and apply one-click recipe adjustments</em>
</p>

Cutting-edge AI capabilities make specialty brewing intuitive and scientifically reproducible.

* **Link & Text AI Recipe Conversion**:
  * Paste a coffee brewing video URL, blog link, or clipboard screenshot: the AI transcribes speech/text into water temperatures, volumes, pour patterns, and intervals.
  * Automatically separates multi-recipe content (Hot vs Iced, 1-cup vs 2-cup).
  * Converts generic grind sizes or micron (µm) metrics into exact xBloom physical click numbers.
  * One-click import pushes all parameters directly into Recipe Studio.
* **Real-time AI Barista Lab**:
  * Share sensory feedback like *"a bit too bitter"* or *"needs more brightness"*; the AI evaluates actual **extraction time, water poured, and scale yield data** from your latest brew.
  * Offers tailored adjustments (grind tweaks, late-stage temperature drops, interval padding) applied via `[One-Click Patch]`.
* **Flagship Model Support**:
  * Officially supports **Google Gemini 3.8 Flash** and **OpenAI GPT-4o**.
* **Physically Grounded Decision Layer**:
  * Pre-verified against bed resistance hydrodynamics and multi-turn dialing-in convergence benchmarks.

---

## Feature Comparison

| Feature Domain | Foundation Library (`xbloom-ble`) | **xBloom bleUI (v1.0.1)** |
| :--- | :--- | :--- |
| **Execution Platform** | Terminal CLI & TUI (Linux-focused) | **Standalone Android APK + Cross-platform PC Web Dashboard** |
| **PC Dependency** | PC Python environment required | **Smartphone Standalone (Direct BLE connection from phone)** |
| **Automated Brewing** | Not supported | **Wake-up Scheduled Auto-Brew (Doze-bypass & Background Completion)** |
| **Water Bypass** | Not supported | **Bypass water delivery & 20g/40g large-dose support** |
| **AI Capabilities** | Not supported | **Video/Web Link AI Recipe Extraction & Real-time AI Barista Lab** |
| **Extraction Visualization** | Terminal TUI real-time telemetry graph | **High-resolution Chart.js Dual Curves (Water vs Yield) & Smart Flow Markers** |
| **Hand-Drip Intervals** | Standard pause (`wait`) seconds | **Automatic cumulative interval tracking & overhead subtraction** |
| **Cloud Integration** | One-way recipe upload | **2-way cloud sync + Official Web Share URL generator & parser** |
| **Brew Log Archiving** | Session-only monitoring | **Permanent local history, interactive chart restoration, 1-click re-brew** |
| **Auto Update** | Manual git pull or re-download | **GitHub Release 1-click update with 100% user data preservation** |
| **Multilingual (i18n)** | English based | **Global 7 languages (Korean, English, Japanese, Traditional/Simplified Chinese, German, French)** |

---

## Interface Showcase

### 1. 📊 Real-time Brewing Dashboard
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="Real-time Brewing Dashboard Screen" width="800">
</p>

* **4 Live Metrics**: 0.1s refresh rate for Water Temp, Elapsed Time, Water Poured, and Yield Weight.
* **Dual Live Curves**: Simultaneous tracking of Water Pour and Coffee Yield with spline curve smoothing.
* **Smart Flow Detection Markers**: Accurately detects the exact moment water impacts the scale bed, pinning numbered markers (`1st 00:00`, `2nd 00:35`...).
* **Real-time Ratio Calculation**: Live brew ratio updating (e.g. `1 : 16.0`).
* **Emergency Stop Guard**: Immediate motor shut-off upon emergency button click while preserving BLE connection.

---

### 2. 🎛️ Recipe Studio
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="Recipe Studio Editor" width="800">
</p>

* **Precision Grinder Control**: 1~80 clicks & 60~120 RPM control with real-time micron (`≈ 808 µm`) banner.
* **Pour Patterns**: Center, Ring, and Spiral rotation modes.
* **Smart Agitation**: Separate pre-pour leveling and post-pour agitation settings.
* **Hand-Drip Interval Sync**: Live hints showing actual pause times minus pouring duration.
* **YAML Compatibility**: Local file import and export.

---

### 3. 📋 Saved Recipes
<p align="center">
  <img src="docs/img/server-recipes.png" alt="Saved Recipes Modal" width="600">
</p>

* Manage, search, and recall saved recipes instantly.
* Remotely flash recipes into machine physical **A, B, C hardware buttons**.

---

### 4. ☁️ xBloom Cloud Sync & Web Sharing
<p align="center">
  <img src="docs/img/cloud-share.png" alt="Cloud Upload Success and Web Share Modal" width="600">
</p>

* 1-click sync with your official xBloom cloud account.
* Auto-generates official share URLs (`https://share-h5.xbloom.com/?id=...`).
* Paste any shared xBloom URL to import directly into the Studio.

---

### 5. 📜 Permanent Brew History Archive
<p align="center">
  <img src="docs/img/brew-history.png" alt="Brew History and Chart Restoration Modal" width="800">
</p>

* Archives every brew session, including emergency-stopped runs.
* Full dual-curve restoration with pour markers and 1-click recipe reload.

---

## 📦 Downloads & Releases

Choose the distribution suited for your setup:

| Edition | Recommended For | Download Link |
| :--- | :--- | :--- |
| **📱 Android Release APK**<br>*(Highly Recommended for Mobile ⭐)* | **Control without a PC directly from smartphone**<br>• Download APK & install directly on Android<br>• Fully signed with v2 Signature Scheme | [⬇️ Download APK (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **🚀 Windows Standalone Portable**<br>*(Recommended for PC ⭐)* | **Zero Python setup required on Windows**<br>• Embedded Python 3.10 runtime & dependencies pre-packaged<br>• Unzip and double-click `run.bat` | [⬇️ Download Portable ZIP (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **💻 Standard Source Edition**<br>*(Cross-platform)* | **Windows, macOS, Linux**<br>• Python 3.10+ installed<br>• Run via `git clone` or source ZIP | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## Quick Start

### System Requirements
* **Mobile**: Android 8.0 (Oreo) or higher with Bluetooth BLE
* **PC**: Windows 10/11, macOS, Linux (Bluetooth 4.2 / 5.0+ adapter required)
* **Machine**: xBloom Studio powered on and in range

---

### Method A. Install APK on Android (Recommended)
1. Open [Releases Page](https://github.com/ennemate/xBloom-bleUI/releases) on your smartphone.
2. Download **`xBloom-bleUI-release.apk`** and install.
3. Open the app and tap **[Connect BLE]** at the top right to discover and pair with your machine.

---

### Method B. Windows Standalone Portable (PC Recommended)
1. Download `xBloom-bleUI-v1.0.1-Windows-Portable.zip` from [Releases](https://github.com/ennemate/xBloom-bleUI/releases).
2. Unzip into any directory.
3. Double-click **`run.bat`**.
   * The server starts automatically and opens your default browser at `http://localhost:8000`.

---

### Method C. Run from Source (Cross-Platform)
1. Clone the repository:
   ```bash
   git clone https://github.com/ennemate/xBloom-bleUI.git
   cd xBloom-bleUI
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python run.py
   ```
4. Access `http://localhost:8000` in your browser.

---

### 🔄 Data-Safe Updates
* **1-Click Update**: Upgrade seamlessly via the top update notification badge or Settings (⚙️).
* **100% User Data Preserved**:
  * Updates never overwrite your user data:
    * 📂 `recipes/` (custom recipes & slot presets)
    * 📄 `history.json` (all past extraction logs & dual curves)
    * ⚙️ `config.json` (themes, wallpaper, cloud settings)
    * 🐍 `python/` (embedded runtime in portable editions)
