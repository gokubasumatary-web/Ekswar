# Stage 9: Mix + final video + subtitles

**Status:** ✅ Built and tested (2026-11-07) · ⏸ team watching the first dubbed videos
**Depends on:** [Stage 2](STAGE_02_audio_prep.md) (music stem) · [Stage 5](STAGE_05_units.md) (start times) · [Stage 7](STAGE_07_timing_agent.md) (final clips)
**Next stage:** Stage 10: Full pipeline + CLI + report

---

## 1. What we built

`src/mix.py`, which turns the timing agent's clips into a **finished, watchable dubbed video** plus a subtitle file. **No API calls**: everything is local (numpy + ffmpeg).

## 2. Why Ekswar needs it

All earlier stages produce pieces. This stage assembles them into the product: **the creator's video, in another language, in their voice, with the original music**.

## 3. How it works

```
final clips (Stage 7) + start times (Stage 5)
   │ build_dub_track()   silent track as long as the VIDEO; each clip added at its start (numpy, sample-exact)
   ▼                     overlaps / clips past the end → WARNING
dub track  +  no_vocals.wav (Stage 2 music, padded to video length)
   │ mix_with_music()    summed as 32-bit float (no clipping), then ffmpeg loudnorm I=-16 LUFS, TP=-1.5
   ▼
mix.wav
   │ mux_video()         -map 0:v -c:v copy  → picture copied untouched (no quality loss, fast)
   ▼                     new AAC audio, language tag (tam/ben/mar), title "AI-dubbed", comment = AI label
<name>.<lang>.mp4
   + write_srt()         one cue per sentence, timed by character share within the SPEECH time (not padding)
<name>.<lang>.srt
```

### Decisions
| Decision | Why |
|---|---|
| numpy for placing clips | Sample-exact, simple, testable (vs a long ffmpeg filter chain) |
| Track length = **video** length | Phone audio was 0.28 s shorter than the picture (Stage 2 finding) |
| Float sum before loudnorm | Voice + music can exceed full scale; float avoids clipping before normalising |
| -16 LUFS | Common loudness for web video |
| `-c:v copy` | Brief: no re-encode; verified identical bit rate |
| "AI-dubbed" in file metadata | Honesty: the label travels with the file (Streamlit will also show it) |
| Sentence-level subtitles | A 14 s line would otherwise be one huge block |

## 4. Files

| File | Purpose |
|---|---|
| [src/mix.py](../../src/mix.py) | `build_dub_track`, `read_stereo`, `mix_with_music`, `mux_video`, `split_sentences`, `subtitle_cues`, `write_srt`, `render` |
| [scripts/mix_test.py](../../scripts/mix_test.py) | Render all languages for a video |
| [tests/test_mix.py](../../tests/test_mix.py) | 13 tests |

## 5. Tests

**128/128 pass.** Stage 9 tests: clip lands at the exact sample; overlap warned; clip past the end trimmed + warned; short music padded; sentence split for Tamil / Marathi / Bengali (। . ? !); SRT time format; cues cover speech time only; mux copies the video stream (same bit rate) and writes the AI label + 3-letter language tag; **each language gets its own files** (regression test).

## 6. Results (2026-11-07, `samples/chai_video.mp4`)

| Lang | MP4 | Length | Video stream | Audio | Loudness |
|---|---|---|---|---|---|
| Tamil | `outputs/final/chai_video.ta-IN.mp4` | 27.63 s | h264, 1,338,992 b/s (= original) | aac, `tam` | −17.0 LUFS |
| Bengali | `outputs/final/chai_video.bn-IN.mp4` | 27.63 s | identical | aac, `ben` | −16.3 LUFS |
| Marathi | `outputs/final/chai_video.mr-IN.mp4` | 27.63 s | identical | aac, `mar` | −16.1 LUFS |

Tamil subtitles (excerpt):
```
1  00:00:00,204 --> 00:00:02,096  ஹேய் காய்ஸ், என் பேரு குதால் பசுமதாரி.
2  00:00:02,096 --> 00:00:04,636  என்னோட வாய்ஸ் உங்களுக்கு கேக்குதுன்னு நினைக்கிறேன்.
...
4  00:00:14,988 --> 00:00:17,812  பின்னாடி கொஞ்சம் சத்தம் கேட்கும்னு நினைக்கிறேன், தெரியல.
```
The gap from 8.4 s to 15.0 s is where the Tamil speech is shorter than the original (see the Stage 7 observation).

## 7. Problems hit

| Problem | Cause | Fix |
|---|---|---|
| MP4 language tag missing | MP4 needs 3-letter codes (`tam`), ffmpeg silently drops `ta` | `ISO639_2` map |
| **All 3 languages overwrote one file** `chai_video.mp4` | `Path("chai_video.ta-IN").with_suffix(".mp4")` treats `.ta-IN` as an extension | Build names by string; regression test |

## 8. To decide after watching

- Does the gap of silence (dub shorter than original) feel wrong? (Stage 7 §7 options: slow down slightly, or fuller translation.)
- Is the music level right under the new voice?
- Any lip-sync expectations must be stated honestly: **Ekswar does not do lip-sync** (out of scope).
