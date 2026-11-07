"""Local tests for ffmpeg speed-up and padding (no network)."""

import shutil
import subprocess

import pytest

from src.audio import AudioError, change_tempo, duration_of_bytes, pad_to, speech_for_stt

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


@pytest.fixture(scope="module")
def tone():
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi",
                          "-i", "sine=frequency=300:sample_rate=44100:duration=4",
                          "-c:a", "pcm_s16le", "-f", "wav", "-"], capture_output=True, check=True)
    return out.stdout


@pytest.mark.parametrize("tempo", [1.1, 1.15, 1.25])
def test_tempo_shortens_by_the_factor(tone, tempo):
    assert duration_of_bytes(change_tempo(tone, tempo)) == pytest.approx(4 / tempo, abs=0.03)


def test_tempo_out_of_range_rejected(tone):
    with pytest.raises(AudioError):
        change_tempo(tone, 3.0)


def test_pad_extends_with_silence(tone):
    assert duration_of_bytes(pad_to(tone, 6.0)) == pytest.approx(6.0, abs=0.01)


def test_speech_for_stt_drops_padding_and_downsamples(tone):
    import io
    import soundfile as sf
    padded = pad_to(tone, 9.0)                       # 4 s of sound + 5 s of silence
    out = speech_for_stt(padded, 4.0)
    info = sf.info(io.BytesIO(out))
    assert (info.samplerate, info.channels) == (16000, 1)
    assert info.duration == pytest.approx(4.05, abs=0.02)


def test_pad_never_cuts(tone):
    assert duration_of_bytes(pad_to(tone, 2.0)) == pytest.approx(4.0, abs=0.01)
