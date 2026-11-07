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

**2026-11-07 · Gemini docs moved**
- `ai.google.dev/...` docs now redirect to `aistudio.google.com/docs/...`. Docs push the new **Interactions API**, but `POST /v1beta/models/{model}:generateContent` is still listed as current (no deprecation). We use generateContent.
- For Gemini 3.6+ models `temperature/topP/topK` are ignored (future 400), so we don't send them. Gemini 3 uses `thinkingConfig.thinkingLevel`.

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

**2026-11-07 · Gemini key + models**
- Key format starts with `AQ.` (not the familiar `AIza…`), and it works: `GET /v1beta/models` → 200.
- **`gemini-2.5-flash` → 404 "no longer available to new users… use gemini-3.8-flash".** Chosen: **`GEMINI_MODEL=gemini-3.8-flash`** (newest stable Flash text model in our model list).
- **Overload behaviour:** `gemini-3.8-flash` and `gemini-3.7-flash` both returned **503 "high demand"** several times; on one run all 6 attempts **hung until the 120 s read timeout** (no 503 at all). A few minutes later the same request answered at once.
  - *Action:* LLM timeout lowered to 60 s; retries (up to 6, backoff to 60 s) are logged; failure raises a clear `RequestError` for that unit.
- **First successful call:** Hindi "नमस्ते दोस्तों" → Tamil `{"ta": "வணக்கம் நண்பர்களே"}` (JSON mode). Re-run: 0 calls (cache).

**2026-11-07 · Prisma v2.5 REST STT · `POST /stt/v3` (QA of dubbed clips)**
- *Sent:* multipart `audio_file` (44.1 kHz mono WAV, 12–15 s) + `language_code` (`ta-IN` / `bn-IN` / `mr-IN`); no `model` (= v2.5 default), no `format` (= verbatim).
- *Actual:* HTTP 200, keys `success, request_id, transcript, model ("prisma-v2.5"), processing_time, end_to_end_latency`. **Matches the docs.** No `output.literal` field (docs mention it for v2.5). Very fast: ~0.12 s processing.
- Transcripts have no punctuation; spelling variants vs Gemini's text (e.g. Tamil "பாக்கலாம்" vs "பார்க்கலாம்").

**2026-11-07 · Gemini free-tier quotas: same message for per-minute AND per-day (verified)**
- 2-min demo × 3 languages + retries used up the free daily quota of `gemini-3.6-flash` and `gemini-3.5-flash`. 429 body: "You exceeded your current quota…".
- **The same message is used for per-minute limits.** We first treated every quota 429 as daily and skipped models for the whole run → lines failed although `gemini-3.5-flash-lite` worked again a minute later.
- **Verified real details:** `error.details[].violations[].quotaId` = `GenerateRequestsPerDayPerProjectPerModel-FreeTier` or `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`; a `retryDelay` (e.g. "52s") was used as the pause.
- *Actions:* quota 429 → no same-model retries, switch model; **PerDay** → skip the model for the run; otherwise **pause** it (retryDelay, default 60 s); all paused → wait for the first one. Backup chain `gemini-3.5-flash,gemini-3.5-flash-lite`.
- **Lite model sometimes wrote a whole Bengali line in Devanagari**, and the bad answer was cached. *Action:* `ask_json(validate=...)`: answers failing the script check are never cached and the next model is tried; old cached invalid answers are ignored.

**2026-11-07 · Gnani REST STT: intermittent HTTP 504 (HTML gateway page)**
- During the first full CLI runs, `POST /stt/v3` often returned **504 with an HTML page** (a gateway/proxy page, not the JSON error envelope in the docs). Sometimes 5 tries in a row failed; minutes later the same clip passed.
- We first suspected our ~4.8 s padding silence (a speech-only upload of the failing clip answered in 0.8 s), but **later runs got 504s on speech-only clips in all languages**. Conclusion: intermittent server-side errors, not caused by the clip.
- *Actions:* QA now sends **speech only, 16 kHz mono** (smaller, judges the speech not the padding); HTML bodies are summarised in logs instead of dumped; a clip that keeps failing is marked **"not checked"** (never "passed"); re-running retries only the missing checks (everything else cached). All 6 clips eventually checked.
- *Open:* whether 504'd attempts consume credits is unknown (no credits API).

**2026-11-07 · Gemini copies Devanagari letters into Bengali names**
- Translating unit 0 to Bengali with the name hint "गुथल बसुमतारी", Gemini wrote **"গুथल"**: Hindi letters "थल" inside a Bengali word, twice (also with the English spelling added to the hint). The 80 % script-ratio check passed it (98–99 %).
- *Action:* new `mixed_script` check (any letter from another Indian script block = not OK) + **one targeted re-ask** naming the wrong letters. Result: "গুথাল বাসুমাতারি" (pure Bengali) on the first re-ask.

**2026-11-07 · Gemini overload lasted over an hour · model probe**
- 30 s-limit probe of one tiny request each: `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-flash-latest` → **timeout**; `gemini-3.6-flash` 200 in 3.8 s; `gemini-3.5-flash` 200 in 3.5 s; `gemini-3.5-flash-lite` / `gemini-flash-lite-latest` 200 in ~2 s. All gave the correct Tamil.
- *Action (team decision):* `GEMINI_MODEL=gemini-3.6-flash`, new optional `GEMINI_FALLBACK_MODEL=gemini-3.5-flash`. Main model gets 3 tries / 45 s; on busy/unreachable, the backup is asked (logged `[fallback]`).
