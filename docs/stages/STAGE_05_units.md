# Stage 5: Units (cleanup + segmentation)

**Status:** ✅ Done and tested (2026-11-07)
**Depends on:** [Stage 3](STAGE_03_transcription.md) (transcript) · [Stage 4](STAGE_04_llm.md) (Gemini)
**Next stage:** Stage 6: Translation

---

## 1. What we built

`src/units.py` turns Gnani's raw transcript into **units**. A unit is one line that will be translated, spoken in the cloned voice, and fitted into its time slot.

```json
{"id": 0, "start": 0.2, "end": 14.72, "slot": 14.52, "gap": 0.27,
 "text_raw": "हे गाइस माय नेम इस ...", "text": "हे गाइस, माय नेम इस ...।", "punctuation_ok": true}
```

| Field | Meaning |
|---|---|
| `start`, `end` | When the original line was spoken (seconds) |
| `slot` | `end − start`: how long the original took |
| `gap` | Silence after it, until the next unit (last unit: until the end of the audio) |
| `text_raw` | Exactly what Gnani heard |
| `text` | Same words + punctuation (from Gemini) |
| `punctuation_ok` | False if we had to fall back to `text_raw` |

`slot` and `gap` feed the timing agent's budget in Stage 7: `budget = slot + 0.5 × gap`.

## 2. Why Ekswar needs it

- **Translation needs sentences**, not a stream of unpunctuated words.
- **Timing needs a slot per line.**
- **Tiny fragments** (e.g. a 0.4 s "हाँ") make bad translations and bad timing, so they're merged.

## 3. How it works

```
Gnani transcript JSON
  │ segments_from_transcript()  read segments; none? → full_transcript as 1 unit + WARNING
  ▼
  │ merge_tiny()                segments < 1.0 s joined to the closer neighbour
  ▼
  │ build_units()               slot = end − start; gap = next.start − end
  ▼
  │ punctuate()                 ONE Gemini call for the whole video:
  │                             "add punctuation only, same number of lines, don't change words"
  │                             check each line: words unchanged (≥95% similar)?
  │                                yes → use it   no → keep text_raw + WARNING
  │                             Gemini fails entirely → keep text_raw for all + WARNING
  ▼
units
```

### Team decision: option A
Each Gnani segment = one unit. Gnani gives no per-word times, so we can't place sentences *inside* a segment. Option A is simple and reliable; if sync looks bad inside long units after the first full video, we upgrade to option C (re-transcribe pause-chunks with Gnani REST).

### "Same words" check
Gemini sometimes "improves" text, e.g. fixing grammar or translating English words. That would make the dub say something the creator never said. So we strip punctuation from both versions and compare them (rapidfuzz). Below 95% similar → we reject Gemini's version for that line.

**Bug caught while building:** Python's regex `\w` doesn't treat Hindi **vowel signs** (ि े ं ्) as letters, so "नमस्ते" would be chopped into pieces. Fixed by removing only real punctuation/symbols (Unicode categories P and S). A test covers it.

## 4. Gemini backup model (added in this stage)

Gemini 3.8 Flash was **overloaded for over an hour** (503s and 60–120 s hangs), and Stage 5's first live run fell back to unpunctuated text. A probe showed older models answering in ~3 s. **Team decision:**

```
GEMINI_MODEL=gemini-3.6-flash           # newest model answering quickly
GEMINI_FALLBACK_MODEL=gemini-3.5-flash  # used only if the main one is busy
```

How `llm.py` uses the backup:
1. Look for a cached answer from **either** model → 0 calls.
2. Main model: **3 tries, 45 s timeout** (shorter than normal, so we switch sooner).
3. Still busy/unreachable (429, 5xx, timeout, connection) → print `[fallback] ...` → backup model with the normal 6 tries.
4. **Not** used for blocked prompts or bad JSON (the backup would fail the same way, so the call would be wasted).

## 5. Files

| File | Purpose |
|---|---|
| [src/units.py](../../src/units.py) | `segments_from_transcript`, `merge_tiny`, `build_units`, `words_only`, `same_words`, `punctuate`, `make_units` |
| [src/llm.py](../../src/llm.py) | + backup model logic |
| [scripts/units_test.py](../../scripts/units_test.py) | Live run on a saved transcript |
| [tests/test_units.py](../../tests/test_units.py) | 15 offline tests |
| [tests/test_llm.py](../../tests/test_llm.py) | + 4 backup-model tests |

## 6. How we tested it

**Offline:**
- Segments read in time order; empty ones dropped; fallback to `full_transcript` warns
- Tiny segment merges into the *closer* neighbour; first-segment case; single-segment case
- Slot/gap math matches the real transcript (14.52 / 0.27, 12.36 / 0.00)
- Hindi vowel signs survive punctuation stripping
- Punctuation accepted when words are the same; **rejected when Gemini reworded**
- Wrong line count or Gemini failure → raw text, no crash
- Backup: busy main → backup answers; timeouts → backup; blocked prompt → no backup call; no backup configured → 6 normal tries

**Live:**
```powershell
.venv\Scripts\python -m scripts.units_test outputs\transcripts\chai_video.json
```

## 7. Results

**Tests:** 58/58 pass.

**First live run (Gemini 3.8 overloaded):** retries logged, then `WARNING: punctuation step failed … using unpunctuated text`. Units still produced, `ok = N`. **The fallback path worked as designed.**

**After switching to 3.6 + backup:**
```
id  start    end   slot   gap  ok  text
 0   0.20  14.72  14.52  0.27  Y   हे गाइस, माय नेम इस कुताल सुमठारी एंड आई थिंक यू आर हियरिंग माई वॉइस। सो मेरा वौइस् आप लोगों को सुनाई दे रहा होगा। बस मैं ये वीडियो रिकॉर्ड कर रहा हूँ वैसे मेरा वौइस् टेस्टिंग के लिए, सो?
 1  14.99  27.35  12.36  0.00  Y   पीछे शायद मेरे कुछ आवाजें आ रही होंगी, पता नहीं। अभी टेस्ट करके देखते हैं मेरा वौइस् कैसा होगा, कैसा नहीं होगा। तो फिर देखते हैं गाइस, क्या होगा?

Units: 2   Gemini real calls: 1
```
- Words unchanged on both lines (`ok = Y`). Punctuation is mostly natural; "सो?" at the end of unit 0 is a little odd but harmless.
- Re-run: **0 Gemini calls** (cache).
- Saved: `outputs/units/chai_video.json`.

## 8. Known limits (honest)

- **Only 2 units for 27 s**, because Gnani split only at the one clear pause. Long units → sentences inside can drift. Revisit after the first full dub.
- **The misheard name "कुताल सुमठारी" stays wrong**, because we don't let Gemini change words. A do-not-translate / correction list is needed in Stage 6.
- The last unit has `gap = 0`: its dub must fit within its own slot.

## 9. How this connects

- Stage 6 translates each unit's `text`, with a character budget based on `slot`.
- Stage 7 computes `budget = slot + 0.5 × gap` per unit.
- Stage 9 writes subtitles from units' `start`/`end`.
