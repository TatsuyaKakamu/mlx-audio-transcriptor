# mlx-audio-transcriptor

macOS Apple Silicon 上で動作する、ローカル音声文字起こし GUI アプリ。  
`wav` / `mp3` ファイルをドラッグ&ドロップすると `mlx-whisper` で文字起こしし、同フォルダに Markdown ファイルを保存する。

## 動作環境

- macOS（Apple Silicon 必須）
- Python 3.11 以上
- 仮想環境推奨

## インストール

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 起動

```bash
python -m app.main
```

## 使い方

1. アプリを起動する
2. 言語（`Japanese` / `English`）とモデルを選択する
3. `wav` または `mp3` ファイルをウィンドウにドラッグ&ドロップする
4. 文字起こしが完了すると、入力ファイルと同じフォルダに `*.transcript.md` が生成される

複数ファイルを同時にドロップ可。逐次処理。

## 出力フォーマット

```markdown
---
language: ja
model: medium
---

## Transcript

- [00:00.000 - 00:03.200] おはようございます。
- [00:03.200 - 00:08.000] それでは会議を始めます。
```

同名ファイルが存在する場合は `meeting.transcript.1.md` のように連番が付く。

## 対応ファイル

| 拡張子 | 備考 |
|--------|------|
| `.wav` | 大文字小文字不問 |
| `.mp3` | 大文字小文字不問 |

## モデル

| モデル | 備考 |
|--------|------|
| `tiny` | 最速・低精度 |
| `base` | |
| `small` | |
| `medium` | デフォルト |
| `large-v3` | 最高精度 |

初回使用時はモデルが自動ダウンロードされる。

## プロジェクト構成

```
mlx-audio-transcriptor/
├── app/
│   ├── main.py                        # エントリーポイント
│   ├── ui/
│   │   ├── main_window.py             # メインウィンドウ
│   │   └── drop_area.py               # D&D ウィジェット
│   ├── services/
│   │   ├── transcriber.py             # mlx-whisper 呼び出し
│   │   ├── markdown_writer.py         # Markdown 生成・保存
│   │   └── file_naming.py             # 連番ファイル名決定
│   ├── workers/
│   │   └── transcription_worker.py    # バックグラウンド処理
│   └── models/
│       └── types.py                   # Segment / TranscriptionResult
└── tests/
    ├── test_file_naming.py
    └── test_markdown_writer.py
```

## テスト

```bash
pytest
```

## 依存パッケージ

- [PySide6](https://doc.qt.io/qtforpython/) — GUI
- [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) — 音声文字起こし（Apple Silicon MLX）

## 制限事項（初版）

- 話者分離・自動言語判定・動画ファイルは非対応
- キャンセル・一時停止機能なし
- 設定の永続化なし
- `.app` 化非対応