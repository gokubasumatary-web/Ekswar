# NOTES.md: where reality differed from the docs or the brief

Every time a real API response, limit or behaviour differs from the Gnani docs (or from our original brief), record it here: what we expected, what we saw, and what we changed in the code.

Format: **date · area · source of expectation**, then *Expected* / *Actual* / *Action*.

---

## Differences found while reading the docs (before any API call)

**2026-11-06 · Batch STT model name · brief vs docs**
- *Expected (brief):* `"model": "gnani-prisma-v2.5"`
- *Actual (docs, live-verified example):* `"model": "prisma-v2.5"` (case-insensitive)
- *Action:* use `prisma-v2.5`. Confirm on the first real batch call.

**2026-11-06 · REST STT max audio length · brief vs docs**
- *Expected (brief):* clips up to 60 s
- *Actual (docs):* max **30 s**; longer gives `400 MAX_AUDIO_DURATION_EXCEEDED`
- *Action:* the QA step skips clips over 30 s and marks them "not checked".

**2026-11-06 · Batch terminal states · brief vs docs**
- *Expected (brief):* COMPLETED, FAILED, PARTIAL_FAILURE
- *Actual (docs):* also `START_FAILED` and `CANCELLED`
- *Action:* treat all five as terminal when polling.

**2026-11-06 · Voice-clone embedding response · brief vs docs**
- *Expected (brief):* either `{embedding, shape, dtype}` or wrapped in `data.voice_clone_embedding`
- *Actual (docs):* only the wrapped form is documented
- *Action:* the code accepts both. Record which one the real API returns.

**2026-11-06 · Text normalization and Marathi · docs**
- *Docs:* TTS auto-detects language from script for normalization: Devanagari → Hindi. Voice cloning has no `language` field.
- *Risk:* Marathi (Devanagari) may be read with Hindi rules by the cloned voice.
- *Action:* write numbers as words ourselves; include Marathi in the voice test.

**2026-11-06 · Rate limits · docs**
- *Docs:* some accounts allow **one active request at a time**; `429` has **no Retry-After** header.
- *Action:* Gnani calls run one at a time; backoff of 2 s, 4 s, 8 s… (see `src/retry.py`).

**2026-11-06 · HTTP 500 can mean "text too long" · docs**
- *Action:* retry a 500 only once, then fail the unit (don't burn time or credits).

---

## Differences found from real API calls

**2026-11-06 · Auth check · `GET /stt/v3/batch/jobs`**
- *Actual:* HTTP 200, `{"data": [], "pagination": {"has_more": false, "next_cursor": null}}`. Matches the docs. Key valid for STT.

**2026-11-06 · Voice-clone embedding · `POST /api/v1/tts/voice-clone/embeddings`**
- *Sent:* 21.6 s mono 16-bit 44.1 kHz WAV (`audio/wav`).
- *Actual:* HTTP 200, top-level keys `data, message, success` → the **wrapped form** from the docs. `shape=[1, 768]`, `dtype=torch.bfloat16`, embedding = 4,096-character string. **Matches the docs.**
- *Action:* none; the parser accepts both forms anyway.

**2026-11-06 · Cloned-voice TTS · `POST /api/v1/tts/inference` (`vachana-vc-v1`)**
- *Sent:* Tamil, Bengali and Marathi text (native script, no digits), `audio_config {44100, linear_pcm, wav}`, no `language` field.
- *Actual:* HTTP 200, raw WAV bytes (`RIFF…WAVE`), **pcm_s16le, 44,100 Hz, mono**. Accepted Tamil, Bengali and Marathi script without error. **Matches the docs.** No 403, so the key has TTS/voice-clone scope.
- *Open:* whether pronunciation is good is a listening test, not an API fact.

**2026-11-07 · Prisma v2.5 batch STT · first real job** (`samples/chai_video.mp4`, voice stem, 27.35 s, 16 kHz mono, 0.88 MB)
- **Model name `prisma-v2.5` accepted.** Confirms the brief's `gnani-prisma-v2.5` was wrong.
- **Fast:** status was already `COMPLETED` at the first poll (about 1 s after start).
- **Transcript has `segments`** (not only `full_transcript`). Top-level keys: `created_at, duration_seconds, engine, file_id, full_transcript, job_id, language_code, mode, model, original_path, segments`.
  - *Differs from docs:* `engine: "go-batch-asr"` is present for **v2.5** (docs say v3.0 only).
  - *Differs from docs:* `segment_id` **counts up (0, 1)**; the docs example showed 0 for all. We still use list order, not `segment_id`.
  - *Differs from docs:* segments have **no `sentiment` / `emotion` keys** (docs show them as null); `confidence` and `language_detected` are null.
- **Segments are long:** only **2 segments** (14.5 s and 12.4 s), split at the one clear pause (~14.7–15.0 s). **No word-level timestamps.** → Stage 5 can't get sentence timings from Gnani alone.
- **No punctuation**, as expected. **English words come out transliterated in Devanagari** ("हे गाइस माय नेम इस…"). The source was code-mixed Hinglish.
- **Names can be misheard:** the speaker's name came out as "कुताल सुमठारी". `bias_list` might help (v2.5, single words, letters only).
- **API call count:** the client counted 7 HTTP calls for create + start + 1 status + files (expected 4) → **3 silent retries** happened (status unknown; they weren't logged then). Job list confirmed **only one job was created**. *Action:* `retry.py` now prints every retry; `create job` uses `safe_to_repeat=False` (only retried on 429) so a dropped connection can never create a duplicate paid job.
