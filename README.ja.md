# xBloom bleUI (v1.0.1)

<p align="center">
  <strong>xBloom Studio コーヒーマシンのためのスタンドアロンAndroidアプリ＆ローカルWebコントローラー</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.1-orange.svg" alt="Version 1.0.1">
  <img src="https://img.shields.io/badge/Platform-Android%20APK%20%7C%20Web-blue.svg" alt="Platform Android and Web">
  <img src="https://img.shields.io/badge/Hardware-xBloom%20Studio-38bdf8.svg" alt="Hardware xBloom Studio">
  <img src="https://img.shields.io/badge/i18n-7_Languages-brightgreen.svg" alt="i18n Multilingual">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
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
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI リアルタイム抽出ダッシュボード デュアルチャート" width="850">
  <br>
  <em>リアルタイム注水量(Water Pour)とカップ抽出液(Coffee Yield)のデュアルグラフ＆スマート流速検知プアマーカー</em>
</p>

---

## プロジェクト概要

**xBloom bleUI** は、プレミアムオールインワンコーヒーマシン **xBloom Studio** とBluetooth LEで接続し、スマートフォンやPCからマシンを精密に遠隔制御し、抽出データ（水温、注水量、抽出量、抽出比率）をリアルタイムにデュアルグラフで可視化する統合コーヒーコントロールシステムです。

**v1.0.1** では、PC不要でスマートフォン単独でマシンを操作できる **スタンドアロンAndroidアプリ(APK)** に対応し、指定時刻に合わせた **無人自動予約抽出**、温水のみを直接供給する **バイパス(Bypass)加水制御**、Webリンクと連動する **AIレシピ抽出＆バリスタチューニングガイド** を提供します。

---

## コントリビューター＆クレジット (Contributors & Credits)

本プロジェクトはオープンソースコミュニティの貢献によって支えられています。

| プロフィール | 貢献者 | 役割と主な貢献 |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)** | • 原作 **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** ライブラリおよびコアBLE通信プロトコルの基礎構築 |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** スタンドアロンAndroidアプリ(APK)およびWeb UI開発、予約抽出＆AI機能の実装 |

---

## 主な機能 (Features)

### 1. 📱 スタンドアロンAndroidネイティブアプリ (Standalone Android App)

<p align="center">
  <img src="docs/img/mobile-app-preview.png" alt="xBloom bleUI モバイルAndroidスタンドアロンアプリ画面" width="380">
  <br>
  <em>PC不要でスマートフォン単独でBLE直接制御が可能なAndroidネイティブアプリ画面</em>
</p>

PCを起動する必要なく、スマートフォンにアプリをインストールするだけでマシンを直接制御できる公式Androidネイティブアプリケーション（`APK`）です。

* **PC完全独立＆BLE直接制御**:
  * スマートフォン内部に純粋なJavaScriptベースのxBloom BLEバイナリ通信エンジン（`protocol.js`）とモバイルローカルバックエンドを標準内蔵。
  * 外部PythonサーバーやPCの仲介なしに、アプリ起動後ワンタップでマシンとBluetooth直結し、リアルタイム抽出、レシピ編集、マシン制御をスマートフォン単体で完結します。
* **公式クラウドアカウント直結連携**:
  * スマートフォンアプリ内からxBloom公式アカウントへログインし、クラウドアカウント内のマイレシピを即座に読み込んだり新規アップロードしたりできます。
* **正式な開発者署名を適用**:
  * 恒久的な開発者署名鍵（`bleui-release.jks`）およびAndroid APK Signature Scheme v2署名を完了しており、安全かつ確実にインストールできます。
* **モバイル最適化レスポンシブUX**:
  * スマートフォンの画面幅に合わせた1行ヘッダー、視認性の高いステータスバッジ、画面下部ジェスチャーバーと干渉しないセーフエリアパディングを完備。
* **デスクトップ環境との親和性**:
  * 大画面PC環境を好むユーザーは、Windowsポータブル版やWebブラウザを通じて広々としたモニターでダッシュボードとスタジオを同様に利用できます。

---

### 2. ⏰ 目覚まし連動 無人自動予約抽出 (Wake-up Scheduled Auto-Brew)

<p align="center">
  <img src="docs/img/auto-brew-modal.png" alt="目覚まし連動 無人自動予約抽出モーダル" width="700">
  <br>
  <em>時間設定タイムピッカーおよび水タンク残量自動点検安心インジケーター</em>
</p>

忙しい朝の指定時刻に合わせてマシンが自動で起動し、淹れたてのコーヒーを用意しておく無人予約抽出パイプラインです。

* **スマートフォン省電力(Dozeモード)自動復帰＆定時起動**:
  * 画面消灯やロック画面状態の深いスリープモードでも、ネイティブアラームマネージャー（`AlarmManager`）が画面を点灯しアプリをアクティブ化、指定時刻に寸分の狂いなく抽出を開始します。
  * 抽出中はフォアグラウンドサービス（`BrewForegroundService`）が常駐するため、他アプリへ切り替えたり画面をオフにしてもBluetooth通信が途切れることなく完走します。
* **水タンク残量 事前安全点検 (Pre-flight Check)**:
  * モーターを駆動する前に、静電容量センサー（`0x56`）で水タンクの残水量をチェックします。水不足を検知した場合は空焚きを防ぐため安全に待機します。
* **1回限りの安全動作＆履歴保存**:
  * 予約有効化時は指定時刻に1回のみ安全に動作し、完了後は自動で通常待機に戻ります。
  * 抽出完了時は履歴カードに `[⏰ 予約]` 専用バッジが付与され、リアルタイム抽出曲線が永続アーカイブされます。
* **PC環境自動スケジューラー対応**:
  * デスクトップ環境でもローカルサーバーのバックグラウンドスケジューラーが定刻に正確な無人抽出を実行します。

---

### 3. 🧊 バイパス(Bypass, 注水加水)制御＆豆量(Dose)上限解除

<p align="center">
  <img src="docs/img/bypass-water-studio.png" alt="レシピスタジオ バイパス加水制御および豆量セッティング" width="800">
  <br>
  <em>ドリッパーをバイパスして温水のみを直接注水するバイパストグルおよび大容量豆セッティング</em>
</p>

スペシャルティコーヒーレシピの表現力を広げるため、マシンのハードウェアモーター制御領域を拡張しました。

* **バイパス(Bypass)注水サポート**:
  * ドリッパーアームが側方へ退避し、コーヒー粉の層を通さずにサーバーへピュアな温水のみを直接注水するバイパス加水機能に対応しました。
  * 濃度調整（クリーンカップの確保）、アイスコーヒー、アメリカーノ風レシピをレシピスタジオで自由に設計できます。
* **豆量(Dose)上限解除 (20g / 40g 大容量)**:
  * 従来の18g上限を解除し、20gや40gなどの2人分・大容量ドリップレシピを適切な抽出比率で設定・マシン送信できます。

---

### 4. 🧠 知能型AIレシピ抽出＆リアルタイムAIバリスタ研究所

<p align="center">
  <img src="docs/img/ai-recipe-extract.png" alt="AI動画およびWebリンクレシピ抽出モーダル" width="700">
  <br>
  <em>コーヒー抽出動画リンクやレシピテキストをマシン用パラメータへ自動変換するAI抽出モーダル</em>
</p>

<p align="center">
  <img src="docs/img/ai-barista-lab.png" alt="リアルタイム実測連動AIバリスタ研究所モーダル" width="700">
  <br>
  <em>実測テレメトリデータに基づく味わい診断およびワンクリックレシピ補正</em>
</p>

専門的なコーヒードリップレシピをより簡単かつ精密に扱えるよう、最先端のAI技術を統合しました。

* **動画＆Webリンクからのレシピ自動抽出**:
  * コーヒー抽出動画のURLやWebページアドレスを入力すると、AIが字幕や本文テキストを解析し、段階別の水温、水量、プアパターン、待ち時間をレシピへ自動変換します。
  * 1つのコンテンツ内にホット／アイス、1杯分／2杯分など複数のレシピが含まれている場合でも、個別に分離して希望のレシピを選択可能です。
  * 挽き目表記やミクロン（µm）数値をxBloomマシンの物理クリック数へ精密換算し、[推奨 / 甘み・ボディ / クリーンカップ・酸味] の3パターンを提案。
  * `[スタジオへ読み込む]` ボタンをワンクリックするだけで、全パラメータがエディタへ即時反映されます。
* **リアルタイムAIバリスタ研究所**:
  * 抽出したコーヒーを飲んで「少し苦い」「酸味をもっと際立たせたい」などのフィードバックを入力すると、原因を即座に診断します。
  * 単なる一般論にとどまらず、直前に完了した **実際の抽出時間、注水量、スケール収率データ（履歴）** に基づいて抽出のズレを分析。
  * バリスタAIが提案した補正案（挽き目の微調整、後半水温の引き下げ、注水間隔の調整など）を `[ワンクリックパッチ適用]` でマイレシピに即時反映できます。
* **最新フラッグシップAIモデルをサポート**:
  * **Google Gemini 3.8 Flash** および **OpenAI GPT-4o** モデルを公式サポートし、環境設定から自由に選択できます。
* **抽出物理シミュレーション検証済み**:
  * 豆量増加時の粉層水頭抵抗力学やマルチターンのダイヤル収束性など、バリスタの意思決定アルゴリズムが事前に検証スイートで検証されています。

---

## 機能比較表

| 機能領域 | 基盤通信ライブラリ (`xbloom-ble`) | **xBloom bleUI (v1.0.1)** |
| :--- | :--- | :--- |
| **実行プラットフォーム** | ターミナルベース CLI / TUI (Linux中心) | **スタンドアロンAndroidネイティブアプリ(APK) ＋ クロスプラットフォームPC Web** |
| **PC依存度** | PCのPython環境が必須 | **スマートフォン単独駆動（PC不要でスマホからBLE直接接続）** |
| **自動抽出** | 非対応 | **目覚まし連動 無人自動予約抽出（Dozeモード自動復帰＆水位安全点検）** |
| **加水制御** | 非対応 | **バイパス(Bypass)注水および20g/40g大容量豆対応** |
| **AI機能** | 非対応 | **動画/WebリンクAIレシピ抽出 ＆ 実測データ連動AIバリスタ研究所** |
| **抽出の可視化** | ターミナルTUIベースのテレメトリグラフ | **Web/アプリ高解像度 Chart.js デュアルチャート（注水量 vs カップ抽出量）＆スマート流速マーカー** |
| **ハンドドリップ間隔** | マシン標準待機(`wait`)秒数入力 | **総経過時間基準の累積インターバル自動計算＆マシン待機時間精密変換** |
| **クラウド連携** | 一方行レシピ送信機能 | **双方向連携 ＋ 公式Web共有URL発行 ＋ 外部共有リンク自動解析** |
| **抽出データ保存** | セッション中のみのリアルタイム監視 | **ローカル永続履歴アーカイブ、デュアルチャート完全復元、ワンクリック再抽出** |
| **自動アップデート** | 手動 git pull または再インストール | **GitHubリリース連動ワンクリック自動アップデート（ユーザーデータ保護）** |
| **多言語 (i18n)** | 英語ベース | **グローバル7言語対応（日本語、한국어、English、繁體/简体中文、Deutsch、Français）** |

---

## 主な機能と画面

### 1. リアルタイム抽出ダッシュボード
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="リアルタイム抽出ダッシュボード画面" width="800">
</p>

* **リアルタイム水温 / 時間 / 注水量 / 抽出量 4大メトリクス表示**: マシンのテレメトリパケットを0.1秒単位で即座に受信。
* **デュアルリアルタイムチャート**: 注水量（Water Pour）とカップ抽出液量（Coffee Yield）を秒単位で記録し、滑らかなスプライン曲線をレンダリング。
* **スマート流速／スケール検知プアマーカー**: 加熱遅延や撹拌が含まれて実際の出水が遅れた場合でも、スケール上の重量増加をリアルタイムに検知し、チャート上に垂直点線とピンバッジ（`1st 00:00`, `2nd 00:40`...）を表示。
* **抽出比率自動計算**: リアルタイム注水量と豆量（Dose）に基づき、現在の抽出比率（例: `1 : 16.0`）をリアルタイム更新。
* **緊急停止機能**: 異常検知時、ワンクリックでマシン動作を即座に停止し、安全に接続を維持。

---

### 2. レシピスタジオ (Recipe Studio)
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="レシピスタジオ詳細編集画面" width="800">
</p>

* **精密グラインダー制御＆ミクロン(µm)換算案内**: 挽き目（1〜80クリック）およびRPM（60〜120）制御、入力時にミクロンサイズ（`≈ 808 µm` など）をリアルタイムバナーで表示。
* **多彩なプアパターン**: Center（中央注水）、Ring（円形）、Spiral（螺旋）パターンをフルサポート。
* **スマート撹拌(Agitation)**: 注水前の豆平坦化撹拌（`agitation_before`）および注水後の撹拌（`agitation_after`）を独立設定。
* **ハンドドリップインターバル同期**: 目標待機時間から注水所要時間を考慮した実機待機時間をカード内にヒント表示。
* **YAML標準互換**: ローカルファイルへのエクスポートおよびインポート対応。

---

### 3. 保存済みレシピ管理
<p align="center">
  <img src="docs/img/server-recipes.png" alt="サーバー保存済みレシピ一覧モーダル" width="600">
</p>

* 保存されたレシピ一覧を検索し、ワンクリックで呼び出したり不要なレシピを整理したりできます。
* マシン上部の **A, B, C 物理ボタン** へ、お好みのレシピをフラッシュメモリへ遠隔プログラミング可能。

---

### 4. xBloomクラウド連携＆Web共有URL発行
<p align="center">
  <img src="docs/img/cloud-share.png" alt="クラウドアップロード成功およびWeb共有リンクモーダル" width="600">
</p>

* 公式アプリアカウントでログイン後、ワンクリックでマイレシピをxBloom公式クラウドへアップロード。
* アップロード完了と同時に公式Web共有リンク（`https://share-h5.xbloom.com/?id=...`）を自動取得し、ブラウザで開いたりURLを共有したりできます。
* 他のバリスタが共有したレシピURLを貼り付けるだけで、即座にレシピスタジオへインポート可能。

---

### 5. 抽出履歴＆グラフアーカイブ
<p align="center">
  <img src="docs/img/brew-history.png" alt="抽出履歴およびチャート復元モーダル" width="800">
</p>

* 完了した抽出だけでなく、緊急停止した抽出データまでローカルストレージへ保存。
* 過去の履歴をクリックすると、当時の注水曲線、抽出曲線、プアマーカー、所要時間、抽出比率を完全復元して閲覧でき、**[このレシピをスタジオへ読み込む]** ボタンで再抽出が可能です。

---

## ダウンロード＆リリース

ご使用の環境に合わせて適切なエディションを選択してダウンロードしてください：

| エディション | 対象および推奨環境 | ダウンロードリンク |
| :--- | :--- | :--- |
| **Android 正式リリース APK**<br>*(モバイル)* | **PCなしでスマートフォン単独でマシンを操作したい場合**<br>• APKファイルをダウンロード後、スマホに直接インストール<br>• 開発者署名（v2 Signature）完了 | [⬇️ APKダウンロード (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **Windows ポータブル版**<br>*(PC)* | **Pythonの環境構築なしで使用したい場合**<br>• Python 3.10組込みランタイムおよび必須ライブラリを完全内包<br>• 解凍して `run.bat` をダブルクリックするだけで起動 | [⬇️ 最新ポータブル版ダウンロード (Releases)](https://github.com/ennemate/xBloom-bleUI/releases) |
| **ソースコード配布版**<br>*(Cross-platform)* | **Windows, macOS, Linux クロスプラットフォーム対応**<br>• Python 3.10以上がインストール済みのユーザーおよび開発者<br>• `git clone` または Source Code ZIP から直接実行 | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## クイックスタート

### システム要件
* **モバイル**: Android 8.0 (Oreo) 以上、Bluetooth BLE対応スマートフォン
* **PC**: Windows 10/11, macOS, Linux (Bluetooth 4.2 / 5.0 以上のアダプターが必要)
* **マシン**: xBloom Studio の電源がオンになっており、近くにあること

---

### 方法 A. AndroidスマートフォンにAPKをインストール (モバイル推奨)
1. スマートフォンのブラウザで [Releases ページ](https://github.com/ennemate/xBloom-bleUI/releases) にアクセス
2. **`xBloom-bleUI-release.apk`** をダウンロードしてインストール
3. アプリを起動し、画面右上の **[BLE接続]** ボタンを押すと、周囲のxBloom Studioを自動探索して直接接続されます。

---

### 方法 B. Windows ポータブル版を実行 (PC推奨)
1. [Releases ページ](https://github.com/ennemate/xBloom-bleUI/releases) から `xBloom-bleUI-v1.0.1-Windows-Portable.zip` をダウンロード
2. お好みのフォルダーに解凍
3. フォルダー内の **`run.bat`** ファイルをダブルクリック
   * 内蔵されたPython環境でサーバーが自動起動し、既定のWebブラウザ（`http://localhost:8000`）が自動で開きます。

---

### 方法 C. ソースコードから直接実行 (Windows / macOS / Linux)
1. リポジトリをクローンまたはソースコードをダウンロード:
   ```bash
   git clone https://github.com/ennemate/xBloom-bleUI.git
   cd xBloom-bleUI
   ```
2. 必須パッケージのインストール:
   ```bash
   pip install -r requirements.txt
   ```
3. Webサーバーの起動（ブラウザが自動で開きます）:
   ```bash
   # ランチャースクリプトを実行
   python run.py

   # または直接サーバーを起動
   python server.py --host 0.0.0.0 --port 8000
   ```
4. ブラウザで `http://localhost:8000` にアクセス

---

### バージョンアップデート＆ユーザーデータ保護

* **ワンクリック自動アップデート**: Web画面上部のアップデート通知バッジまたは設定（⚙️）の [アップデート確認] から、最新バージョンへ安全にアップグレードできます。
* **ユーザーデータ保護**:
  * アップデート時はソースコードと静的UIファイルのみが選択的に更新されるため、以下のユーザーデータは上書きされず安全に保持されます:
    * 📂 `recipes/` (ユーザー作成のレシピおよびスロットプリセット)
    * 📄 `history.json` (過去の全抽出履歴およびデュアルチャートアーカイブ)
    * ⚙️ `config.json` (テーマ、壁紙、クラウドアカウント設定)
    * 🐍 `python/` (ポータブル版の内蔵ランタイム)
