import os
import time
from collections.abc import Callable
from pathlib import Path

import mlx_whisper
import tqdm as _tqdm_module

from app.models.types import Segment, TranscriptionResult

_MODEL_REPO_MAP: dict[str, str] = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


_DEVNULL = open(os.devnull, "w")


def _make_progress_tqdm(callback: Callable[[int, int, float], None], start: float):
    base = _tqdm_module.tqdm

    class _ProgressTqdm(base):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = False
            kwargs.setdefault("file", _DEVNULL)
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            super().update(n)
            if self.total:
                callback(int(self.n), int(self.total), time.monotonic() - start)

    return _ProgressTqdm


def transcribe(
    source_path: Path,
    model: str,
    language: str,
    progress_callback: Callable[[int, int, float], None] | None = None,
) -> TranscriptionResult:
    repo = _MODEL_REPO_MAP.get(model, f"mlx-community/whisper-{model}-mlx")

    original_tqdm_cls = _tqdm_module.tqdm
    if progress_callback is not None:
        start = time.monotonic()
        _tqdm_module.tqdm = _make_progress_tqdm(progress_callback, start)

    try:
        result = mlx_whisper.transcribe(
            str(source_path),
            path_or_hf_repo=repo,
            language=language,
        )
    finally:
        if progress_callback is not None:
            _tqdm_module.tqdm = original_tqdm_cls
    segments = normalize_segments(result)
    return TranscriptionResult(
        source_path=source_path,
        language=language,
        model=model,
        segments=segments,
    )


def normalize_segments(result: dict) -> list[Segment]:
    raw = result.get("segments", [])
    segments: list[Segment] = []
    for seg in raw:
        text = seg.get("text", "").replace("\n", " ").strip()
        if not text:
            continue
        segments.append(Segment(
            start_sec=float(seg.get("start", 0.0)),
            end_sec=float(seg.get("end", 0.0)),
            text=text,
        ))
    segments.sort(key=lambda s: s.start_sec)
    return segments
