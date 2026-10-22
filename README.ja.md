# xBloom bleUI (v0.9.2)

<p align="center">
  <strong>xBloom Studio のためのモダンなローカルWebダッシュボード＆リアルタイム抽出分析コントローラー</strong>
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
  <img src="docs/img/dashboard-chart.png" alt="xBloom bleUI リアルタイム抽出ダッシュボード デュアルチャート" width="850">
  <br>
  <em>リアルタイム注湯量(Water Pour)とカップ抽出液(Coffee Yield)のデュアルグラフ＆スマート流速検知注湯マーカー</em>
</p>

---

## ☕ プロジェクト概要

**xBloom bleUI** は、プレミアムオールインワンコーヒーマシン **xBloom Studio** とBluetooth LEで接続し、PC・タブレット・スマートフォンのブラウザからレシピを遠隔制御し、抽出データ（水温、注湯量、抽出量、抽出比率）をリアルタイムにグラフ化する次世代ローカルWebシステムです。

公式モバイルアプリの制限（累積インターバル計算の欠如、Web共有リンク解析の非対応、グラインド・抽出フェーズの未分離など）を克服し、バリスタが求める理想のハンドドリップ抽出体験を提供します。

---

## 👥 コントリビューター＆クレジット

本プロジェクトはオープンソースコミュニティの貢献によって進化しています。

| プロフィール | 貢献者 | 役割と貢献 |
| :---: | :---: | :--- |
| <a href="https://github.com/Janczykkkko"><img src="https://github.com/Janczykkkko.png" width="55" style="border-radius:50%;" alt="Janczykkkko"></a> | **[Janczykkkko](https://github.com/Janczykkkko)**<br>*(Original Author)* | • 原作 **[xbloom-ble](https://github.com/Janczykkkko/xbloom-ble)** プロジェクト創始者<br>• xBloom Studio BLE通信プロトコルのリバースエンジニアリングおよびコアパケットデコーダー設計<br>• マシン通信フレームワークおよびハードウェアスロット制御の基礎構築 |
| <a href="https://github.com/ennemate"><img src="https://github.com/ennemate.png" width="55" style="border-radius:50%;" alt="ennemate"></a> | **[ennemate (xBloom bleUI Contributors)](https://github.com/ennemate/xBloom-bleUI)** | • **xBloom bleUI** Webダッシュボードの設計およびフルスタック開発<br>• 純粋PythonによるGitHubワンクリック自動アップデートシステム実装<br>• リアルタイムデュアル抽出チャート(Chart.js)＆スマート流速検知マーカーアルゴリズム<br>• 豆挽き(Grind)と実際の注湯(Brew)の2フェーズ分離とタイマー同期<br>• ハンドドリップ累積インターバル時間補正＆重複減算防止システム<br>• xBloom公式クラウド双方向連携＆Web共有URLの自動発行・解析インポート<br>• 永続抽出履歴アーカイブおよびWindowsポータブル版パッケージング |

---

## ⚡ xBloom bleUI のWebコントローラー独自拡張・特化機能

本プロジェクトは **Janczykkkko** 氏の優れたBLE通信ライブラリ (`xbloom-ble`) をベースエンジンとして採用し、Webブラウザ環境における最高峰のバリスタUXと抽出可視化を実現するため、以下の拡張機能を独自構築しました：

| 主な機能・領域 | 基盤通信ライブラリ (`xbloom-ble`) | **xBloom bleUI (Webコントローラー拡張)** |
| :--- | :--- | :--- |
| **ユーザーインターフェース (UI)** | ターミナルCLI / TUI (Textual) | **モダンレスポンシブWebダッシュボード（ダーク/ライト、カスタム背景対応）** |
| **抽出フェーズ可視化** | テレメトリ生パケットの基本受信 | **豆挽き(Grind)と注湯(Brew)の2フェーズ分離（00:00 タイマー同期）** |
| **リアルタイム注湯検知** | スケール生重量受信 | **スマート流速・スケール検知（Smart Flow Detection）ピンバッジ＆破線マーカー** |
| **ハンドドリップインターバル** | マシン標準待機(`wait`)秒数入力 | **総経過時間基準の累積インターバル自動計算＆マシン待機時間精密変換** |
| **クラウド連携** | レシピ送信機能 | **双方向連携＋Web共有URL自動発行＋外部共有リンク自動解析インポート** |
| **挽き目OFF規格対応** | 基本レシピ送信ペイロード | **公式アプリ規格準拠 (`isSetGrinderSize: 2`、挽き目OFF正常表示)** |
| **マシンスロット** | CLIスロット書き込み | **A / B / C 物理ボタンスロットへのブラウザワンタッチ遠隔書き込み** |
| **抽出データ保存** | セッションリアルタイム監視 | **ローカル永続履歴アーカイブ、デュアルチャート復元、ワンクリック再抽出** |
| **自動アップデート** | 手動 git pull または再インストール | **GitHub Releases連動ワンクリック更新（ユーザーデータ100%保護）** |
| **グラインダー粒度（µm）換算** | クリック数のみ | **挽き目クリック入力時のµmリアルタイム換算表示＆設定トグル** |
| **多言語対応 (i18n)** | 英語ベース | **世界7言語対応（日本語、韓国語、英語、繁体字/簡体字中国語、ドイツ語、フランス語）** |

---

## 🌟 主要機能と画面紹介

### 1. 📊 リアルタイム抽出ダッシュボード
<p align="center">
  <img src="docs/img/dashboard-chart.png" alt="リアルタイム抽出ダッシュボード" width="800">
</p>

- **8大テレメトリ指標**: 水温、抽出時間、注湯量、抽出量、流速、実抽出比率、目標比率、豆量。
- **デュアルリアルタイムチャート**: 注湯量と抽出液量をスプライン曲線で滑らかにプロット。
- **緊急停止機能**: 異常検知時にワンクリックで注湯を即座に安全停止。

---

### 2. 🎛️ レシピスタジオ (Recipe Studio)
<p align="center">
  <img src="docs/img/recipe-studio.png" alt="レシピスタジオ" width="800">
</p>

- **高精度グラインダー制御＆リアルタイム挽き目（µm）換算案内**: 公式挽き目範囲(1〜80クリック)、回転数(60〜120 RPM)、挽き目入力時のµmリアルタイム換算バナー（`≈ 808 µm`など）を表示。
- **挽き目換算ガイドモーダル**: バナーをクリックすると算出式（`挽き目(µm) ≈ 25 + (クリック数 - 1) × 13.8`）および5段階の推奨挽き目ガイドを表示。
  * **📚 換算の算出根拠＆参考資料 (References & Sources)**:
    1. **xBloom 48mmコニカル刃ハードウェア仕様**: 80段階マイクロクリック調整（1クリックあたり約13.8 µm間隙変化）。
    2. **xBloom公式レシピガイドライン**: 公式プリセットのハンドドリップ標準推奨範囲（35〜45クリック）。
    3. **コミュニティ実測データ＆SCA標準**: コニカル刃のネジピッチ実測値およびSCA標準挽き目規格。
    > 💡 焙煎度や刃の状態により実際の粉の細かさに差が生じる場合がある、**レシピ設計用の参考値**です。
- **注湯パターン**: Center(中央)、Spiral(渦巻き)、Ring(外周)対応。
- **デュアル攪拌(Agitation)**: 注湯前ベッド平坦化攪拌＆注湯後抽出攪拌を個別設定。

---

### 3. 📋 保存済みレシピ管理＆マシンスロット
<p align="center">
  <img src="docs/img/server-recipes.png" alt="保存済みレシピ一覧モーダル" width="600">
</p>

- PCローカル(`recipes/`)のレシピを検索・即時ロード。
- マシン本体の **A, B, C ボタン** にワンクリックでレシピを書き込み。

---

### 4. 📜 永続抽出履歴＆チャート復元
<p align="center">
  <img src="docs/img/brew-history.png" alt="抽出履歴モーダル" width="800">
</p>

- 過去の抽出カーブ、注湯マーカー、テイスティングノートを完全復元。
- **[⚡ このレシピをスタジオに読み込む]** ボタンでワンクリック再抽出が可能。

---

## 📦 ダウンロード＆リリース

| エディション | おすすめ対象 | ダウンロードリンク |
| :--- | :--- | :--- |
| **🚀 Windows ポータブル版** | **Python導入が難しい一般ユーザー向け**<br>• 内蔵Python 3.10環境同梱（インストール不要）<br>• 解凍して `run.bat` をダブルクリックするだけ | [⬇️ 最新ポータブル版ダウンロード](https://github.com/ennemate/xBloom-bleUI/releases) |
| **💻 ソースコード版** | **Windows, macOS, Linux クロスプラットフォーム**<br>• Python 3.10以上導入済み環境向け | [⬇️ Source Code (ZIP / tar.gz)](https://github.com/ennemate/xBloom-bleUI/releases) |

---

## 🚀 クイックスタート (Windows ポータブル版)

1. [Releases](https://github.com/ennemate/xBloom-bleUI/releases) から `xBloom-bleUI-v0.9.2-Windows-Portable.zip` をダウンロード。
2. 任意のフォルダに解凍。
3. **`run.bat`** をダブルクリック。
   - 自動でローカルサーバーが起動し、ブラウザで `http://localhost:8000` が開きます。

---

## 📄 ライセンス

本プロジェクトは [MIT License](LICENSE) に基づいて公開されています。

## ⚠️ 免責事項

- 本ソフトウェアは個人が研究・趣味目的で開発した**非公式オープンソースプロジェクト**であり、TBDx Inc. (xBloom) の公式ソフトウェアではありません。
- 抽出前には必ず十分な水温・注湯先カップの設置等、安全を確認の上でご利用ください。
