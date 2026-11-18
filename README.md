# Escuta A1 (Gemini Edition)

入門者（CEFR A1）向けのブラジルポルトガル語（`pt-BR`）**「聞く（多聴・音声知覚・記号接地）」特化型パーソナル学習Webアプリ**、およびローカル動作する **Gemini 教材自動生成パイプライン** です。

---

## 1. 特徴と6つの学習ステップ

すべての学習履歴（進捗 `✓`、キーワードチェック、SM-2間隔反復フラッシュカード、振り返りメモ）はサーバーへ一切送信されず、ブラウザの `localStorage` のみに保存されます（JSONエクスポート／インポート対応）。

| ステップ | モード名 | 主な機能 |
| :--- | :--- | :--- |
| **Step ①** | 字幕なしで聞く（全体推測） | 全文非表示＋場面イラスト・2〜3語の場面キーワードタップチェック |
| **Step ②** | 字幕あり（精聴・記号接地） | 上部固定プレイヤー、話者別字幕（Ana＝白 / Pedro＝黄）、自動スクロール、単語タップで「コアイメージ＋文脈意味＋チャンク」ポップアップ |
| **Step ③** | チャンク＆文法予測 | 会話チャンク一覧・個別再生・カード一括追加、3例文から法則を推測して開く「文法パターン予測ミニワーク」 |
| **Step ④** | 練習（Active Recall & 録音） | 4択リスニングクイズ＋マイク録音による**「お手本 → 自分の声」連続A/B比較**（録音はメモリ上のみ保持） |
| **Step ⑤** | 反復（耳慣らしループ） | ポルトガル語連続再生／ポーズ中日本語ガイド挿入切替、`Media Session API` ロック画面操作対応 |
| **Step ⑥** | 振り返り（文化・メタ認知） | ブラジル文化理解設問＋リアルタイム自動保存の自由メモ欄 |

---

## 2. すぐ試す（ローカル起動手順）

パッケージ未インストールの状態でも、Python標準ライブラリのみでサーバーを起動して全UI・サンプル教材（`manaus-demo` 3場面・12文）をすぐ確認できます。

```bash
cd /Users/okudayuuya/.gemini/antigravity/scratch/escuta-a1
python3 scripts/server.py --port 8000
```

ブラウザ（または同じWi-Fi内のiPhone時は `--host 0.0.0.0` を付けて `http://<MacのIP>:8000`）で `http://127.0.0.1:8000` を開きます。

* **`scripts/server.py` 経由で開いた場合**: 右上の **「✨ AI作成」** からブラウザ上でパイプラインを実行できる **🟢 ローカルAI管理モード** になります。
* **静的サーバー（GitHub Pages等）で配信した場合**: 自動的に **📱 静的ビューアーモード** として動作します。
* **オフライン単一HTMLにまとめたい場合**:
  ```bash
  python3 scripts/build_single_html.py
  # -> dist/escuta-a1-offline.html が生成されます
  ```

---

## 3. AI教材生成パイプラインのセットアップ

### 3-1. FFmpeg と Python 仮想環境の準備
```bash
# macOS で FFmpeg が未導入の場合（CBR 128kbps MP3 エンコードに使用）
brew install ffmpeg

# Python 3.10+ 仮想環境の作成と依存パッケージ導入
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3-2. 環境変数 `.env` の設定
```bash
cp .env.example .env
```
作成した `.env` を開き、`GEMINI_API_KEY` に自分のAPIキーを設定してください（モデルIDも `.env` で切り替え可能です）。

---

## 4. APIを消費しないドライラン検証 ＆ 最初の3文テスト手順

いきなり全文を生成してAPI枠を消費しないよう、すべてのスクリプトに **`--dry-run`（API呼び出し0回）** と **`--limit 3`（先頭3文のみ実行）** を用意しています。

### Step A: ドライラン確認（APIリクエスト 0回）
```bash
python3 scripts/generate_script.py --topic "カフェでポン・デ・ケイジョを注文" --lesson-id cafe-test --dry-run
python3 scripts/synthesize_audio.py --lesson-id manaus-demo --limit 3 --dry-run
python3 scripts/audit_quality.py --lesson-id manaus-demo --limit 3 --dry-run
python3 scripts/generate_visuals.py --lesson-id manaus-demo --with-video --dry-run
```

### Step B: サンプル教材の先頭3文だけで本番TTS＆監査テスト
* **発生するAPIリクエスト目安**:
  * `synthesize_audio.py --limit 3`: Gemini 3.8 TTS リクエスト **3回**（軽量テスト時は `--lite` で `gemini-3.8-flash-lite-tts` に切替可能）
  * `audit_quality.py --limit 3`: Whisperはローカル実行（**0回**）＋ Geminiマルチモーダル監査 **1回**（リペア発生時のみ該当文だけ再合成）

```bash
# 1. 先頭3文のみ Gemini 3.8 TTS で音声合成（speech_metadata.style に15%ゆっくりA1スタイルを分離指定）
python3 scripts/synthesize_audio.py --lesson-id manaus-demo --limit 3

# 2. Whisper文字起こし照合 ＋ Geminiネイティブイントネーション監査
python3 scripts/audit_quality.py --lesson-id manaus-demo --limit 3
```

---

## 5. フル教材の本番生成コマンド一式

3文テストで音声品質を確認できたら、`--limit` を外してフル生成します。

```bash
# ① 台本・記号接地データ・クイズ生成（Gemini Text Structured Output: 1リクエスト）
python3 scripts/generate_script.py \
  --topic "マナウスの市場で熱帯フルーツと魚料理を楽しむ" \
  --lesson-id manaus-mercado \
  --scenes 4 \
  --lines 16

# ② 全文TTS合成 ＋ 無音正規化（350ms/650ms/1400ms）＋ CBR 128kbps MP3出力
python3 scripts/synthesize_audio.py --lesson-id manaus-mercado

# ③ Whisper ＋ Gemini 二重品質監査＆自動リペア（最大2回リトライ）
python3 scripts/audit_quality.py --lesson-id manaus-mercado

# ④ Ana / Pedro 一貫キャラクター静止画の生成
python3 scripts/generate_visuals.py --lesson-id manaus-mercado

# （オプション）重要場面のみ Veo (veo-3.1-generate-preview) で5〜8秒の情景ループ動画を生成する場合
python3 scripts/generate_visuals.py --lesson-id manaus-mercado --with-video --video-scenes scene-1
```

---

## 6. 既存のClaude版データ（Manaus 145文・47枚イラスト等）の引き継ぎ

既存のClaude版HTMLやJSON、イラストフォルダが手元にある場合は、`migrate_legacy.py` を使うと**元ファイルを一切削除・変更せず `legacy_backup/` に自動退避**したうえで、新UI形式（`lessons/<id>/lesson.json`）へ変換・カタログ登録します。

```bash
python3 scripts/migrate_legacy.py \
  --source /path/to/legacy_manaus_v2.html \
  --lesson-id manaus-v2-full \
  --title "Manaus Complete (145 Lines)" \
  --title-ja "マナウス完全版（145文）" \
  --media-dir /path/to/manaus_images \
  --audio /path/to/manaus_audio.mp3
```
