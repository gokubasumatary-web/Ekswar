"""Offline tests for Stage 8 (QA). No network."""

from types import SimpleNamespace

import pytest

from src import gnani
from src.cache import Cache
from src.qa import QA_THRESHOLD, check_clip, judge, normalize, similarity


def test_normalize_ignores_punctuation_and_case():
    assert normalize("Hello,  World! வணக்கம்.") == "hello world வணக்கம்"


def test_identical_text_scores_100():
    assert similarity("என் வாய்ஸ் எப்படி இருக்கு?", "என் வாய்ஸ் எப்படி இருக்கு") == 100.0


def test_small_spelling_difference_scores_high():
    assert similarity("பாக்கலாம் காய்ஸ்", "பார்க்கலாம் காய்ஸ்") > 85


def test_unrelated_text_scores_low_and_flags():
    r = judge(0, "ta-IN", "என் வாய்ஸ் எப்படி இருக்கு", "நாளை மழை பெய்யும்")
    assert r.similarity < QA_THRESHOLD and r.qa_flag


def test_empty_transcript_flags_with_note():
    r = judge(0, "bn-IN", "আমার ভয়েস", "")
    assert r.qa_flag and r.note == "no speech heard"


def test_long_clip_not_checked_and_no_call():
    calls = []
    r = check_clip(lambda a, l: calls.append(1) or "x", 0, "ta-IN", b"", "text", duration=31.0)
    assert not r.checked and not r.qa_flag and calls == []


def test_stt_error_becomes_not_checked():
    def boom(a, l):
        raise RuntimeError("503")
    r = check_clip(boom, 0, "mr-IN", b"", "text", duration=5.0)
    assert not r.checked and "503" in r.note


def test_rest_stt_request_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY", "k")
    c = gnani.GnaniClient(cache=Cache(tmp_path))
    sent = []

    def fake_send(method, path, what, **kw):
        sent.append((method, path, kw["data"], list(kw["files"])))
        return SimpleNamespace(json=lambda: {"success": True, "transcript": "வணக்கம்"})

    c._send = fake_send
    assert c.transcribe_rest(b"RIFF..", "ta-IN")["transcript"] == "வணக்கம்"
    assert c.transcribe_rest(b"RIFF..", "ta-IN")["transcript"] == "வணக்கம்"  # cached
    assert sent == [("POST", "/stt/v3", {"language_code": "ta-IN"}, ["audio_file"])]


def test_rest_stt_missing_transcript_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY", "k")
    c = gnani.GnaniClient(cache=Cache(tmp_path))
    c._send = lambda *a, **k: SimpleNamespace(json=lambda: {"success": False})
    with pytest.raises(gnani.RequestError):
        c.transcribe_rest(b"x", "ta-IN")
