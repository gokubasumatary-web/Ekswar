# Stage 6: Translation

**Status:** ✅ Done and tested (2026-11-07) · ⏸ native-speaker check and the correct name spelling still wanted
**Depends on:** [Stage 4](STAGE_04_llm.md) (Gemini) · [Stage 5](STAGE_05_units.md) (units)
**Next stage:** Stage 7: Timing agent

---

## 1. What we built

`src/translate.py`: `translate_units(units, lang, llm, names=[])` translates every unit into **Tamil (`ta-IN`), Bengali (`bn-IN`) or Marathi (`mr-IN`)** with **one Gemini call per unit**, then checks each result.

## 2. Why Ekswar needs it

This is the "every Indian language" part. The translation must be:
- **natural spoken language** (it will be *said* in the creator's voice, not read),
- **short enough** to fit the original time slot,
- **easy for TTS to pronounce** (numbers as words),
- **faithful** (same meaning, names untouched).

## 3. How it works

### The prompt (per unit)
| Part | Why |
|---|---|
| Whole transcript as context | Gemini understands the topic, not just one line |
| "natural, spoken {language}, like a creator on camera" | Dubbing needs casual speech, not textbook style |
| Common English words may stay (in the target script) | Real Indian creators say "video", "voice", "test" |
| **All numbers as words, no digits** | Brief + Gnani docs: digits get mispronounced; cloned voice has no language field |
| Names not translated; optional name list | Names must sound the same |
| **"at most N characters"** | Fewer re-tries in the timing agent |
| JSON `{"translation": "..."}` | Reliable parsing |

### Character budget
```
budget = slot × chars_per_second[language] × 0.9
```
| Language | chars/s (cloned voice, Stage 1) |
|---|---|
| Tamil | 17.7 |
| Bengali | 13.5 |
| Marathi | 14.7 |

⚠️ Measured on **one sentence each**, so these are rough starting values. Stage 7 measures every real clip anyway.

### Checks after each translation (flags, never crashes)
| Flag | Meaning |
|---|---|
| `digits_found` | Any digit in any script (0-9, ௫, ৫ …) |
| `script_ratio` / `script_ok` | Share of letters in the right script (≥ 80% = OK) |
| `over_budget` | Longer than the character budget |
| `error` | Gemini failed for this unit; the other units continue |

## 4. Files

| File | Purpose |
|---|---|
| [src/translate.py](../../src/translate.py) | `char_budget`, `script_ratio`, `has_digits`, `build_prompt`, `check`, `translate_units` |
| [scripts/translate_test.py](../../scripts/translate_test.py) | Live run: all 3 languages, table, JSON per language |
| [tests/test_translate.py](../../tests/test_translate.py) | 16 offline tests |

## 5. How we tested it

**Offline:** budget math per language; script detection (Tamil / Bengali / Devanagari; Hindi text is *not* Tamil); digits in any script; prompt contains context, budget and names; cleanup of quotes/spaces; over-budget flag; **one failed unit doesn't stop the others**; wrong-script warning; unknown language rejected.

**Live:**
```powershell
.venv\Scripts\python -m scripts.translate_test outputs\units\chai_video.json
.venv\Scripts\python -m scripts.translate_test outputs\units\chai_video.json --names "<correct name>"
```

## 6. Results (2026-11-07)

**Tests:** 74/74 pass.

**Live:** 6 Gemini calls (2 units × 3 languages), **main model answered every time** (backup used 0×). Re-run: **0 calls**.

| Unit | Slot | Hindi | Tamil | Bengali | Marathi |
|---|---|---|---|---|---|
| 0 | 14.52 s | 187 ch | 164 / 231 | 161 / 176 | 187 / 192 |
| 1 | 12.36 s | 145 ch | 145 / 196 | 100 / 150 | 118 / 163 |

(chars / budget). **All within budget, 100% correct script, no digits, no errors.**

```
Tamil   0: ஹாய் காய்ஸ், என் பேரு குதால் சுமடாரி. என்னோட வாய்ஸ் உங்களுக்கு கேக்குதுனு நினைக்கிறேன். ...
Bengali 0: হে গাইজ, আমার নাম কু তাল সুমঠারি আর আই থিংক তোমরা আমার ভয়েস শুনতে পাচ্ছো। ...
Marathi 0: हे गाईज, माझं नाव कुताल सुमठारी आहे आणि आय थिंक तुम्हाला माझा व्हॉईस ऐकू येत असेल. ...
```
Full output: `outputs/translations/chai_video.<lang>.json`.

## 7. Observations (honest)

- **Style is casual and spoken** ("பண்றேன்", "দেখা যাক গাইজ", "चला बघूया गाईज"), which is what we asked for.
- **The misheard name spreads into every language, spelled differently each time:** Tamil "குதால் சுமடாரி", Bengali "কু তাল সুমঠারি", Marathi "कुताल सुमठारी". → Use `--names` with the correct spelling.
- **Quality not verified by native speakers.** The Marathi reads naturally; Tamil and Bengali look fluent but need a native check before we claim anything.
- Even with the budget, the translations are similar in length to the Hindi. Whether they *fit in time* is only known after speaking them, which is Stage 7's job.

## 8. How this connects

- Stage 7 speaks each translation with the cloned voice, measures it, and shortens it if needed.
- Stage 9 uses the translations for the subtitles.
