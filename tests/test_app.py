"""Tests for the Streamlit page: pure helpers + a headless render (no network)."""

from types import SimpleNamespace

import pytest

import app


def test_button_needs_everything_including_consent():
    f = object()
    assert app.can_run(None, f, ["ta-IN"], True)[0] is False
    assert app.can_run(f, None, ["ta-IN"], True)[0] is False
    assert app.can_run(f, f, [], True)[0] is False
    ok, why = app.can_run(f, f, ["ta-IN"], False)
    assert ok is False and "consent" in why
    assert app.can_run(f, f, ["ta-IN"], True) == (True, "")


def test_line_table_statuses():
    rows = [
        {"start": 0, "end": 4, "original": "अ", "final_text": "அ", "status": "fit", "tempo": 0.9,
         "qa_similarity": 96.0, "qa_flag": False},
        {"start": 4, "end": 8, "original": "ब", "final_text": "ব", "status": "sped_up", "tempo": 1.1,
         "qa_similarity": 70.0, "qa_flag": True},
        {"start": 8, "end": 9, "original": "क", "translation": "", "status": "failed"},
        {"start": 9, "end": 12, "original": "ड", "final_text": "ட", "status": "rewritten", "tempo": 1.0,
         "qa_similarity": None},
    ]
    t = app.line_table(rows)
    assert t[0]["Timing"] == "Fit · slowed 0.90×" and t[0]["QA"] == "96%"
    assert t[1]["Timing"] == "Sped up · 1.10×" and t[1]["QA"] == "70% ⚠"
    assert t[2]["Timing"] == "Failed" and t[2]["QA"] == "—"
    assert t[3]["Timing"] == "Rewritten" and t[3]["QA"] == "not checked"


def test_save_upload_is_content_addressed(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "UPLOAD_DIR", tmp_path)
    a = app.save_upload(SimpleNamespace(name="My Video.MP4", getvalue=lambda: b"same"), "video")
    b = app.save_upload(SimpleNamespace(name="other.mp4", getvalue=lambda: b"same"), "video")
    c = app.save_upload(SimpleNamespace(name="x.mp4", getvalue=lambda: b"different"), "video")
    assert a == b != c and a.suffix == ".mp4" and a.read_bytes() == b"same"


def test_page_renders_with_label_and_disabled_button():
    st_testing = pytest.importorskip("streamlit.testing.v1")
    from pathlib import Path
    at = st_testing.AppTest.from_file(str(Path(app.__file__).resolve()), default_timeout=30).run()
    assert not at.exception
    assert any("AI-dubbed" in c.value for c in at.caption)
    assert at.button[0].label == "Dub my video" and at.button[0].disabled
    assert any("Upload a Hindi video" in i.value for i in at.info)
