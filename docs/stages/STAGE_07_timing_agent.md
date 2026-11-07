# Stage 7: Timing Agent (core innovation)

**Status:** ✅ Done and tested: offline (all branches) + real cloned voice in all 3 languages + real stress test of speed-up and rewrite (2026-11-07). Unit 0 to be re-run once the correct name spelling is known.
**Depends on:** [Stage 1](STAGE_01_voice_test.md) (cloned TTS) · [Stage 4](STAGE_04_llm.md) (Gemini) · [Stage 5](STAGE_05_units.md) (slots) · [Stage 6](STAGE_06_translation.md) (translations)
**Next stage:** Stage 8: Quality check

---

## 1. What we built

`src/timing.py`: the agent that makes **every dubbed line fit the time the original line took**.

## 2. Why it matters (the core idea of Ekswar)

Tamil, Bengali and Marathi sentences rarely take the same time to say as Hindi. If a translated line is too long, the dub either **overlaps the next line** or **drifts further out of sync** with every sentence. The timing agent measures every spoken line and **fixes it until it fits**, using the gentlest fix that works.

## 3. The decision ladder

```
budget = slot + 0.5 × gap          (own time + half of the pause after it)

clip ≤ budget                → FIT        pad with silence to the budget
clip ≤ budget × 1.15         → SPED_UP    ffmpeg atempo (faster, same pitch)
clip > budget × 1.15         → REWRITE    Gemini shortens → Gnani speaks again → re-check
                                          (up to 3 times; ask for
                                           chars × budget/duration × 0.95)
   after a rewrite: fits?                       → REWRITTEN
                    fits with ≤1.15 speed-up?   → REWRITTEN (tempo recorded)
still too long after 3 rewrites (use the SHORTEST version):
   ≤ budget × 1.25           → SPED_UP    (up to 1.25×)
   otherwise                 → FLAGGED    keep it as is; never cut words; needs a human look
```

Gentlest fix first: do nothing → small speed-up → rewrite → bigger speed-up → flag.

### Safety rules
| Situation | Behaviour |
|---|---|
| Gemini fails to shorten (e.g. overloaded) | Stop rewriting for this unit; continue down the ladder (speed-up / flag). Recorded in `note`. |
| Gemini returns the same text | Stop rewriting (no pointless re-synthesis = no wasted credits) |
| Gnani TTS fails | Error goes to the caller, which marks the unit `failed` and continues with the next |
| Padding | Only adds silence at the end; **never cuts audio** (tested) |
| Speed-up range | Limited to 0.5–2.0 in code; the ladder never asks above 1.25 |

### Pure decisions vs real actions
```python
decide(duration, budget, rewrites_done) -> Decision("fit" | "speed" | "rewrite" | "flag", tempo)
fit_unit(..., synthesize=..., measure=..., shorten=..., speed_up=..., pad=...)
```
`decide` is pure maths. `fit_unit` takes the actions as **plugged-in functions**:
- **tests** plug in fakes (a "clip" is just a number of seconds) → every branch tested in 0.1 s, no credits,
- **real runs** plug in Gnani TTS, ffprobe, Gemini `shorten_line`, ffmpeg `atempo` / `apad`.

## 4. Files

| File | Purpose |
|---|---|
| [src/timing.py](../../src/timing.py) | `budget_for`, `decide`, `target_chars`, `fit_unit`, `TimingResult` |
| [src/audio.py](../../src/audio.py) | + `change_tempo()` (atempo), `pad_to()` (apad) |
| [src/translate.py](../../src/translate.py) | + `shorten_line()` (Gemini prompt for a shorter line) |
| [scripts/timing_test.py](../../scripts/timing_test.py) | Real run: cloned voice + agent + timing table |
| [tests/test_timing.py](../../tests/test_timing.py) | 21 tests: every branch of the ladder |
| [tests/test_audio.py](../../tests/test_audio.py) | 5 tests: speed-up accuracy, padding never cuts |

## 5. Test results (offline)

**102/102 tests pass** (whole project). Timing tests cover:
- budget = slot + half the gap; negative gap ignored
- decisions at every boundary (exactly on budget, exactly 1.15×, just over, 1.25×, just over)
- fit → padded to the budget; small overrun → sped up, no LLM call
- too long → rewritten → fits; rewrite + light speed-up → "rewritten"
- 3 failed rewrites → speed-up applied to the **shortest** version
- hopeless line → flagged, shortest kept, **no extreme speed-up**
- Gemini failure → rewrites stop, unit still finishes; rewrite count stays honest (0)
- same text returned → no re-synthesis
- TTS failure → raised to the caller

**ffmpeg on the real cloned Tamil clip (8.26 s), free:**
```
atempo 1.10   7.518 s   expected 7.509   error 9 ms
atempo 1.15   7.191 s   expected 7.183   error 8 ms
atempo 1.25   6.614 s   expected 6.608   error 6 ms
pad to 10 s   10.000 s
pad to 5 s    8.260 s  (unchanged: never cut)
```
Listening files: `outputs/timing_check/ta_1.15x.wav`, `ta_1.25x.wav`. **Team listening (2026-11-07): 1.25× judged OK**, so the brief's limits (1.15 / 1.25) are kept.

## 6. Real run with the cloned voice (2026-11-07)

```powershell
.venv\Scripts\python -m scripts.timing_test outputs\units\chai_video.json --lang ta-IN --ref samples\ref_voice_raw.mpeg
```

| Lang | Unit | Slot | Budget | Spoken | Status |
|---|---|---|---|---|---|
| Tamil | 0 | 14.52 | 14.65 | 8.72 | fit |
| Tamil | 1 | 12.36 | 12.36 | 7.21 | fit |
| Bengali | 0 | 14.52 | 14.65 | 11.77 | fit |
| Bengali | 1 | 12.36 | 12.36 | 7.11 | fit |
| Marathi | 0 | 14.52 | 14.65 | 13.29 | fit |
| Marathi | 1 | 12.36 | 12.36 | 7.28 | fit |

- **Cost:** 6 Gnani TTS calls, 0 Gemini. Final clips are padded exactly to the budget (14.65 s / 12.36 s).
- **All six fit at once.** The source speaker talks slowly with pauses, so the slots are roomy.

### Stress test (artificial: slots squeezed, NOT a real result)
To prove the speed-up and rewrite paths work with the **real** APIs, Tamil unit 1 was re-run with its slot shrunk (`--squeeze`; output in separate `*.squeezeX` folders):

| Squeeze | Budget | Spoken | Result | Calls |
|---|---|---|---|---|
| ×0.55 | 6.80 s | 7.21 s | **sped_up**, tempo 1.06 → 6.80 s | 0 (cached clip) |
| ×0.45 | 5.56 s | 7.21 s | **rewritten**: Gemini asked for ≤106 chars → 95 chars → **4.87 s**, fits | 1 Gemini + 1 Gnani |

Rewrite (meaning kept, filler dropped):
```
145 ch 7.21 s  பின்னாடி கொஞ்சம் சத்தம் கேட்கும்னு நினைக்கிறேன், தெரியல. இப்போ டெஸ்ட் பண்ணி பாப்போம் என் வாய்ஸ் எப்படி இருக்குனு. பாக்கலாம் காய்ஸ், என்ன ஆகுதுனு!
 95 ch 4.87 s  பின்னாடி சத்தம் கேட்கலாம். என் வாய்ஸ் எப்படி இருக்குனு டெஸ்ட் பண்ணி பாப்போம். பாக்கலாம் காய்ஸ்!
```

## 7. Observation for the team: dubs can be much SHORTER than the slot

Tamil unit 0 speaks for 8.7 s in a 14.65 s budget, so **~6 s of silence** follows while the speaker is still on screen talking. The brief only handles lines that are too *long*. Possible future fixes (not built, need a team decision):
- let the timing agent **slow down** slightly (e.g. tempo down to 0.9) when a clip is far too short,
- or ask translation for a fuller line when it's much shorter than the slot.
Decide after watching the first full dubbed video (Stage 9).

## 7b. Update: filling short lines (2026-11-07, team decision after watching)

New rule `fill_tempo(duration, slot)`: if a fitting clip is shorter than **90 %** of the original speaking time, slow it toward the slot, but **never below 0.9×**. Status stays `fit`; `report.json` counts it as `slowed`. On the 2-min demo, 18–19 of 21 lines per language were slowed, and the voice filled 69–78 % of the speaking time instead of ~65 %.

## 7c. Update: fuller lines + 0.85× (2026-11-08, team: "lip sync little bit not nice")

True lip-sync stays out of scope; this improves **how much of the speaker's talking time the voice covers**.
- `MIN_SLOWDOWN` 0.9 → **0.85**.
- **Expand step:** if a fitting clip fills < **75 %** of the slot, ask Gemini **once** (`translate.expand_line`) for a fuller, natural line: same meaning, no new facts, about 92 % of the slot (≤ 1.5× chars). Rejected if it has digits or wrong-script letters; kept only if it still fits the budget; never loops. Then `fill_tempo` as before.
- `report.json`: `expanded`, `speech_coverage`; page shows "Fuller" and "Your dubbed voice fills X %".

| 2-min demo | Coverage before → after | Fuller | QA before → after |
|---|---|---|---|
| Tamil | 78 % → **90 %** | 10 | 96.3 → 97.7 % |
| Bengali | 69 % → **89 %** | 15 | 93.4 → 95.1 % |
| Marathi | 72 % → **92 %** | 14 | 96.9 → 98.3 % |

0 failed, 0 flagged, no wrong-script letters, no digits. Run: 105 Gnani + 49 Gemini calls (Gemini main models hit the daily quota; lite backup used). Tests: 173/173.

## 8. How this connects

- Stage 8 transcribes each final clip to check it says what we intended.
- Stage 9 places each final clip at its unit's `start` time over the music.
- `report.json` (Stage 10) counts fit / sped_up / rewritten / flagged.
