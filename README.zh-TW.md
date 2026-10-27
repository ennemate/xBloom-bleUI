# xBloom bleUI (v1.0.2)

<p align="center">
  <strong>專為 xBloom Studio 打造的獨立 Android 原生 App 與本機網頁控制器</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.2-orange.svg" alt="Version 1.0.2">
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
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI 即時沖煮儀表板雙曲線圖" width="850">
  <br>
  <em>即時注水量 (Water Pour) 與杯中萃取液 (Coffee Yield) 雙曲線圖＆智慧流速感應注水標記</em>
</p>

---

## ☕ 專案簡介

**xBloom bleUI** 透過低功耗藍牙 (Bluetooth LE) 與精品咖啡機 **xBloom Studio** 建立連線，讓您可以在智慧型手機或電腦上遠端控制沖煮參數，並將萃取數據（水溫、注水量、萃取量、粉水比）以動態雙曲線圖即時呈現。

除了提供跨平台網頁介面外，亦支援無需電腦即可由手機直接連線的 **獨立 Android 原生 App (`APK`)**。結合預約自動沖煮、旁路給水 (Bypass) 控制、大容量粉量支援與 AI 配方輔助功能，提供更靈活便捷的手沖咖啡控制體驗。

---

## 👥 貢獻者與致謝 (Contributors & Credits)

本專案的持續演進仰賴開源社群的分享與合作。

| 個人頭像 | 貢獻者 | 角色與主要貢獻 |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)**<br>*(Original Author)* | • 原作 **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** 專案創始作者<br>• xBloom 藍牙通訊協定逆向工程與核心封包解析基礎建置 |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** 獨立 Android 原生 App (APK) 與跨平台全端架構設計<br>• 晨間預約自動沖煮（Android Doze 深度休眠喚醒與前景常駐服務）<br>• 旁路給水 (Bypass) 硬體控制與 20g/40g 大容量粉量配方流程<br>• AI 配方擷取與實測遙測連動 AI 咖啡師實驗室<br>• 網頁與行動端 Chart.js 即時雙曲線圖表與智慧流速感應注水標記<br>• 磨豆與注水計時器同步、手沖區間時間補償、官方雲端雙向同步 |

---

## 主要功能 (Core Features)

### 1. 📱 獨立 Android 原生 App (Standalone Android App)

<p align="center">
  <img src="docs/img/mobile-app-preview.png" alt="xBloom bleUI 行動 Android 獨立 App 畫面" width="380">
  <br>
  <em>無需電腦、由智慧型手機單獨直接透過藍牙控制機身的 Android 原生 App</em>
</p>

無需開啟電腦，只要在 Android 手機上安裝應用程式，即可獨立連線並控制咖啡機的正式原生安裝包（`APK`）。

* **完全脫離電腦，藍牙直接連線控制**:
  * 手機內部原生內建純 JavaScript 開發的 xBloom BLE 二進位通訊引擎（`protocol.js`）與行動端本機後端。
  * 啟動 App 即可一鍵搜尋並連線周圍的 xBloom Studio，無需 Python 伺服器中繼，隨時隨地完成即時沖煮、配方編輯與機器控制。
* **官方雲端帳號直接同步**:
  * 可在手機 App 內直接登入 xBloom 官方帳號，一鍵載入雲端專屬配方或將新創作上傳備份。
* **無縫後台遙測與即時通知**:
  * 萃取過程中即使關閉螢幕或切換應用，返回時也能完整還原從0秒累積至今的萃取曲線；狀態列通知可即時查看注水量與萃取量。
* **正式開發者簽章保護**:
  * 採用永久開發者金鑰（`bleui-release.jks`）與 Android APK Signature Scheme v2 完整簽署，安裝安全可靠。
* **行動端最佳化響應式介面**:
  * 針對手機螢幕寬度量身打造單行頂部導航列、清晰醒目的連線狀態徽章，以及防誤觸底部手勢導覽條的安全區域間距。
* **與桌面電腦使用者完美相容**:
  * 偏好大螢幕操作的使用者，依然可以透過 Windows 免安裝綠色便攜版或網頁瀏覽器，在電腦螢幕上享有同等流暢的完整功能。

---

### 2. ⏰ 晨間喚醒 無人預約自動沖煮 (Wake-up Scheduled Auto-Brew)

<p align="center">
  <img src="docs/img/auto-brew-modal.png" alt="預約自動沖煮設定彈窗" width="700">
  <br>
  <em>預約時間選擇器與晨間沖煮事前準備確認清單</em>
</p>

在忙碌早晨的指定時刻，咖啡機自動喚醒並為您沖煮好一杯新鮮香醇手沖咖啡的無人自動排程系統。

* **自動喚醒 Android Doze 深度休眠**:
  * 即使手機處於螢幕關閉、鎖定螢幕或深度休眠狀態，系統原生鬧鐘管理員（`AlarmManager`）仍能在設定時刻準時喚醒應用程式並啟動沖煮。
  * 沖煮過程中啟動前景常駐服務（`BrewForegroundService`），切換應用程式或關閉螢幕也不會中斷藍牙連線，確保即時數據完整紀錄。
* **晨間沖煮事前準備確認清單**:
  * 提供咖啡豆投放、咖啡杯就位與水箱加水的貼心確認提醒，協助您安心完成無人預約沖煮。
* **單次安全機制與歷史封存**:
  * 預約啟用後僅會在指定時間執行一次，沖煮完成後自動重設為待機狀態，防止誤觸重覆執行。
  * 沖煮完成時歷史記錄卡將自動標記 `[⏰ 預約]` 專屬徽章，完整雙曲線圖永久封存。
* **支援 PC 本機排程**:
  * 桌面電腦使用者亦可透過背景排程服務，在指定時間準確執行自動沖煮。

---

### 3. 🧊 旁路給水 (Bypass, 補水加水) 控制＆咖啡粉量 (Dose) 上限解除

<p align="center">
  <img src="docs/img/bypass-water-studio.png" alt="配方工作室旁路給水設定與粉量調整畫面" width="800">
  <br>
  <em>不經過濾杯、直接向分享壺注水的旁路給水開關與大容量咖啡粉設定</em>
</p>

為滿足更多精品手沖配方變化，全面拓展了咖啡機硬體馬達的控制自由度。

* **支援旁路給水 (Bypass)**:
  * 濾杯手臂移至側面，讓純熱水直接注入分享壺而不經過咖啡粉層，實現專業的 Bypass 補水加水流程。
  * 可在配方工作室中自由調配濃淡度（提升純淨度 Clean Cup）、冰咖啡萃取，或美式手沖配方。
* **解除粉量 (Dose) 上限 (20g / 40g 大容量)**:
  * 解除原先 18g 的輸入上限，支援 20g、40g 等雙人份或大容量沖煮配方，並維持精確的粉水比換算與傳輸。

---

### 4. 🧠 智慧 AI 配方擷取＆即時 AI 咖啡師實驗室

<p align="center">
  <img src="docs/img/ai-recipe-extract.png" alt="AI 影片與網頁連結配方解析彈窗" width="700">
  <br>
  <em>將咖啡沖煮影片連結或配方文字一鍵轉換為機器參數的 AI 解析彈窗</em>
</p>

<p align="center">
  <img src="docs/img/ai-barista-lab.png" alt="即時遙測數據連動 AI 咖啡師實驗室彈窗" width="700">
  <br>
  <em>根據真實萃取遙測數據診斷風味並一鍵套用配方修正</em>
</p>

結合先進 AI 語言模型，讓複雜專業的手沖配方調整變得無比簡單精準。

* **影片與網頁連結自動解析配方**:
  * 輸入咖啡教學影片連結或網頁網址，AI 會自動分析字幕與文章內容，提取水溫、水量、注水手法及間隔時間，轉換為標準配方。
  * 單篇內容若同時介紹熱沖、冰沖或不同人份，系統會智慧分拆，供您自由挑選。
  * 精確將 EK43、Comandante C40、Fellow Ode 等主流磨豆機刻度或微米（µm）數據換算為 xBloom 機身格數。
  * 點擊 `[載入至工作室]` 即可將全部參數一鍵填入編輯器。
* **即時 AI 咖啡師實驗室**:
  * 品嚐剛沖煮完的咖啡後，只需給予「尾韻偏苦」或「想增強果酸」等簡單回饋，AI 即可分析萃取原因。
  * 不僅僅是理論建議，更會結合剛剛完成的 **實際注水耗時、注水量、電子秤萃取率（歷史記錄）** 等實測數據精準診斷。
  * 咖啡師建議的修正方案（微調刻度、調降後段水溫、縮短間隔等），點擊 `[一鍵套用修復]` 即可直接寫入配方。
* **支援最新旗艦 AI 模型**:
  * 正式支援 **Google Gemini 3.8 Flash** 與 **OpenAI GPT-4o**，可於設定面板中自由切換。
* **經嚴謹萃取物理動態驗證**:
  * 包含增加粉量時的粉層水頭阻力力學、多輪修正收斂性等決策邏輯，皆預先通過驗證測試套件驗證。

---

## 功能比較表

| 功能範疇 | 底層通訊函式庫 (`xbloom-ble`) | **xBloom bleUI (v1.0.2)** |
| :--- | :--- | :--- |
| **執行平台** | 終端機命令列 CLI / TUI (Linux 為主) | **獨立 Android 原生 App (APK) ＋ 跨平台 PC 網頁儀表板** |
| **電腦依賴性** | 必須仰賴電腦 Python 環境 | **手機獨立運作（完全無需電腦，手機藍牙直接連線控制）** |
| **自動沖煮** | 不支援 | **晨間鬧鐘喚醒 無人預約自動沖煮（Doze 喚醒與背景無人完工）** |
| **補水控制** | 不支援 | **旁路給水 (Bypass) 與 20g/40g 大容量粉量支援** |
| **AI 智慧功能** | 不支援 | **影片/網址 AI 配方解析 ＆ 實測數據連動 AI 咖啡師實驗室** |
| **萃取動態視覺化** | 終端機 TUI 基礎遙測圖表 | **網頁/行動端高解析 Chart.js 雙曲線圖（注水量 vs 萃取液量）＆智慧流速標記** |
| **手沖區間間隔** | 機身標準等待(`wait`)秒數輸入 | **依總經過時間自動計算注水耗時補償，並轉換為精準待機時間** |
| **雲端同步** | 單向配方傳送 | **雙向同步 ＋ 官方網頁分享連結生成 ＋ 外部分享連結自動解析** |
| **沖煮歷史保存** | 僅即時階段監控 | **本機永久歷史封存、雙曲線圖完整重現、一鍵複製再沖** |
| **自動更新** | 手動 git pull 或重新下載 | **GitHub Releases 一鍵無損自動更新（使用者資料保留）** |
| **多國語系 (i18n)** | 英文為主 | **全球 7 種語系支援（繁體中文、簡體中文、日本語、한국어、English、Deutsch、Français）** |

---

## 主要功能與畫面導覽

### 1. 即時沖煮儀表板
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="即時沖煮儀表板畫面" width="800">
</p>

* **水溫 / 時間 / 注水量 / 萃取量 4 大即時數據**: 以 0.1 秒頻率接收機身遙測封包。
* **動態雙曲線圖表**: 即時繪製注水量 (Water Pour) 與杯中萃取量 (Coffee Yield)，支援平滑曲線運算。
* **智慧流速與電子秤注水標記**: 即使因加熱延遲或攪拌使出水時間推遲，系統能自動偵測電子秤重量增加的真實瞬間，在圖表上繪製垂直虛線與階段標籤（`1st 00:00`, `2nd 00:40`...）。
* **粉水比自動換算**: 依據即時給水量與咖啡粉量，自動更新當前粉水比（例如 `1 : 16.0`）。
* **緊急停止功能**: 遇到突發狀況時，一鍵立即停止機器動作並安全保留藍牙連線。

---

### 2. 配方工作室 (Recipe Studio)
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="配方工作室編輯畫面" width="800">
</p>

* **精準磨豆機控制與微米(µm)換算標籤**: 刻度 (1~80 clicks) 與 RPM (60~120) 控制，輸入刻度時即時顯示對應微米顆粒尺寸提示（如 `≈ 808 µm`）。
* **豐富注水路徑**: 支援 Center（中心注水）、Ring（同心圓）、Spiral（螺旋外擴）等手法。
* **智慧攪拌 (Agitation)**: 注水前平整粉層攪拌 (`agitation_before`) 與注水後攪拌 (`agitation_after`) 獨立設定。
* **手沖區間精準同步**: 依據目標間隔自動扣除注水所需時間，並在步驟卡片即時顯示換算後的機身待機秒数。
* **標準 YAML 相容**: 支援本機檔案匯出與匯入備份。

---

### 3. 本機配方管理
<p align="center">
  <img src="docs/img/server-recipes.png" alt="伺服器儲存配方清單彈窗" width="600">
</p>

* 快速搜尋本機配方清單，隨時載入編輯或刪除過期配方。
* 遠端將常用配方直接燒錄寫入咖啡機頂部的 **A、B、C 實體快捷按鈕** 快閃記憶體中。

---

### 4. xBloom 官方雲端同步與網頁分享
<p align="center">
  <img src="docs/img/cloud-share.png" alt="雲端上傳成功與網頁分享連結彈窗" width="600">
</p>

* 登入官方帳號後，一鍵將自製配方上傳至 xBloom 官方雲端。
* 上傳成功即刻取得官方網頁分享連結（`https://share-h5.xbloom.com/?id=...`），可直接在瀏覽器預覽或複製給好友。
* 貼上其他咖啡師分享的連結，即可秒速匯入配方工作室。

---

### 5. 沖煮歷史與曲線還原
<p align="center">
  <img src="docs/img/brew-history.png" alt="沖煮歷史與曲線還原彈窗" width="800">
</p>

* 無論正常完成或中途緊急停止的沖煮數據，皆完整保存於本機資料庫。
* 點擊歷史卡片即可重現當時的注水線、萃取線、注水標記點、耗時與粉水比，並可點擊 **[載入此配方至工作室]** 再次沖煮。

---

## 下載與發行版本

請依據您的使用習慣與裝置挑選適合的版本：

| 發行版本 | 適用對象與推薦環境 | 下載連結 |
| :--- | :--- | :--- |
| **Android 正式發行版 APK**<br>*(行動裝置)* | **想擺脫電腦、僅用手機操作咖啡機的使用者**<br>• 下載 APK 檔案後於 Android 手機直接安裝<br>• 具備開發者簽章 (v2 Signature) | [⬇️ 下載 APK (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **Windows 免安裝便攜版**<br>*(PC)* | **不想在電腦上配置 Python 的 PC 使用者**<br>• 完整內建 Python 3.10 嵌入式環境與必要函式庫<br>• 解壓縮後按兩下 `run.bat` 即可啟動 | [⬇️ 下載最新便攜版 (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **原始碼發行版**<br>*(Cross-platform)* | **Windows、macOS、Linux 跨平台相容**<br>• 已安裝 Python 3.10+ 的開發者與使用者<br>• 透過 `git clone` 或下載 Source Code ZIP 直接啟動 | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## 快速開始

### 系統需求
* **行動端**: Android 8.0 (Oreo) 以上，支援 Bluetooth BLE 之智慧型手機
* **PC 端**: Windows 10/11, macOS, Linux (需具備 Bluetooth 4.2 / 5.0 以上藍牙接收器)
* **硬體設備**: xBloom Studio 已開機並處於連線有效範圍內

---

### 途徑 A. 在 Android 手機安裝 APK (行動端推薦)
1. 使用手機瀏覽器前往 [Releases 頁面](https://github.com/ennemate/xBloom-bleUI/releases)
2. 下載 **`xBloom-bleUI-release.apk`** 並依照指示安裝
3. 開啟 App，點選右上角的 **[藍牙連線]** 按鈕，系統將自動搜尋並直接連線附近的 xBloom Studio。

---

### 途徑 B. 執行 Windows 免安裝便攜版 (PC 推薦)
1. 於 [Releases 頁面](https://github.com/ennemate/xBloom-bleUI/releases) 下載 `xBloom-bleUI-v1.0.2-Windows-Portable.zip`
2. 解壓縮至任意資料夾
3. 按兩下資料夾內的 **`run.bat`**
   * 內建的 Python 環境將自動帶起伺服器，並自動在預設瀏覽器開啟 `http://localhost:8000`。

---

### 途徑 C. 原始碼跨平台手動執行 (Windows / macOS / Linux)
1. 複製儲存庫或下載原始碼：
   ```bash
   git clone https://github.com/ennemate/xBloom-bleUI.git
   cd xBloom-bleUI
   ```
2. 安裝必要相依套件：
   ```bash
   pip install -r requirements.txt
   ```
3. 啟動伺服器（將自動開啟預設瀏覽器）：
   ```bash
   # 透過啟動腳本執行
   python run.py

   # 或直接以 uvicorn 啟動
   python server.py --host 0.0.0.0 --port 8000
   ```
4. 在瀏覽器中造訪 `http://localhost:8000`

---

### 版本更新與使用者資料安全保障

* **一鍵線上自動更新**: 網頁介面上方出現更新提示徽章或前往設定 (⚙️) 點擊 [檢查更新]，即可一鍵安全更新至最新發行版本。
* **使用者資料保留**:
  * 更新過程僅會替換原始碼與前端介面檔案，以下重要使用者資料不會被覆寫或刪除：
    * 📂 `recipes/` (自訂調配配方與實體按鈕預設)
    * 📄 `history.json` (過去所有沖煮歷程與雙曲線圖數據)
    * ⚙️ `config.json` (主題、桌布、雲端帳號等偏好設定)
    * 🐍 `python/` (便攜版內建獨立執行環境)
