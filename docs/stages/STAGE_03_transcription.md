# Stage 3: Hindi transcription (Gnani Prisma v2.5 Batch)

**Status:** ✅ Done and tested (2026-11-07)
**Depends on:** [Stage 0](STAGE_00_foundation.md) (cache, retry) · [Stage 2](STAGE_02_audio_prep.md) (voice-only 16 kHz file)
**Next stage:** Stage 4: Gemini LLM layer

---

## 1. What we built

`GnaniClient.transcribe_batch()` in `src/gnani.py`: it sends the voice track to **Gnani Prisma v2.5** and gets back the Hindi words **with start/end times**.

## 2. Why Ekswar needs it

Everything after this depends on two things only Prisma gives us:
- **what was said** → to translate it,
- **when it was said** → so the dubbed line goes in the same place (the timing agent's slot).

We use the **Batch** API, not REST, because REST only accepts ≤30 s and our videos go up to 3 min.

## 3. How it works

The batch API is like a courier office: drop off, then check back.

```
1. POST /stt/v3/batch/jobs            upload file + config   → job_id   (status CREATED)
   └─ job_id saved to cache/stt_batch_job/ IMMEDIATELY
2. POST /stt/v3/batch/jobs/{id}/start  begin processing        (creating ≠ starting!)
3. GET  /stt/v3/batch/jobs/{id}        poll every 10 s until COMPLETED / FAILED / ...
4. GET  /stt/v3/batch/jobs/{id}/files  → transcript_url (pre-signed, expires in 1 h)
5. GET  transcript_url                 → transcript JSON → cache/stt_batch/
```

Config sent:
```json
{"model": "prisma-v2.5", "language_code": "hi-IN", "mode": "transcribe",
 "with_diarization": false, "is_multi_channel": false}
```

### Credit-safety features
| Feature | What it prevents |
|---|---|
| Result cached by (file fingerprint + config) | Paying again for the same audio |
| Job id saved right after creation; resumed on re-run | A crash while waiting creating a **second** paid job |
| `create job` is `safe_to_repeat=False`: retried only on 429 | A dropped connection after Gnani already created the job → duplicate job |
| Poll interval exactly 10 s | Breaking the docs' rule (and hitting rate limits) |
| Download link fetched **without** our API key | Sending the key to Amazon S3, which doesn't need it |

### Retries are never silent (changed in this stage)
`retry.py` now prints a line for every retry, e.g.
`[retry] batch STT status: HTTP 429 ...; waiting 2 s (attempt 1/5)`.

## 4. Files

| File | Change |
|---|---|
| [src/gnani.py](../../src/gnani.py) | + `transcribe_batch()`, `batch_config()`, constants |
| [src/retry.py](../../src/retry.py) | + `on_retry` (log every retry), + `safe_to_repeat` |
| [scripts/transcribe_test.py](../../scripts/transcribe_test.py) | Video → separate → transcribe → table + raw JSON |
| [tests/test_gnani_batch.py](../../tests/test_gnani_batch.py) | 4 tests with a fake Gnani server |
| [tests/test_foundation.py](../../tests/test_foundation.py) | + 5 tests for the new retry rules |

## 5. How we tested it

**Offline (fake server, no credits):**
- Full flow in the right order (create → start → poll → files → download); polls every 10 s.
- **Second call = zero API calls** (cache).
- **Crash while waiting, then re-run → still only 1 job created and 1 start.**
- Failed job → clear error, nothing cached.
- Not-safe-to-repeat requests never resend after 500/503/network errors, but do retry 429.

**Real:**
```powershell
.venv\Scripts\python -m scripts.transcribe_test samples\chai_video.mp4
```

## 6. Results

**Tests:** 30/30 pass.

**Real run on `chai_video.mp4` (27.35 s):**
```
job created: 01a1b270-d5d5-7b93-882f-c65ab594112c
job started
status: COMPLETED (0 s)

 #  start    end   len  text
 0   0.20  14.72 14.52  हे गाइस माय नेम इस कुताल सुमठारी एंड आई थिंक यू आर हियरिंग माई वॉइस सो मेरा वौइस् आप लोगों को सुनाई दे रहा होगा बस मैं ये वीडियो रिकॉर्ड कर रहा हूँ वैसे मेरा वौइस् टेस्टिंग के लिए सो
 1  14.99  27.35 12.36  पीछे शायद मेरे कुछ आवाजें आ रही होंगी पता नहीं अभी टेस्ट करके देखते हैं मेरा वौइस् कैसा होगा कैसा नहीं होगा तो फिर देखते हैं गाइस क्या होगा
```
- Raw JSON saved: `outputs/transcripts/chai_video.json`.
- Re-run: **0 API calls** (cached).
- Job list check: **exactly 1 job** exists.

## 7. What we learned (important for later stages)

| Finding | Impact |
|---|---|
| **Only 2 segments, ~13–14 s each**, split at the one clear pause. **No per-word times.** | Stage 5 can't get *sentence* timings from Gnani alone. See the options below. |
| **No punctuation**, all one stream of words | Gemini adds punctuation in Stage 5 (as planned) |
| **English words written in Hindi script** ("हे गाइस माय नेम इस") | Fine for translation; Gemini understands it |
| **The speaker's name was misheard** ("कुताल सुमठारी") | Names should go in a do-not-translate list, and we could try `bias_list` |
| Very fast (done by the first poll) | Processing time isn't a concern for transcription |
| The test speech was free-form Hinglish, not the chai script | Fine: real creators talk like this |

### Open design question for Stage 5: segments are too long
A 14 s segment has several sentences, but we only know when the *whole segment* starts and ends. Options (decide in Stage 5):
1. **Treat each segment as one unit** (simplest). The timing agent fits the whole 14 s block. Drift *inside* the block is possible but bounded.
2. **Split by silence locally:** find short pauses in `vocals.wav` with ffmpeg (free), cut the segment into sentence-sized pieces, and share the text across them using Gemini.
3. **Re-transcribe each silence-chunk with Prisma REST** (≤30 s each): exact text per chunk, but costs extra calls.

## 8. Problems hit

| Problem | Fix |
|---|---|
| 7 HTTP calls counted instead of 4: retries happened **silently** | Every retry is now printed; verified only 1 job exists |
| Risk: retrying "create job" after a network drop could double-charge | `safe_to_repeat=False` for create (only 429 retried) |

## 9. How this connects

- Stage 5 turns these segments into units with `start / end / slot / gap`.
- Stage 6 translates the text; Stage 7 uses the slots.
