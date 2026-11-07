"""End-to-end pipeline test with FAKE Gnani + Gemini (no network, no credits).

Real code runs for everything else: ffmpeg extraction, units, translation checks,
timing agent, QA scoring, mixing, muxing, SRT and report.json.
"""

import io
import json
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from src.pipeline import InputError, run, summarize

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

TAMIL = {0: "வணக்கம் நண்பர்களே. இது ஒரு சோதனை.", 1: "நன்றி. மீண்டும் சந்திப்போம்!"}


def tone_wav(seconds):
    buf = io.BytesIO()
    t = np.arange(int(seconds * 44100)) / 44100
    sf.write(buf, (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), 44100, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class FakeGnani:
    def __init__(self, secs_per_char=0.05, fail_unit=None):
        self.api_calls = 0
        self.spc = secs_per_char
        self.fail_unit = fail_unit
        self.spoken = {}  # audio bytes -> text (so the fake STT can "hear" it)

    def transcribe_batch(self, wav, lang, log=print):
        self.api_calls += 1
        assert lang == "hi-IN"
        return {"duration_seconds": 8.0, "full_transcript": "नमस्ते दोस्तों यह एक परीक्षण है धन्यवाद",
                "segments": [{"start_time": 0.2, "end_time": 4.0, "text": "नमस्ते दोस्तों यह एक परीक्षण है"},
                             {"start_time": 4.5, "end_time": 7.5, "text": "धन्यवाद फिर मिलेंगे"}]}

    def create_voice_embedding(self, ref):
        self.api_calls += 1
        return {"embedding": "AAAA", "shape": [1, 768], "dtype": "torch.bfloat16"}

    def synthesize_cloned(self, text, emb, what=""):
        self.api_calls += 1
        if self.fail_unit is not None and f"unit {self.fail_unit} " in what:
            raise RuntimeError("TTS 500")
        audio = tone_wav(len(text) * self.spc)
        self.spoken[audio] = text
        return audio

    def transcribe_rest(self, audio, lang, what=""):
        self.api_calls += 1
        # padded clips differ from raw ones; find the longest spoken text that fits
        return {"transcript": max(self.spoken.values(), key=len) if not self.spoken else
                next((t for a, t in self.spoken.items() if audio.startswith(a[:2000])), "")}


class FakeLLM:
    api_calls = 0
    fallback_used = 0

    def ask_json(self, prompt, schema=None, what="", validate=None):
        self.api_calls += 1
        if what == "punctuation":
            return {"lines": ["नमस्ते दोस्तों, यह एक परीक्षण है।", "धन्यवाद, फिर मिलेंगे!"]}
        if what.startswith("translate unit"):
            return {"translation": TAMIL[int(what.split()[2])]}
        raise AssertionError(f"unexpected LLM call: {what}")


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    video, ref = d / "talk.mp4", d / "ref.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=green:s=64x64:d=8",
                    "-f", "lavfi", "-i", "sine=f=300:d=8", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(video)], check=True)
    ref.write_bytes(tone_wav(6))
    return video, ref


def test_full_pipeline_with_fakes(media, tmp_path, monkeypatch):
    monkeypatch.setattr("src.separate.CACHE_DIR", tmp_path / "cache")
    video, ref = media
    steps = []
    res = run(video, ["ta-IN"], ref, gnani=FakeGnani(), llm=FakeLLM(), no_music=True, out_root=tmp_path,
              progress=lambda i, n, m: steps.append(i), log=lambda m: None)
    assert steps == list(range(1, 10))                      # all 9 steps, in order
    lr = res.langs["ta-IN"]
    assert lr.mp4.exists() and lr.srt.exists()
    assert [r["status"] for r in lr.units] == ["fit", "fit"]
    rep = json.loads(res.report_path.read_text(encoding="utf-8"))
    ta = rep["languages"]["ta-IN"]
    assert ta["total_units"] == 2 and ta["fit"] == 2 and ta["failed"] == 0
    assert rep["label"].startswith("AI-dubbed")
    assert (res.out_dir / "transcript.json").exists() and (res.out_dir / "units.json").exists()
    assert "வணக்கம் நண்பர்களே." in lr.srt.read_text(encoding="utf-8")


def test_one_failed_unit_does_not_stop_the_run(media, tmp_path, monkeypatch):
    monkeypatch.setattr("src.separate.CACHE_DIR", tmp_path / "cache")
    video, ref = media
    res = run(video, ["ta-IN"], ref, gnani=FakeGnani(fail_unit=1), llm=FakeLLM(), no_music=True,
              out_root=tmp_path, log=lambda m: None)
    rows = res.langs["ta-IN"].units
    assert rows[0]["status"] == "fit" and rows[1]["status"] == "failed"
    assert "synthesis failed" in rows[1]["note"]
    assert res.langs["ta-IN"].mp4.exists()                   # video still produced
    assert res.langs["ta-IN"].report["failed"] == 1


def test_inputs_checked_before_any_api_call(media, tmp_path):
    video, ref = media
    g = FakeGnani()
    with pytest.raises(InputError, match="language"):
        run(video, ["fr-FR"], ref, gnani=g, llm=FakeLLM(), out_root=tmp_path, log=lambda m: None)
    short_ref = tmp_path / "short.wav"
    short_ref.write_bytes(tone_wav(2))
    with pytest.raises(InputError, match="5-30 s"):
        run(video, ["ta-IN"], short_ref, gnani=g, llm=FakeLLM(), out_root=tmp_path, log=lambda m: None)
    assert g.api_calls == 0                                   # nothing spent


def test_summarize_counts():
    rows = [{"status": "fit", "qa_similarity": 90.0, "qa_flag": False},
            {"status": "rewritten", "qa_similarity": 70.0, "qa_flag": True},
            {"status": "failed"}]
    s = summarize("bn-IN", rows, 12.34, {"gnani_api_calls": 5, "gemini_api_calls": 2})
    assert (s["fit"], s["rewritten"], s["failed"], s["qa_flags"]) == (1, 1, 1, 1)
    assert s["average_similarity"] == 80.0 and s["qa_not_checked"] == 0 and s["language_name"] == "Bengali"
