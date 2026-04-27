"""ユーザー設定 (言語・モデル・話者識別 ON/OFF) の永続化。

macOS の慣習に従い `~/Library/Application Support/mlx-audio-transcriptor/config.json`
に保存する。値変更時に都度 save() を呼ぶ前提でクラッシュ耐性を確保。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

_APP_DIR_NAME = "mlx-audio-transcriptor"
_CONFIG_FILE_NAME = "config.json"


@dataclass
class AppSettings:
    language: str = "ja"
    model: str = "medium"
    enable_diarization: bool = False


def get_settings_path() -> Path:
    return (
        Path.home() / "Library" / "Application Support" / _APP_DIR_NAME / _CONFIG_FILE_NAME
    )


def load(path: Path | None = None) -> AppSettings:
    target = path or get_settings_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(raw, dict):
        return AppSettings()
    known = {f.name for f in fields(AppSettings)}
    filtered = {k: v for k, v in raw.items() if k in known}
    try:
        return AppSettings(**filtered)
    except TypeError:
        return AppSettings()


def save(settings: AppSettings, path: Path | None = None) -> None:
    target = path or get_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
