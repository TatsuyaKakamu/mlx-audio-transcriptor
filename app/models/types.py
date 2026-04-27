from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    start_sec: float
    end_sec: float
    text: str
    speaker_id: int | None = None


@dataclass
class TranscriptionResult:
    source_path: Path
    language: str
    model: str
    segments: list[Segment]
    diarization_enabled: bool = False
