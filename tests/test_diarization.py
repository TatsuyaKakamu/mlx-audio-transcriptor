from app.models.types import Segment
from app.services.diarization import assign_speakers, normalize_speaker_ids


def seg(start, end, text="x", speaker_id=None):
    return Segment(start_sec=start, end_sec=end, text=text, speaker_id=speaker_id)


def test_assign_speakers_single_speaker_covers_all():
    segments = [seg(0.0, 2.0), seg(2.0, 5.0)]
    intervals = [(0.0, 10.0, 0)]
    result = assign_speakers(segments, intervals, kept_intervals=None)
    assert [s.speaker_id for s in result] == [0, 0]


def test_assign_speakers_overlap_priority():
    # segment [2, 5] overlaps A=[0,3] for 1s, B=[3,10] for 2s → B wins
    segments = [seg(2.0, 5.0)]
    intervals = [(0.0, 3.0, 0), (3.0, 10.0, 1)]
    result = assign_speakers(segments, intervals, kept_intervals=None)
    assert result[0].speaker_id == 1


def test_assign_speakers_no_overlap_remains_none():
    segments = [seg(10.0, 20.0)]
    intervals = [(0.0, 5.0, 0)]
    result = assign_speakers(segments, intervals, kept_intervals=None)
    assert result[0].speaker_id is None


def test_assign_speakers_empty_intervals_preserves_input():
    segments = [seg(0.0, 1.0, speaker_id=99)]
    result = assign_speakers(segments, [], kept_intervals=None)
    assert result[0].speaker_id == 99


def test_assign_speakers_with_kept_intervals_remap():
    # 元音声 [2,5)+[8,12) → VAD タイムライン [0,3)+[3,7)
    # speaker_interval (vad) [0,3) speaker=0, [3,7) speaker=1
    # 元時間軸では [2,5) と [8,12)
    # segment [3.0, 4.0] (元) は speaker=0 [2,5) と完全重複 → 0
    # segment [9.0, 11.0] (元) は speaker=1 [8,12) と重複 → 1
    kept = [(2.0, 5.0), (8.0, 12.0)]
    intervals = [(0.0, 3.0, 0), (3.0, 7.0, 1)]
    segments = [seg(3.0, 4.0), seg(9.0, 11.0)]
    result = assign_speakers(segments, intervals, kept_intervals=kept)
    assert [s.speaker_id for s in result] == [0, 1]


def test_normalize_speaker_ids_first_seen_order():
    segments = [
        seg(0, 1, speaker_id=5),
        seg(1, 2, speaker_id=2),
        seg(2, 3, speaker_id=5),
        seg(3, 4, speaker_id=2),
        seg(4, 5, speaker_id=7),
    ]
    result = normalize_speaker_ids(segments)
    assert [s.speaker_id for s in result] == [1, 2, 1, 2, 3]


def test_normalize_speaker_ids_preserves_none():
    segments = [
        seg(0, 1, speaker_id=None),
        seg(1, 2, speaker_id=3),
        seg(2, 3, speaker_id=None),
    ]
    result = normalize_speaker_ids(segments)
    assert [s.speaker_id for s in result] == [None, 1, None]


def test_normalize_speaker_ids_zero_based_input():
    segments = [seg(0, 1, speaker_id=0), seg(1, 2, speaker_id=1)]
    result = normalize_speaker_ids(segments)
    assert [s.speaker_id for s in result] == [1, 2]
