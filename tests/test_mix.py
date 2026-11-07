"""Tests for Stage 9 (mix + subtitles). Pure parts offline; mux test uses local ffmpeg only."""

import io
import json
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from src import mix
from src.mix import Placed, build_dub_track, split_sentences, srt_time, subtitle_cues, write_srt


def wav(seconds, value=0.5):
    buf = io.BytesIO()
    sf.write(buf, np.full(int(seconds * mix.RATE), value, dtype=np.float32), mix.RATE,
             format="WAV", subtype="FLOAT")
    return buf.getvalue()


def test_clip_lands_exactly_at_its_start():
    track = build_dub_track([Placed(0, 1.0, wav(0.5), 0.5, "x")], total_seconds=3.0, warn=lambda m: None)
    assert track.shape == (3 * mix.RATE, 2)
    i = mix.RATE  # 1.0 s
    assert track[i - 1, 0] == 0.0 and track[i, 0] == pytest.approx(0.5)
    assert track[i + int(0.5 * mix.RATE), 0] == 0.0  # ends after 0.5 s


def test_overlap_is_warned():
    warnings = []
    build_dub_track([Placed(0, 0.0, wav(2), 2.0, "a"), Placed(1, 1.0, wav(1), 1.0, "b")], 3.0,
                    warn=warnings.append)
    assert any("overlap" in w for w in warnings)


def test_clip_past_end_is_trimmed_and_warned():
    warnings = []
    track = build_dub_track([Placed(0, 2.5, wav(1), 1.0, "a")], 3.0, warn=warnings.append)
    assert len(track) == 3 * mix.RATE and "past the end" in warnings[0]


def test_read_stereo_pads_short_music(tmp_path):
    p = tmp_path / "m.wav"
    sf.write(p, np.ones((mix.RATE, 2), dtype=np.float32) * 0.1, mix.RATE)
    out = mix.read_stereo(p, 2.0)
    assert out.shape == (2 * mix.RATE, 2) and out[-1, 0] == 0.0


@pytest.mark.parametrize("text,expected", [
    ("வணக்கம். எப்படி இருக்கீங்க? சரி!", ["வணக்கம்.", "எப்படி இருக்கீங்க?", "சரி!"]),
    ("आज मी आलो. चला बघूया।", ["आज मी आलो.", "चला बघूया।"]),
    ("আমার নাম গুথাল। তুমি কেমন?", ["আমার নাম গুথাল।", "তুমি কেমন?"]),
    ("no punctuation at all", ["no punctuation at all"]),
])
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected


def test_srt_time_format():
    assert srt_time(0) == "00:00:00,000"
    assert srt_time(3725.5) == "01:02:05,500"


def test_cues_cover_speech_time_proportionally():
    cues = subtitle_cues([Placed(0, 10.0, b"", 6.0, "aa. aaaa.")])  # 3 chars + 5 chars
    assert cues[0][0] == 10.0 and cues[-1][1] == pytest.approx(16.0)  # speech only, not padding
    assert cues[0][1] - cues[0][0] == pytest.approx(6.0 * 3 / 8)


def test_write_srt(tmp_path):
    p = write_srt([Placed(0, 0.2, b"", 2.0, "हे गाईज. चला!")], tmp_path / "x.srt")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("1\n00:00:00,200 --> ") and "\n\n2\n" in text and "चला!" in text


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_each_language_gets_its_own_files(tmp_path):
    """Regression: Path.with_suffix() turned 'v.ta-IN' + '.mp4' into 'v.mp4' (all languages overwrote)."""
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", "-c:v", "libx264",
                    "-c:a", "aac", str(video)], check=True)
    music = tmp_path / "m.wav"
    sf.write(music, np.zeros((mix.RATE, 2), dtype=np.float32), mix.RATE)
    for lang in ("ta-IN", "bn-IN"):
        mix.render(video, music, [Placed(0, 0.0, wav(0.3, 0.1), 0.3, "ok.")], tmp_path / f"v.{lang}", lang,
                   warn=lambda m: None)
    assert {p.name for p in tmp_path.glob("v.*.mp4")} == {"v.ta-IN.mp4", "v.bn-IN.mp4"}
    assert (tmp_path / "v.bn-IN.srt").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_mux_copies_video_and_labels_audio(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=2",
                    "-f", "lavfi", "-i", "sine=f=200:d=2", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(video)], check=True)
    audio = tmp_path / "a.wav"
    sf.write(audio, np.zeros((2 * mix.RATE, 2), dtype=np.float32), mix.RATE)
    out = mix.mux_video(video, audio, tmp_path / "out.mp4", "ta-IN")
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                       str(out)], capture_output=True, text=True, check=True).stdout)
    v_in = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-select_streams", "v",
                                      "-of", "json", str(video)], capture_output=True, text=True).stdout)
    v_out = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    assert v_out["codec_name"] == "h264" and v_out["bit_rate"] == v_in["streams"][0]["bit_rate"]  # copied
    assert "AI-dubbed" in probe["format"]["tags"]["comment"]
    a_out = [s for s in probe["streams"] if s["codec_type"] == "audio"][0]
    assert a_out["tags"]["language"] == "tam"
