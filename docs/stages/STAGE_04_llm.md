# Stage 4: LLM layer (Gemini)

**Status:** ✅ Done and tested (2026-11-07)
**Depends on:** [Stage 0](STAGE_00_foundation.md) (cache, retry)
**Next stage:** Stage 5: Units (cleanup + segmentation)

---

## 1. What we built

`src/llm.py`: the **one and only** place Ekswar talks to an LLM. One main function:

```python
LLM().ask_json(prompt, schema=None, what="label")  # -> parsed JSON (dict or list)
```

## 2. Why Ekswar needs it

Three later stages need a language model:
| Stage | Job |
|---|---|
| 5 | Add punctuation to Gnani's transcript, split/merge into sentences |
| 6 | Translate each sentence into Tamil / Bengali / Marathi |
| 7 | Shorten a translation that's too long for its time slot |

Keeping it behind **one function** means: one place for caching, retries and error handling, and if Gemini is a problem we can swap providers by editing only this file. **[BRIEF rule]** Gnani's own LLM (Evon) is not on the API, so we use Gemini.

## 3. How it works

```
ask_json(prompt, schema)
   │ build body: contents + generationConfig {
   │     responseMimeType: "application/json",   ← reply must be JSON
   │     responseJsonSchema: schema,             ← optional exact shape
   │     thinkingConfig: {thinkingLevel: "LOW"}  ← Gemini 3: think a little, answer fast
   │ }
   │ cache key = hash(model + body)  → hit? return it, 0 calls
   ▼
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent
   header x-goog-api-key (never logged)
   │ retries: 429/503/network → back off (up to 6 tries, waits up to 60 s, all printed)
   │          404 (wrong model) → STOP the run;  403 → STOP the run
   ▼
check answer:
   - prompt blocked (promptFeedback.blockReason)? → error for this item
   - finishReason ≠ STOP (e.g. MAX_TOKENS cut off)? → error
   - skip "thought" parts, keep the real answer text
   - parse JSON (tolerates a ```json fence)
   - not JSON? → ONE stricter re-ask, then error
   ▼
cache the answer → return it
```

### Decisions
| Decision | Why |
|---|---|
| **Plain HTTP (`requests`), not the Google SDK** | No new library; Gemini uses the **same cache + retry rules** as Gnani; easy to swap |
| **`gemini-3.8-flash`** | Newest stable Flash text model on our key. `gemini-2.5-flash` returned 404 "no longer available to new users". |
| **JSON mode** | Later stages need structured answers (e.g. `{"translation": ..., "chars": ...}`), not chatty text |
| **thinkingLevel LOW** | Translation doesn't need deep reasoning; faster replies |
| **No temperature** | Ignored by Gemini 3.6+ (docs) |
| **Timeout 60 s** | When overloaded, Gemini sometimes *hangs* instead of replying 503. 60 s limits the damage. |

## 4. Files

| File | Purpose |
|---|---|
| [src/llm.py](../../src/llm.py) | `LLM.ask_json()`, `build_body()`, `extract_text()`, `parse_json_text()`; `python -m src.llm` = live check |
| [tests/test_llm.py](../../tests/test_llm.py) | 10 offline tests (fake Gemini) |
| `.env` | `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.8-flash` |

## 5. How we tested it

**Offline (fake Gemini, no quota):**
- Request asks for JSON + LOW thinking, no temperature
- "Thought" parts ignored
- Blocked prompt / no candidates / cut-off answer → clear error
- ```json fences tolerated
- **Same question twice → 1 real call** (cache)
- Non-JSON answer → exactly one strict re-ask
- 503, 503, 200 → retried and succeeds
- Wrong model (404) → stops the run with a message naming `GEMINI_MODEL`

**Live:**
```powershell
.venv\Scripts\python -m src.llm
```

## 6. Results

- **Tests:** 40/40 pass (whole project).
- **Key check:** `GET /v1beta/models` → 200 (free); 23 Flash-family models listed.
- **Live:** `"नमस्ते दोस्तों"` → `{"ta": "வணக்கம் நண்பர்களே"}` ("Hello friends" in Tamil) ✅
- **Re-run:** `real calls=0` (cache) ✅

## 7. Problems hit

| Problem | What we did |
|---|---|
| `gemini-2.5-flash` → 404 for new users | Use `gemini-3.8-flash` (what Google's error suggests) |
| `gemini-3.8-flash` & `3.7-flash` → **503 "high demand"** several times | Temporary on Google's side; our retry handles it |
| One run: **all 6 attempts hung 120 s each** (~12 min) then failed | Timeout cut to 60 s; the failure was a clear error, not a crash or silent skip. A retry minutes later worked instantly. |
| The Gemini key was pasted in chat | It's in `.env` only. **Regenerate before submission.** |

**Update (Stage 5):** the overload lasted over an hour, so we switched to `gemini-3.6-flash` and added an automatic **backup model** (`GEMINI_FALLBACK_MODEL=gemini-3.5-flash`). See [Stage 5 §4](STAGE_05_units.md).

**Risk to remember:** Gemini overload can slow the full pipeline (dozens of calls per video). Caching means a re-run only re-asks the items that failed.

## 8. How this connects

- Stage 5 will call `ask_json()` with the Gnani transcript → punctuated sentences.
- Stage 6 will call it per sentence → translation within a character budget.
- Stage 7 will call it to shorten lines that don't fit.
