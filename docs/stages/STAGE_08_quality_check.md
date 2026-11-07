# Stage 8: Quality check (Gnani Prisma REST)

**Status:** ✅ Done and tested (2026-11-07)
**Depends on:** [Stage 7](STAGE_07_timing_agent.md) (final dubbed clips)
**Next stage:** Stage 9: Mix + final video + subtitles

---

## 1. What we built

`src/qa.py` + `GnaniClient.transcribe_rest()`: for every final dubbed clip, **Gnani listens to it in the target language** and we measure how close what it heard is to what we intended.

## 2. Why Ekswar needs it

A 3-minute video has dozens of lines in 3 languages. Nobody can listen to all of them every time. The QA step automatically points at lines where the cloned voice may have **mumbled, skipped words or mispronounced** something.

**It is a warning light, not a verdict.** Speech-to-text writes things its own way (spelling variants, no punctuation), so a perfect clip still scores below 100%, and a high score doesn't prove perfect pronunciation.

## 3. How it works

```
final clip (Stage 7) ──► POST /stt/v3  {audio_file, language_code}  ──► "heard" text   (cached)
                                                                       │
intended translation ─────────────────────────────────────────────────┤
                                                                       ▼
              normalize both (lower-case, strip punctuation, keep all letters & vowel signs)
              similarity = rapidfuzz character ratio (0–100)
              similarity < 80  →  qa_flag
```

| Rule | Why |
|---|---|
| Clip > 30 s → "not checked" (no call) | Docs: REST max is 30 s |
| STT error → "not checked", run continues | QA must never stop the pipeline |
| Empty transcript → flagged, note "no speech heard" | Possible silent/broken clip |
| Default `format=verbatim` (numbers as words) | Matches our translations, which spell numbers out |
| Cached by (clip bytes + language) | No repeat charges |

## 4. Choosing the threshold (from real data)

| Comparison | Scores |
|---|---|
| Clip vs **its own** intended text (6 clips) | **93.7 – 98.3 %** |
| Clip vs the **wrong** line's text (simulated bad clip) | **36.7 – 47.5 %** |

The wrong-line scores aren't near 0 because lines share words (வாய்ஸ், টেস্ট, गाईज). **Threshold = 80 %**: well under the good scores, well over the bad ones, and it would also catch a partly garbled line. Small sample, so revisit on the 2–3 min video.

## 5. Files

| File | Purpose |
|---|---|
| [src/qa.py](../../src/qa.py) | `normalize`, `similarity`, `judge`, `check_clip`, `QA_THRESHOLD` |
| [src/gnani.py](../../src/gnani.py) | + `transcribe_rest()` (POST /stt/v3, cached) |
| [scripts/qa_test.py](../../scripts/qa_test.py) | Real run over Stage 7 clips → table + `qa.json` |
| [tests/test_qa.py](../../tests/test_qa.py) | 9 offline tests |

## 6. Results (2026-11-07)

**Tests:** 111/111 pass.

**Real run:** 6 Gnani REST calls (~0.12 s each on Gnani's side); re-run: 0 calls.

| Lang | Unit 0 | Unit 1 |
|---|---|---|
| Tamil | 95.7 % ok | 96.9 % ok |
| Bengali | 95.2 % ok | 93.7 % ok |
| Marathi | 98.3 % ok | 96.9 % ok |

Example (Tamil unit 1):
```
intended: பின்னாடி கொஞ்சம் சத்தம் கேட்கும்னு நினைக்கிறேன், தெரியல. இப்போ டெஸ்ட் பண்ணி பாப்போம் ...
heard:    பின்னாடி கொஞ்சம் சத்தம் கேட்கணும்னு நினைக்கிறேன் தெரியல இப்போ டெஸ்ட் பண்ணி பார்ப்போம் ...
```
Differences are spelling/colloquial variants (பாப்போம் / பார்ப்போம்), not missing words.

**What we can honestly claim:** Gnani's own STT recognised the cloned-voice dub as the intended text with 94–98 % character similarity on this test video. This supports intelligibility; it does **not** prove native-quality pronunciation.

## 7. Problems hit

None. The API matched the docs (see NOTES.md).

## 8. How this connects

- `report.json` (Stage 10) will include `qa_flags` count and average similarity.
- The Streamlit unit table (Stage 11) shows each line's QA score.
