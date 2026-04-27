# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 実行環境

- macOS Apple Silicon 必須
- Python 3.11 以上
- 仮想環境: `.venv`

## コマンド

```bash
# セットアップ
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# アプリ起動
python -m app.main

# テスト全件
pytest

# 特定テスト
pytest tests/test_file_naming.py
pytest tests/test_markdown_writer.py
```

## アーキテクチャ

### データフロー

```
DropArea (DnD) → MainWindow → TranscriptionWorker (QThread)
                                  ↓
                          transcriber.transcribe()
                                  ↓ (VAD前処理)
                          vad.preprocess_with_vad()  →  silero_vad で無音区間除去
                                  ↓
                          mlx_whisper.transcribe()  →  mlx-community HuggingFace repo
                                  ↓
                          normalize_segments()  →  VADタイムラインを元タイムラインに再マッピング
                                  ↓ (話者識別 ON のみ)
                          diarization.diarize_pcm()  →  sherpa-onnx で話者区間検出
                          diarization.assign_speakers()  →  各セグメントに話者ID付与
                                  ↓
                          segment_merger.merge_by_conversation()  →  話者境界でブロック分割
                                  ↓
                          file_naming.resolve_output_path()
                                  ↓
                          markdown_writer.write()
```

### スレッド境界

- `TranscriptionWorker` は `QThread` で動作し、`Signal` で UI に通知する
  - `log_message(level, message)` — ログペイン追記
  - `status_update(text)` — ステータス1行表示
  - `progress(float)` — プログレスバー 0–100%
  - `finished(had_errors)` — 完了通知
- UI スレッドからワーカーへの直接呼び出しは禁止

### VAD（音声区間検出）

`services/vad.py` は Silero VAD でファイルを前処理し、無音区間を除去した PCM 配列と元タイムラインへの対応区間リストを返す。`transcriber.py` の `normalize_segments()` が `remap_timestamp()` を使ってセグメントのタイムスタンプを元の時刻に戻す。VAD が失敗した場合はファイルパス文字列にフォールバックして処理を続行する。

### モデル解決

`transcriber.py` の `_MODEL_REPO_MAP` でモデル名を HuggingFace リポジトリ名にマッピングする。未登録名は `mlx-community/whisper-{name}-mlx` として自動補完する。

### ファイル命名

`file_naming.resolve_output_path()` は `meeting.wav` → `meeting.transcript.md` を生成し、衝突時は `meeting.transcript.1.md`, `meeting.transcript.2.md` と最小未使用番号で採番する。

### 話者識別（Diarization）

`services/diarization.py` は sherpa-onnx (ONNX 推論) で話者区間を検出する。HuggingFace アクセストークン不要・ライセンス受諾不要でオフライン動作。初回のみ k2-fsa の GitHub Releases から ONNX モデル (segmentation: pyannote-segmentation-3.0、embedding: 3D-Speaker eres2net) を取得し `~/Library/Application Support/mlx-audio-transcriptor/models/diarization/` にキャッシュする。`assign_speakers()` で Whisper セグメントと話者区間の時間重なりを計算し、最大 overlap の話者を割り当てる。`normalize_speaker_ids()` で初出順に `Speaker 1`, `Speaker 2`... と振り直す。話者識別 ON のとき `merge_by_conversation` は `respect_speaker=True` で動作し、話者境界でブロックを分割する。失敗時は `speaker_id=None` のまま処理続行。

### 設定永続化

`services/settings.py` は `~/Library/Application Support/mlx-audio-transcriptor/config.json` に言語・モデル・話者識別フラグを JSON で保存する。UI 上で値が変わるたびに即時保存し、起動時に `MainWindow` がロードして UI 状態を復元する。ファイル不在 / 破損時はデフォルト値 (`ja` / `medium` / `False`) にフォールバック。

## 出力フォーマット

```markdown
---
language: ja
model: medium
---

## Transcript

- [00:00.000 - 00:03.200] おはようございます。
- [01:02:03.456 - 01:02:08.000] 1時間超えは HH:MM:SS.mmm 形式
```

話者識別 ON のとき:

```markdown
---
language: ja
model: medium
diarization: enabled
---

## Transcript

- [00:00.000 - 00:03.200] **Speaker 1**: おはようございます。
- [00:03.200 - 00:08.000] **Speaker 2**: こちらこそ、よろしくお願いします。
```

## テスト対象モジュール

ロジック層（`services/`）は GUI なしで単体テスト可能。`tests/` にはファイル命名・Markdown 生成・セグメントマージ・VAD 再マッピング・話者割り当て (`diarization.assign_speakers` / `normalize_speaker_ids`)・設定永続化のテストがある。`transcriber.py` と `vad.py` 本体、`diarization.diarize_pcm` / `ensure_models` は `mlx-whisper` / `silero_vad` / `sherpa_onnx` への依存があるためテスト外。

## 現時点の制限

- キャンセル・一時停止不可（処理中ドロップは無視）
- 自動言語判定・動画ファイル非対応
- `.app` 化非対応
