# xBloom bleUI (v0.9.2)

<p align="center">
  <strong>專為 xBloom Studio 打造的現代化本機網頁儀表板與即時沖煮萃取分析控制器</strong>
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
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI 即時沖煮儀表板雙曲線圖" width="850">
  <br>
  <em>即時注水量 (Water Pour) 與杯中萃取液 (Coffee Yield) 雙曲線圖＆智慧流速感應注水標記</em>
</p>

---

## ☕ 專案簡介

**xBloom bleUI** 透過低功耗藍牙 (Bluetooth LE) 與旗艦級一體式精品手沖機 **xBloom Studio** 連線，讓您可以在電腦、平板或手機的網頁瀏覽器上，遠端精準控制沖煮配方，並將萃取即時數據（水溫、注水量、萃取量、粉水比）以雙曲線圖動態視覺化呈現。

本專案解決了官方行動 App 的諸多限制（如缺乏手沖累積區間計算、無法直接匯入網頁分享連結、磨豆與注水階段未分離等），為咖啡玩家與吧檯咖啡師提供極致的手沖萃取體驗。

---

## 👥 貢獻者與致謝 (Contributors & Credits)

本專案的持續演進仰賴開源社群的無私分享與協同合作。

| 大頭貼 | 貢獻者 | 角色與主要貢獻 |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)**<br>*(Original Author)* | • 原作 **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** 專案創始作者<br>• xBloom Studio 藍牙通訊協定逆向工程與核心封包解碼器架構設計<br>• 咖啡機通訊框架與機身硬體記憶體槽位控制基石 |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate (xBloom bleUI Contributors)](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** 網頁儀表板全端架構與前端 UI 設計<br>• 純 Python 打造的 GitHub Releases 一鍵無損自動升級系統<br>• 即時雙曲線圖表 (Chart.js) 與智慧流速感應注水標記演算法<br>• 磨豆 (Grind) 與實際注水 (Brew) 兩階段分離與計時器完美同步<br>• 手沖累積區間時間自動補償與重複扣除防護機制<br>• xBloom 官方雲端雙向同步與網頁分享連結自動生成／解析匯入<br>• 永久本機沖煮歷史封存與 Windows 免安裝綠色便攜版封裝 |

---

## ⚡ xBloom bleUI 網頁控制器專屬擴充與核心特色

本專案採用 **Janczykkkko** 所開創的傑出 BLE 核心通訊函式庫 (`xbloom-ble`) 作為底層引擎，並在此基礎上為網頁瀏覽器環境自主開發了以下專屬擴充功能，以實現極致的咖啡師操作體驗與萃取視覺化：

| 主要功能與範疇 | 底層通訊函式庫 (`xbloom-ble`) | **xBloom bleUI (網頁控制器專屬擴充)** |
| :--- | :--- | :--- |
| **使用者介面 (UI)** | 終端機命令列 CLI / TUI (Textual) | **現代化響應式網頁儀表板（支援深色／淺色主題、自訂桌布）** |
| **萃取階段視覺化** | 機身遙測原始封包串流接收 | **磨豆 (Grind) 與注水 (Brew) 兩階段分離（00:00 計時器出水校準）** |
| **即時出水偵測** | 電子秤原始重量數據接收 | **智慧流速與電子秤偵測（Smart Flow Detection）即時徽章與標記** |
| **手沖區間支援** | 機身標準等待時間 (`wait`) 秒數輸入 | **依累積時間自動計算注水耗時補償，並轉換為精準機身待機時間** |
| **官方雲端連動** | 基本配方推播功能 | **雙向連動＋自動生成網頁分享網址＋外部分享連結自動解析匯入** |
| **免磨豆規格相容** | 標準配方資料結構傳輸 | **遵循官方標準規格 (`isSetGrinderSize: 2`，磨豆關閉正常顯示)** |
| **機身硬體槽位** | CLI 命令列槽位寫入 | **A / B / C 實體按鍵瀏覽器一鍵遠端無線韌體燒錄** |
| **歷史數據封存** | 沖煮過程即時監控 | **永久本機歷史資料庫、雙曲線圖完整重現、一鍵複製再沖** |
| **自動無損升級** | 手動 git pull 或重新安裝 | **GitHub Releases 連動一鍵無痛升級（100% 完整保留使用者資料）** |
| **研磨度微米（µm）換算** | 僅段數設定 | **基於 48mm 錐刀間隙之理論微米（µm）即時換算與設定開關** |
| **多國語言 (i18n)** | 英文介面為主 | **全球 7 國語言支援＆精品手沖咖啡專業術語全面在地化** |

---

## 🌟 主要功能畫面導覽

### 1. 📊 即時沖煮儀表板
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="即時沖煮儀表板" width="800">
</p>

- **8 大即時遙測指標**: 水溫、萃取計時、注水量、萃取量、流速、實際粉水比、目標粉水比、咖啡豆重量。
- **雙即時曲線圖表**: 以三次樣條平滑曲線精確繪製注水量與下壺萃取量。
- **緊急停止機制**: 遇到異常時可一鍵中斷出水並安全保持藍牙連線。

---

### 2. 🎛️ 配方工作台 (Recipe Studio)
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="配方工作台" width="800">
</p>

- **精密磨豆機控制與微米（µm）即時換算**: 研磨刻度 (10~100) 與馬達轉速 (60~120 RPM)，提供基於 48mm 錐刀規格的理論微米（`≈ 836 µm` 等）即時換算標籤（可於設定中自訂開啟/關閉）。
- **多元注水水流模式**: 支援 Center (中心注水)、Spiral (螺旋旋轉注水) 與 Ring (外圈注水)。
- **雙擾動震動控制**: 獨立設定注水前整粉擾動與注水後萃取擾動。

---

### 3. 📋 本機配方管理與機身記憶體槽位
<p align="center">
  <img src="docs/img/server-recipes.png" alt="已儲存配方清單" width="600">
</p>

- 瀏覽與管理本機 `recipes/` 目錄中的配方檔案。
- 將自訂配方一鍵寫入機器上方的 **A、B、C 實體快捷鍵**。

---

### 4. 📜 永久沖煮歷史與曲線還原
<p align="center">
  <img src="docs/img/brew-history.png" alt="沖煮歷史紀錄" width="800">
</p>

- 完整紀錄每一次萃取數據、曲線、注水標記與風味杯測筆記。
- 點選 **[⚡ 載入至工作台]** 按鈕即可一鍵還原參數重新沖煮。

---

## 📦 下載與安裝版本

| 版本類型 | 推薦對象 | 下載連結 |
| :--- | :--- | :--- |
| **🚀 Windows 免安裝綠色版** | **不熟悉 Python 環境配置的廣大使用者**<br>• 內建 Python 3.10 獨立環境，無須安裝任何軟體<br>• 解壓縮後直接點擊 `run.bat` 即可啟動 | [⬇️ 最新免安裝版下載 (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **💻 原始碼跨平台版** | **Windows, macOS, Linux 跨平台使用者**<br>• 電腦已安裝 Python 3.10 以上環境 | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## 🚀 快速上手 (Windows 免安裝版)

1. 前往 [Releases](https://github.com/ennemate/xBloom-bleUI/releases) 下載 `xBloom-bleUI-v0.9.2-Windows-Portable.zip`。
2. 解壓縮至任意資料夾。
3. 雙擊執行 **`run.bat`**。
   - 系統將自動啟動本機伺服器並在瀏覽器中開啟 `http://localhost:8000`。

---

## 📄 授權條款 (License)

本專案採用 [MIT License](LICENSE) 開源授權條款。

## ⚠️ 免責聲明 (Disclaimer)

- 本軟體為愛好者基於研究目的開發的**非官方開源專案**，並非 TBDx Inc. (xBloom) 的官方軟體。
- 進行沖煮控制時會排出高溫熱水，操作前請務必確認水箱水量充足且接水咖啡杯已就定位。
