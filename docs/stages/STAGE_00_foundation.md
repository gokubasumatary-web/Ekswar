# Stage 0: Foundation

**Status:** ✅ Done and tested (2026-11-06)
**Depends on:** nothing (first stage)
**Next stage:** [Stage 1: Voice test](STAGE_01_voice_test.md) *(not written yet)*

---

## 1. What we built

The base that every other stage stands on:

- a private Python environment for the project,
- ffmpeg (the audio/video tool),
- safe loading of API keys,
- a disk cache so we never pay twice for the same API call,
- one shared set of rules for handling API errors,
- offline tests that prove the above works.

No dubbing happens yet. This stage is the plumbing.

## 2. Why Ekswar needs it

| Problem | What solves it |
|---|---|
| Our packages could clash with other Python projects on the laptop | `.venv` (virtual environment) |
| API keys must never end up in code or on GitHub | `.env` + `.gitignore` + `src/config.py` |
| We only have **5,000 Gnani credits**; debugging re-runs the pipeline many times | `src/cache.py` |
| APIs fail sometimes (rate limits, outages, out of credit) | `src/retry.py` |
| We need proof the above works without spending credits | `tests/test_foundation.py` |

## 3. How each piece works

### 3.1 Virtual environment (`.venv`)
A folder with its own copy of Python and its own packages, used only by Ekswar.
- Python **3.13.7**. Why not another version: 3.11 isn't installed on this laptop, and 3.14 is too new for Demucs (Stage 2).
- Always run Python as `.venv\Scripts\python ...` so the project's packages are used.

### 3.2 ffmpeg
A command-line program that can cut, convert, speed up, mix and combine audio/video. Installed with `winget` (version 9.0.2). Used from Stage 1 onward.
> After installing, **restart VS Code / the terminal**, or it won't be found.

### 3.3 Secrets: `.env`, `.env.example`, `.gitignore`
- `.env.example` is a **template** with empty values. It *is* committed so teammates know which keys are needed.
- `.env` holds the **real keys**. It is **never** committed.
- `.gitignore` tells Git which files to never track: `.env`, `.venv/`, `cache/`, `outputs/`, audio/video files.

### 3.4 `src/config.py`: settings
- Loads `.env` automatically.
- `get_setting("GNANI_API_KEY")` returns the key, or raises a clear error naming the missing variable. **It never prints the value.**
- `find_tool("ffmpeg")` finds ffmpeg or explains what to install.
- Holds shared constants: Gnani base URL `https://api.vachana.ai`, target languages (`ta-IN`, `bn-IN`, `mr-IN`), and the `cache/` and `outputs/` paths.
- Run `python -m src.config` for an environment check.

### 3.5 `src/cache.py`: the credit saver
Think of it as a **fingerprint system**:
1. Before calling an API, we take everything that affects the answer (text, model, settings, audio bytes) and compute a **SHA-256 hash**, a 64-character fingerprint.
2. Same inputs → same fingerprint. Change even one character → completely different fingerprint.
3. The result is saved as `cache/<kind>/<fingerprint>.json` (or `.wav`).
4. Next time, if that file exists, we return it **without calling the API**: zero credits.

Safety rules:
- **Only successes are saved**, never errors.
- Files are written **atomically**: first to a temp file, then renamed. If the program crashes mid-write, no half-written file is left looking like a real result.
- It counts **hits** (served from disk) and **misses** (real API calls), useful for the metrics report.

### 3.6 `src/retry.py`: what to do when an API call fails
Every HTTP response has a status code. Our rules (based on the Gnani docs):

| Status | Meaning | What we do |
|---|---|---|
| 2xx | Success | Return the result |
| 429 | Too many requests | Wait and retry: 2 s, 4 s, 8 s… (Gnani sends no "wait this long" hint) |
| 503 / 504 | Service down / timed out | Same as 429 |
| 500 | Server error, can mean "text too long" | Retry **once** only |
| 400 / 422 | Our request is wrong | Don't retry; that one unit fails, the run continues |
| 401 / 402 / 403 | Bad key / **no credit** / no permission | **Stop the whole run** |
| Network drop | Connection lost | Retry like 503 |

Two kinds of errors come out of it:
- `RequestError`: one item failed, keep going.
- `FatalAPIError`: stop everything.

It's written so tests can pass in fake responses and a fake "sleep", so tests run instantly with no internet.

## 4. Files created

```
.gitignore              files Git must never track
.env.example            key template (committed)
.env                    real keys (NOT committed)
requirements.txt        Python packages + versions
src/__init__.py         marks src/ as a Python package
src/config.py           settings, keys, tool lookup, env check
src/cache.py            disk cache keyed by SHA-256
src/retry.py            retry/stop rules for HTTP calls
tests/__init__.py
tests/test_foundation.py  13 offline tests
```

Packages installed: `requests`, `python-dotenv`, `rapidfuzz`, `pytest` (exact versions in `requirements.txt`).

## 5. How we tested it

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m src.config
```

What the 13 tests prove:
- Same inputs give the same fingerprint; a one-character change gives a different one.
- Saved results come back identical.
- A second request for the same thing is **served from cache**: the expensive function runs only once.
- **Failed calls are not cached** and leave no temp files.
- 429 → waits 2 s then 4 s, then succeeds.
- 500 → retried exactly once.
- 401/402/403 → stops immediately.
- 400 → not retried.
- Gives up after the maximum number of attempts.
- Network errors are retried.

## 6. Results

```
13 passed in 0.07s

[OK ]     Python          3.13.7
[OK ]     ffmpeg          (winget install, 9.0.2)
[OK ]     ffprobe
[OK ]     GNANI_API_KEY   set
[MISSING] GEMINI_API_KEY  (needed from Stage 4)
[MISSING] GEMINI_MODEL    (needed from Stage 4)
```

**Gnani key check:** `GET /stt/v3/batch/jobs` (free, read-only) → **HTTP 200**, empty job list. The key is valid for speech-to-text. Voice-clone access is confirmed in Stage 1.

## 7. Problems we hit and how we fixed them

| Problem | Cause | Fix |
|---|---|---|
| Environment check said ffmpeg was missing right after installing it | The terminal was opened before the install, so it had the old program list (PATH) | Open a new terminal / restart VS Code. Verified by adding ffmpeg's folder to PATH manually. |
| No Python 3.11 for the planned environment | Not installed on the laptop | Used Python 3.13 instead (3.14 too new for Demucs) |
| The API key was pasted into chat | n/a | It's in `.env` (git-ignored). **Regenerate the key in the Gnani dashboard before submission.** |

## 8. How this connects to the rest of Ekswar

- **Every Gnani call** (Stages 1, 3, 8) goes through `retry.py` and `cache.py`.
- **Every Gemini call** (Stages 4–7) uses the same cache.
- **Every stage** reads settings from `config.py`.
- The cache hit/miss counters feed `report.json` (Stage 10).

## 9. Setup for a teammate (e.g. Ananya on another laptop)

```powershell
git clone https://github.com/gokubasumatary-web/Ekswar.git
cd Ekswar
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
winget install --id Gyan.FFmpeg -e      # then restart the terminal
copy .env.example .env                   # then fill in the keys
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m src.config
```
