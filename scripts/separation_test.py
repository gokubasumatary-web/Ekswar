"""Stage 2 measured test with a synthetic video (no API calls, no credits).

Builds a test video from KNOWN parts:
    voice = our own reference recording
    music = computer-generated chords (ffmpeg), roughly as loud as the voice (a hard case)
then runs extract -> Demucs -> STT prep, and measures how well Demucs
recovered each part (SDR in dB: higher = cleaner; >10 dB is good).

Usage:  .venv\\Scripts\\python -m scripts.separation_test outputs\\voice_test\\ref_clean.wav
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from src.audio import _run, duration
from src.config import OUTPUT_DIR, find_tool
from src.separate import WORK_RATE, extract_audio, prepare_for_stt, separate


def build_test_video(voice: Path, out_dir: Path) -> tuple[Path, Path, Path]:
    ff = find_tool("ffmpeg")
    secs = duration(voice)
    voice_st = out_dir / "src_voice.wav"
    music_st = out_dir / "src_music.wav"
    video = out_dir / "synthetic_test.mp4"
    base = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    # voice as stereo 44.1k
    _run(base + ["-i", str(voice), "-ar", str(WORK_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(voice_st)])
    # music: a slowly pulsing chord (A, C, E, A)
    chord = "+".join(f"0.25*sin(2*PI*{f}*t)" for f in (220, 261.63, 329.63, 440))
    expr = f"({chord})*(0.6+0.4*sin(2*PI*0.5*t))*0.35"
    _run(base + ["-f", "lavfi", "-i", f"aevalsrc={expr}|{expr}:s={WORK_RATE}:d={secs:.3f}",
                 "-c:a", "pcm_s16le", str(music_st)])
    # video = coloured background + (voice + music) mixed
    _run(base + ["-f", "lavfi", "-i", f"color=c=0x203040:s=640x360:d={secs:.3f}",
                 "-i", str(voice_st), "-i", str(music_st),
                 "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0[a]",
                 "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", str(video)])
    return video, voice_st, music_st


def sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Signal-to-distortion ratio in dB (simple version)."""
    n = min(len(reference), len(estimate))
    ref, est = reference[:n].astype(np.float64), estimate[:n].astype(np.float64)
    noise = ref - est
    return 10 * np.log10((ref ** 2).sum() / max((noise ** 2).sum(), 1e-12))


def main(voice: str) -> None:
    out_dir = OUTPUT_DIR / "separation_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    video, voice_st, music_st = build_test_video(Path(voice), out_dir)
    print(f"Test video: {video}  ({duration(video):.2f} s)")

    audio = extract_audio(video, out_dir / "audio.wav")
    t0 = time.time()
    stems = separate(audio)
    t_sep = time.time() - t0
    t0 = time.time()
    stems_again = separate(audio)  # should be instant (cached)
    t_cache = time.time() - t0
    stt = prepare_for_stt(stems.vocals, out_dir / "vocals_16k_mono.wav")
    nm = separate(audio, no_music=True)

    v_ref, _ = sf.read(voice_st)
    m_ref, _ = sf.read(music_st)
    v_est, _ = sf.read(stems.vocals)
    m_est, _ = sf.read(stems.no_vocals)
    mix, _ = sf.read(audio)

    print("\n--- separation quality (higher is better) ---")
    print(f"voice before Demucs (mix vs voice): {sdr(v_ref, mix):6.1f} dB")
    print(f"voice after  Demucs:                {sdr(v_ref, v_est):6.1f} dB")
    print(f"music after  Demucs:                {sdr(m_ref, m_est):6.1f} dB")
    print("\n--- files ---")
    for label, p in [("audio", audio), ("vocals", stems.vocals), ("no_vocals", stems.no_vocals),
                     ("stt upload", stt), ("no-music vocals", nm.vocals), ("no-music silence", nm.no_vocals)]:
        info = sf.info(p)
        print(f"{label:17} {info.duration:6.2f} s  {info.samplerate} Hz  {info.channels} ch  "
              f"{p.stat().st_size / 1e6:5.2f} MB")
    peak_silence = np.abs(sf.read(nm.no_vocals)[0]).max()
    print(f"\nno-music silence peak: {peak_silence}")
    print(f"Demucs time: {t_sep:.1f} s   second call (cache): {t_cache:.2f} s   same files: "
          f"{stems_again.vocals == stems.vocals}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.separation_test <voice wav>")
    main(sys.argv[1])
