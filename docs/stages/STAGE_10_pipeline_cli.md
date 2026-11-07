# Stage 10: Full pipeline + CLI + report

**Status:** ✅ Done and tested (2026-11-07) on the 27.6 s chai video in all 3 languages · ⏸ 2–3 min video still to run
**Depends on:** Stages 0–9
**Next stage:** Stage 11: Streamlit page

---

## 1. What we built

- `src/pipeline.py`: `run(video, langs, ref, gnani=..., llm=...)`, all stages in one function.
- `cli.py`: the command a user types.
- `report.json`: metrics for each run.

```powershell
.venv\Scripts\python cli.py --video samples\chai_video.mp4 --lang ta-IN,bn-IN,mr-IN `
    --ref samples\ref_voice_raw.mpeg --names "गुथल बसुमतारी (Guthal Basumatary)"
```
Options: `--lang` one or several (comma-separated); `--names` names to keep; `--no-music` skip Demucs.

## 2. Why Ekswar needs it

Until now each stage ran from its own test script. A real user needs **one command: video in, dubbed video out**. The Streamlit page (Stage 11) calls this same `run()` function.

## 3. How it works

```
check inputs (≤ 3 min video, 5–30 s voice sample, supported language)   ← before ANY credit is spent
[1/9] separate voice / music          (Demucs or --no-music)            shared by all languages
[2/9] transcribe Hindi                 (Gnani Prisma batch)              shared
[3/9] units + punctuation              (Gemini)                          shared
[4/9] voice embedding                  (Gnani, cached)                   shared
for each language:
  [5/9] translate                      (Gemini, names list)
  [6/9] timing agent                   (Gnani cloned TTS + Gemini shortening)
  [7/9] quality check                  (Gnani REST, speech only, 16 kHz)
  [8/9] mix → MP4 + SRT                (local)
[9/9] report.json
```

### Error handling
| Problem | Result |
|---|---|
| Input outside scope | `InputError` before any API call (exit code 2) |
| Bad key / no credit / no permission | `FatalAPIError` stops the run (exit code 3) |
| One line's translation or TTS fails | That line is `failed`, left silent; the rest continues |
| QA call keeps failing | Line marked **"not checked"** (not "passed"); re-run retries only those |

### Outputs: `outputs/runs/<video>/`
```
transcript.json  units.json  ref_clean.wav  audio.wav  vocals_16k_mono.wav
<video>.<lang>.mp4   <video>.<lang>.srt   <video>.<lang>.mix.wav
<lang>/unit_<id>.wav   <lang>/units_result.json   (per-line: translation, status, tempo, QA)
report.json
```

### report.json (per language)
`total_units, fit, sped_up, rewritten, flagged, failed, qa_flags, qa_not_checked, qa_threshold, average_similarity, processing_seconds, gnani_api_calls, gemini_api_calls`, plus run totals, `gemini_fallback_used`, the AI-dubbed label, and `gnani_credits_used: "not available via the API; check the Gnani dashboard"` (honest: no credits API exists).

## 4. Files

| File | Purpose |
|---|---|
| [src/pipeline.py](../../src/pipeline.py) | `check_inputs`, `summarize`, `run` |
| [cli.py](../../cli.py) | Command line |
| [src/audio.py](../../src/audio.py) | + `speech_for_stt()` |
| [src/retry.py](../../src/retry.py) | HTML error pages summarised in logs |
| [tests/test_pipeline.py](../../tests/test_pipeline.py) | End-to-end with fake Gnani + Gemini |

## 5. Tests

**134/134 pass.** New:
- **Full pipeline with fakes:** all 9 progress steps in order; MP4 + SRT + transcript + units + report written; real ffmpeg / units / timing / mix code runs
- **One failed line doesn't stop the run:** video still produced, report counts `failed: 1`
- **Inputs checked before any API call:** bad language, 2 s voice sample → error, 0 calls
- `summarize` counts; HTML error pages kept out of logs; `speech_for_stt` drops padding

## 6. Real results (2026-11-07)

```
Tamil    outputs\runs\chai_video\chai_video.ta-IN.mp4
         units 2: fit 2, sped_up 0, rewritten 0, flagged 0, failed 0 | QA avg 96.6% (0 flagged, 0 not checked)
Bengali  outputs\runs\chai_video\chai_video.bn-IN.mp4
         units 2: fit 2, ... | QA avg 95.1% (0 flagged, 0 not checked)
Marathi  outputs\runs\chai_video\chai_video.mr-IN.mp4
         units 2: fit 2, ... | QA avg 97.7% (0 flagged, 0 not checked)
```
- First run: ~141 s total (mostly new TTS/QA calls + retries). Fully cached re-run: **24 s** for all 3 languages.

## 7. Problems hit

| Problem | What we did |
|---|---|
| Gnani REST STT returned **HTTP 504 HTML pages**, sometimes 5× in a row | Lines marked "not checked" (honest), logs readable, re-run retries only missing checks. All 6 eventually checked. |
| Wrong first guess: blamed our padding silence for the 504s | Later runs disproved it (504s on speech-only clips too). Documented the correction; kept speech-only QA for its own benefits. |

## 8. The 2-minute demo video and what it taught us (2026-11-07)

`samples/ekswar_demo.mp4`: 117.4 s, the speaker's own Diwali greeting, soft music.

### Problem 1: "lip-sync / languages don't match the video" (team feedback)
**True lip-sync (changing the mouth in the video) is out of scope** (brief) and not claimed. But most of what looked wrong was **timing**:
- Gnani gave segments up to **31 s**; inside one long line the dub drifted.
- The cloned voice speaks faster than the speaker, so each line ended early, then silence while the mouth still moved (voice filled only ~65 % of speaking time).

**Fixes (timing sync, in scope):**
| Fix | Where | Effect |
|---|---|---|
| **Split long segments at the speaker's pauses** (silencedetect on the voice stem; chunks 3–8 s; exact text per chunk via Gnani REST; any failure keeps the original line) | `src/segment.py`, `audio.find_pauses`, `audio.slice_for_stt` | 11 → 23 segments → **21 lines** (after the 2 s merge); each line starts where the speaker starts that part |
| **Slow short lines slightly** (if < 90 % of the slot, down to 0.9× at most) | `timing.fill_tempo` | Voice fills more of the speaking time |

### Problem 2: Gemini free quota
See NOTES.md: per-minute vs per-day quotas, the backup chain, cool-downs, validation before caching.

### Final result
| Lang | Lines | Timing | QA avg (min) | Voice fills speaking time |
|---|---|---|---|---|
| Tamil | 21 | fit 18 (all slowed), sped_up 2, **rewritten 1**, failed 0 | 96.3 % (83.9) | **78 %** (was ~65 %) |
| Bengali | 21 | fit 21 (19 slowed), failed 0 | 93.4 % (80.6) | 69 % |
| Marathi | 21 | fit 21 (19 slowed), failed 0 | 96.9 % (85.7) | 72 % |

0 failed, 0 QA-flagged, no wrong-script letters, no digits. For the first time on real content the timing agent **sped up and rewrote** lines.

## 9. Still to do

- [x] Run a **2–3 minute** video in all 3 languages (done, see §8).
- [ ] Team to watch the new videos and confirm the timing sync is better.
- [ ] Optional: `--names` could come from a small config file instead of the command line.
