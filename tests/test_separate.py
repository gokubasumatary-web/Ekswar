"""Fast local tests for Stage 2 helpers (ffmpeg only, no Demucs, no network)."""

import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from src import separate as sep
from src.audio import AudioError, duration

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def make_tone(path, secs=2.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:sample_rate=44100:duration={secs}",
                    "-ac", "2", str(path)], check=True)
    return path


def test_no_music_gives_original_voice_and_matching_silence(tmp_path, monkeypatch):
    monkeypatch.setattr(sep, "CACHE_DIR", tmp_path / "cache")
    audio = make_tone(tmp_path / "a.wav")
    stems = sep.separate(audio, no_music=True)
    assert stems.separated is False
    assert stems.vocals.read_bytes() == audio.read_bytes()
    assert abs(duration(stems.no_vocals) - duration(audio)) < 0.05
    assert np.abs(sf.read(stems.no_vocals)[0]).max() == 0.0


def test_prepare_for_stt_is_16k_mono(tmp_path):
    out = sep.prepare_for_stt(make_tone(tmp_path / "a.wav"), tmp_path / "stt.wav")
    info = sf.info(out)
    assert (info.samplerate, info.channels) == (16000, 1)


def test_prepare_for_stt_rejects_over_10mb(tmp_path, monkeypatch):
    monkeypatch.setattr(sep, "STT_MAX_BYTES", 1000)  # pretend the limit is tiny
    with pytest.raises(AudioError, match="10 MB"):
        sep.prepare_for_stt(make_tone(tmp_path / "a.wav"), tmp_path / "stt.wav")
