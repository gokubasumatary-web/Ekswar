# Stage 2: Audio prep (extraction + voice/music separation)

**Status:** ✅ Built and tested on a **synthetic** video · ⏸ re-check on a real 30 s Hindi video when available
**Depends on:** [Stage 0](STAGE_00_foundation.md) (cache, ffmpeg)
**Next stage:** Stage 3: Hindi transcription (Gnani Prisma Batch)

---

## 1. What we built

`src/separate.py`, which takes a video and produces:

| Output | What it is | Used by |
|---|---|---|
| `audio.wav` | The video's full soundtrack (44.1 kHz stereo) | input to Demucs |
| `vocals.wav` | **Only the voice** | Stage 3 (transcription) |
| `no_vocals.wav` | **Only the music/background** | Stage 9 (final mix, under the new voice) |
| `vocals_16k_mono.wav` | Voice converted for Gnani upload | Stage 3 |

Plus a `--no-music` mode for videos without background music.

## 2. Why Ekswar needs it

A video's sound is **one mixed track**: voice + music together. To dub it we must:
1. give **clean voice** to speech-to-text (more accurate timestamps and words),
2. keep the **music without the Hindi voice**, so the new language can replace the old voice while the music stays.

Without separation: either the Hindi voice is still audible under the dub, or the music is lost.

## 3. How it works

```
video.mp4
  │ ffmpeg: -vn, 44.1 kHz, stereo, 16-bit WAV
  ▼
audio.wav
  │ Demucs (htdemucs model, --two-stems=vocals, CPU)    ← cached by file fingerprint
  ▼
vocals.wav  +  no_vocals.wav
  │ ffmpeg: 16 kHz, mono
  ▼
vocals_16k_mono.wav   (checked < 10 MB: Gnani batch upload limit)
```

**What is Demucs?** A free AI model (by Meta) trained on thousands of songs where the voice and instruments were known separately. It learned what a voice sounds like versus music, so it can pull them apart. "Two-stems" = split into just two parts: voice and everything else.

**`--no-music` mode:** skips Demucs. `vocals.wav` = the original audio, `no_vocals.wav` = silence of the same length. Faster, and avoids any separation artifacts when there's no music.

**Caching:** Demucs output is stored in `cache/separation/<fingerprint>/`. Files are moved there only after **both** stems exist, so a crash never leaves half a result. Second call: 0.01 s.

**Why 44.1 kHz stereo internally?** The music sounds best in stereo at full quality, and the cloned-voice clips from Gnani are also 44.1 kHz. Only the STT upload is reduced to 16 kHz mono (what the docs recommend, and smaller).

## 4. Setup decisions

| Decision | Why |
|---|---|
| **Demucs 4.1.0** | pip picked the newest. It no longer needs `torchaudio`, which removed the compatibility risk with new PyTorch. |
| **PyTorch CPU build (2.15)** | The GPU build (2.5 GB) download failed on a network drop. CPU is fast enough for ≤3 min videos. **Team decision: CPU.** |
| Run Demucs as a subprocess (`python -m demucs`) | Uses Demucs's official command line, so there's less chance of breaking on version changes. |

## 5. Files

| File | Purpose |
|---|---|
| [src/separate.py](../../src/separate.py) | `extract_audio()`, `separate()`, `prepare_for_stt()`, CLI |
| [scripts/separation_test.py](../../scripts/separation_test.py) | Measured test on a synthetic video |
| [tests/test_separate.py](../../tests/test_separate.py) | 3 fast tests (ffmpeg only) |

## 6. How we tested it

### Why a synthetic video?
We don't have the real test video yet. So we **built one from known parts**: our own voice sample + computer-generated chord music (allowed by the rules: own voice + synthetic content). Because we know exactly what went in, we can **measure** how well Demucs got each part back, not just guess by ear.

**SDR (signal-to-distortion ratio)** compares the separated track with the true original. Higher = cleaner. Rough guide: **above ~10 dB is good**.

```powershell
.venv\Scripts\python -m scripts.separation_test outputs\voice_test\ref_clean.wav
.venv\Scripts\python -m pytest -q
```

## 7. Results (2026-11-06)

```
voice before Demucs (mix vs voice):    0.4 dB   ← music about as loud as voice
voice after  Demucs:                  17.1 dB
music after  Demucs:                  16.7 dB

audio              21.60 s  44100 Hz  2 ch   3.81 MB
vocals             21.60 s  44100 Hz  2 ch   3.81 MB
no_vocals          21.60 s  44100 Hz  2 ch   3.81 MB
stt upload         21.60 s  16000 Hz  1 ch   0.69 MB
no-music silence peak: 0.0
Demucs time: 23.5 s   second call (cache): 0.01 s
```

- Demucs improved voice clarity from **0.4 dB → 17.1 dB** and recovered the music at **16.7 dB**: a clear, measurable separation.
- All outputs keep the exact length (21.60 s), which matters for timing later.
- **Speed:** ≈1.1× real time on CPU → a 3-min video ≈ 3–4 min.
- **Upload size:** 21.6 s → 0.69 MB, so 3 min ≈ 5.8 MB, safely under 10 MB.
- **Tests:** 21/21 pass.

**Honest limit:** synthetic chords are easier to separate than real music with drums and vocals-like instruments. A real video may score lower. **We'll listen to the real one.**

## 8. Problems hit

| Problem | Fix |
|---|---|
| GPU PyTorch download failed (network drop) | Use the CPU build (team decision) |
| Windows "symlinks" warning from the model download | Harmless (it's about how the model file is cached), ignored |

## 9. Real-video run (2026-11-07)

Input: `samples/chai_video.mp4`: the team's own chai-recipe video (WhatsApp), **27.6 s, portrait 480×864, H.264 + AAC 48 kHz stereo**.

```
audio        27.35 s   4.82 MB
vocals       27.35 s   4.82 MB   mean -30.8 dB, peak -2.7 dB
no_vocals    27.35 s   4.82 MB   mean -43.2 dB, peak -25.3 dB
stt upload   27.35 s   0.88 MB
```

Observations:
- Separation ran fine on a real phone video.
- **Music is soft:** about 12 dB below the voice. That's realistic for a talking video.
- **Voice is quiet on average** (−30.8 dB mean) but peaks at −2.7 dB: a big gap between loud and quiet parts, probably from distance to the phone. Gnani should still cope; watch the Stage 3 transcript quality.
- **The audio track (27.35 s) is 0.28 s shorter than the video container (27.63 s).** This is common with phone/WhatsApp videos. Stage 9 must handle it: the final audio should cover the whole video.
- **WhatsApp video reports an odd frame rate** (`90000/1`, i.e. variable frame rate). Fine for us, because Stage 9 copies the video stream without re-encoding.

Listening files: `outputs/separation/chai_video/0_original.wav`, `1_voice_only.wav`, `2_music_only.wav`.

- [ ] Team listening: is the Hindi voice gone from `2_music_only.wav`? Is the music intact in it?

## 10. How this connects

- Stage 3 uploads `vocals_16k_mono.wav` to Gnani Prisma Batch.
- Stage 9 lays the dubbed voice over `no_vocals.wav` and puts it back on the original video.
