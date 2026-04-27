"""話者識別 (speaker diarization) サービス。

sherpa-onnx (ONNX 推論) をバックエンドに使い、HuggingFace アクセストークン不要・
ライセンス受諾不要でオフライン動作する。モデルは k2-fsa の GitHub Releases から
初回のみ自動ダウンロードしてユーザーディレクトリにキャッシュする。

純粋関数 (`assign_speakers`, `normalize_speaker_ids`) は ML 依存なしで単体テスト可能。
`diarize_pcm` / `ensure_models` は sherpa-onnx 依存のためテスト外。
"""
from __future__ import annotations

import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np

from app.models.types import Segment

SpeakerInterval = Tuple[float, float, int]  # (start_sec, end_sec, speaker_id)

_APP_DIR_NAME = "mlx-audio-transcriptor"

_SEGMENTATION_ARCHIVE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
_SEGMENTATION_ARCHIVE_NAME = "sherpa-onnx-pyannote-segmentation-3-0"
_SEGMENTATION_MODEL_REL = "model.onnx"

_EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
)
_EMBEDDING_FILE_NAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"


@dataclass
class DiarizationModelPaths:
    segmentation_model: Path
    embedding_model: Path


_diarizer_singleton = None  # type: ignore[var-annotated]


def _get_cache_dir() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / _APP_DIR_NAME
        / "models"
        / "diarization"
    )


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def ensure_models() -> DiarizationModelPaths:
    """初回のみ ONNX モデルを取得しキャッシュ。2 回目以降は即座にパスを返す。"""
    cache = _get_cache_dir()
    seg_dir = cache / _SEGMENTATION_ARCHIVE_NAME
    seg_model = seg_dir / _SEGMENTATION_MODEL_REL
    if not seg_model.exists():
        archive = cache / f"{_SEGMENTATION_ARCHIVE_NAME}.tar.bz2"
        _download(_SEGMENTATION_ARCHIVE_URL, archive)
        with tarfile.open(archive, "r:bz2") as tf:
            tf.extractall(cache)
        archive.unlink(missing_ok=True)
        if not seg_model.exists():
            raise RuntimeError(
                f"segmentation model not found at {seg_model} after extraction"
            )

    emb_model = cache / _EMBEDDING_FILE_NAME
    if not emb_model.exists():
        _download(_EMBEDDING_URL, emb_model)

    return DiarizationModelPaths(
        segmentation_model=seg_model,
        embedding_model=emb_model,
    )


def _build_diarizer(cluster_threshold: float):
    global _diarizer_singleton
    if _diarizer_singleton is not None:
        cached_threshold, instance = _diarizer_singleton
        if cached_threshold == cluster_threshold:
            return instance

    import sherpa_onnx  # type: ignore[import]

    paths = ensure_models()
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(paths.segmentation_model),
            ),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(paths.embedding_model),
        ),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=-1,
            threshold=cluster_threshold,
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError("Invalid OfflineSpeakerDiarizationConfig")
    instance = sherpa_onnx.OfflineSpeakerDiarization(config)
    _diarizer_singleton = (cluster_threshold, instance)
    return instance


def diarize_pcm(
    audio_pcm: np.ndarray,
    sample_rate: int = 16_000,
    cluster_threshold: float = 0.5,
) -> list[SpeakerInterval]:
    """VAD 連結タイムライン上の (start, end, speaker_id) リストを返す。

    audio_pcm は float32 mono、サンプルレートは sherpa-onnx 側の期待値と
    一致する必要がある (segmentation モデルは 16 kHz 固定)。
    """
    diarizer = _build_diarizer(cluster_threshold)
    if sample_rate != diarizer.sample_rate:
        raise ValueError(
            f"audio sample_rate={sample_rate} does not match diarizer.sample_rate={diarizer.sample_rate}"
        )
    samples = np.ascontiguousarray(audio_pcm, dtype=np.float32)
    result = diarizer.process(samples).sort_by_start_time()
    return [(float(seg.start), float(seg.end), int(seg.speaker)) for seg in result]


def assign_speakers(
    segments: list[Segment],
    speaker_intervals: list[SpeakerInterval],
    kept_intervals: list[tuple[float, float]] | None,
) -> list[Segment]:
    """各 segment に最大 overlap の話者 ID を付与した新リストを返す。

    speaker_intervals は VAD 連結タイムラインの座標。kept_intervals が
    与えられた場合は元タイムラインへリマップしてから overlap を計算する。
    overlap=0 の segment は speaker_id=None のまま残す。
    """
    if not speaker_intervals:
        return [
            Segment(
                start_sec=s.start_sec,
                end_sec=s.end_sec,
                text=s.text,
                speaker_id=s.speaker_id,
            )
            for s in segments
        ]

    if kept_intervals is not None:
        from app.services.vad import remap_timestamp

        mapped: list[SpeakerInterval] = [
            (
                remap_timestamp(s, kept_intervals),
                remap_timestamp(e, kept_intervals),
                sid,
            )
            for s, e, sid in speaker_intervals
        ]
    else:
        mapped = list(speaker_intervals)

    result: list[Segment] = []
    for seg in segments:
        best_id: int | None = None
        best_overlap = 0.0
        for s, e, sid in mapped:
            overlap = min(seg.end_sec, e) - max(seg.start_sec, s)
            if overlap > best_overlap:
                best_overlap = overlap
                best_id = sid
        result.append(
            Segment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                text=seg.text,
                speaker_id=best_id,
            )
        )
    return result


def normalize_speaker_ids(segments: list[Segment]) -> list[Segment]:
    """初出順に 1, 2, 3... と振り直す。None はそのまま。"""
    mapping: dict[int, int] = {}
    next_id = 1
    result: list[Segment] = []
    for seg in segments:
        if seg.speaker_id is None:
            new_id: int | None = None
        else:
            if seg.speaker_id not in mapping:
                mapping[seg.speaker_id] = next_id
                next_id += 1
            new_id = mapping[seg.speaker_id]
        result.append(
            Segment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                text=seg.text,
                speaker_id=new_id,
            )
        )
    return result
