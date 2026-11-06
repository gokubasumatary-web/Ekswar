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

*(none yet: no API calls made)*
