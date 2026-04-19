from pathlib import Path

import mlx_whisper

from app.models.types import Segment, TranscriptionResult

_MODEL_REPO_MAP: dict[str, str] = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


def transcribe(source_path: Path, model: str, language: str) -> TranscriptionResult:
    repo = _MODEL_REPO_MAP.get(model, f"mlx-community/whisper-{model}-mlx")
    result = mlx_whisper.transcribe(
        str(source_path),
        path_or_hf_repo=repo,
        language=language,
    )
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
