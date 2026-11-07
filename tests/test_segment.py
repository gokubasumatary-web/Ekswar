"""Tests for splitting long segments at pauses. Pure logic + fake STT (no network)."""

import pytest

from src import segment
from src.segment import MAX_LEN, MIN_LEN, cut_points, refine_segments


def test_short_segment_is_not_split():
    assert cut_points(0.0, 7.5, [(3.0, 3.5)]) == [(0.0, 7.5)]


def test_long_segment_cut_at_pause_midpoints():
    pauses = [(4.0, 4.4), (9.0, 9.6), (14.0, 14.4), (19.0, 19.6)]
    chunks = cut_points(0.0, 24.0, pauses)
    assert chunks[0][0] == 0.0 and chunks[-1][1] == 24.0
    assert all(b == c for (_, b), (c, _) in zip(chunks, chunks[1:]))       # contiguous, no gaps
    assert all(MIN_LEN <= b - a <= MAX_LEN for a, b in chunks)
    assert {b for _, b in chunks[:-1]} <= {4.2, 9.3, 14.2, 19.3}            # cuts only at pauses


def test_no_chunk_shorter_than_min():
    chunks = cut_points(0.0, 20.0, [(1.0, 1.2), (18.9, 19.1), (10.0, 10.4)])  # pauses near the edges
    assert all(b - a >= MIN_LEN for a, b in chunks)


def test_no_pauses_means_no_split():
    assert cut_points(0.0, 30.0, []) == [(0.0, 30.0)]


def test_pause_far_away_still_used_if_nothing_closer():
    chunks = cut_points(0.0, 30.0, [(14.8, 15.2)])  # only one pause, chunks of 15 s
    assert chunks == [(0.0, 15.0), (15.0, 30.0)]


T = {"duration_seconds": 30, "segments": [
    {"start_time": 0.5, "end_time": 20.0, "text": "पूरा लंबा वाक्य"},
    {"start_time": 21.0, "end_time": 25.0, "text": "छोटा"}]}
PAUSES = [(6.0, 6.4), (12.0, 12.4)]


@pytest.fixture(autouse=True)
def no_ffmpeg_slicing(monkeypatch):
    monkeypatch.setattr(segment, "slice_for_stt", lambda path, a, b: f"{a}-{b}".encode())


def test_refine_splits_long_segment_with_exact_texts():
    heard = {b"0.5-6.2": "पहला हिस्सा", b"6.2-12.2": "दूसरा हिस्सा", b"12.2-20.0": "तीसरा हिस्सा"}
    t, stats = refine_segments(T, "v.wav", lambda wav: heard[wav], pauses=PAUSES, warn=lambda m: None)
    texts = [s["text"] for s in t["segments"]]
    assert texts == ["पहला हिस्सा", "दूसरा हिस्सा", "तीसरा हिस्सा", "छोटा"]
    assert stats["split_segments"] == 1 and stats["segments_after"] == 4
    assert t["segments"][1]["start_time"] == 6.2 and t["segments"][1]["split_from"] == 0.5


def test_failed_chunk_keeps_original_segment():
    def stt(wav):
        raise RuntimeError("504")
    warnings = []
    t, stats = refine_segments(T, "v.wav", stt, pauses=PAUSES, warn=warnings.append)
    assert [s["text"] for s in t["segments"]] == ["पूरा लंबा वाक्य", "छोटा"]
    assert stats["kept_unsplit"] == 1 and "kept as one line" in warnings[0]


def test_empty_chunk_keeps_original_segment():
    t, stats = refine_segments(T, "v.wav", lambda wav: "", pauses=PAUSES, warn=lambda m: None)
    assert len(t["segments"]) == 2 and stats["kept_unsplit"] == 1


def test_nothing_long_means_no_work():
    short = {"segments": [{"start_time": 0, "end_time": 5, "text": "x"}]}
    calls = []
    t, stats = refine_segments(short, "v.wav", lambda w: calls.append(1) or "y", warn=lambda m: None)
    assert t is short and calls == [] and stats["split_segments"] == 0
