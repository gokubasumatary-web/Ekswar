# HANDOFF.md: Ekswar in one page (for Ananya)

> Last updated: 2026-11-07 · Branch: **`feature`** · Deadline: **Nov 10, 2026, 11:59 PM IST**

## What Ekswar is

A short **Hindi video** (≤ 3 min, one speaker) goes in. The same video comes out **dubbed into Tamil, Bengali or Marathi**, in the **creator's own cloned voice**, with every line **timed to the original** and the **background music kept**. It also writes subtitles (`.srt`) and a `report.json`.

**Main idea to demo: the Timing Agent.** It measures every dubbed line and fits it to the original time slot. It pads short lines, slows them slightly (≥ 0.9×), speeds long ones up (≤ 1.15×, or ≤ 1.25× after rewrites), or asks Gemini to **rewrite** them shorter. Lines that still don't fit get **flagged**. Words are never cut.

**It is timing sync, not lip-sync.** The lips in the video don't change. Always say this honestly.

## Status

| | |
|---|---|
| ✅ Stages 0–11 done | Pipeline, CLI, Streamlit page (with design + animations) |
| ⬜ Stage 12 left | README, written explanation, architecture diagram, demo video, LinkedIn post, submission |
| Tests | **164 / 164 pass** (`.venv\Scripts\python -m pytest -q`) |
| Real results | 2-min demo in 3 languages: 63 lines, 0 failed, QA 93–97 % |

## Models used

- **Gnani Prisma v2.5**: speech-to-text. Batch for the Hindi source; REST to check each dubbed line and to split long lines at pauses.
- **Gnani voice cloning `vachana-vc-v1`**: speaks every line in the creator's voice.
- **Google Gemini** (`gemini-3.6-flash`, backups `gemini-3.5-flash`, `gemini-3.5-flash-lite`): punctuation, translation, shortening.
- **Demucs** (local): separates voice from music. **ffmpeg** (local): all audio/video work.

## Set up on your laptop (Windows)

```powershell
git clone https://github.com/gokubasumatary-web/Ekswar.git
cd Ekswar
git switch feature
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
winget install --id Gyan.FFmpeg -e        # then open a NEW terminal
copy .env.example .env                     # ask Guthal for the keys; paste them into .env only
.venv\Scripts\python -m src.config         # checks everything (never prints keys)
.venv\Scripts\python -m pytest -q
```

## Run it

```powershell
# command line (one or more languages)
.venv\Scripts\python cli.py --video samples\your_video.mp4 --lang ta-IN,bn-IN,mr-IN --ref samples\your_voice.mp3 --names "Your Name"

# web page → http://localhost:8501
.venv\Scripts\streamlit run app.py
```
Outputs go to `outputs/runs/<video>/` (MP4 and SRT per language, plus `report.json`).

## Where things are

| Path | What |
|---|---|
| `src/pipeline.py` | Runs all steps in order (the CLI and the page both call it) |
| `src/gnani.py` · `src/llm.py` | Gnani and Gemini clients (cached, retries, quota handling) |
| `src/timing.py` | **Timing Agent** |
| `src/segment.py` · `src/units.py` · `src/translate.py` · `src/qa.py` · `src/mix.py` | Pause splitting, lines, translation, quality check, final mix |
| `app.py` · `src/ui_style.py` | Web page and its design |
| `PROJECT_CONTEXT.md` | Full design and decisions |
| `DEVELOPMENT_PLAN.md` | Stages and the day-by-day log |
| `docs/stages/STAGE_00…11.md` | Detail of every stage: what, why, tests, problems |
| `NOTES.md` | Every place the real APIs differed from their docs |

## Rules we follow

1. **Never put API keys in code, chat or GitHub.** Only in `.env` (git-ignored).
2. **Credits are limited.** Everything is cached, so re-runs are free. Test on short clips.
3. **Work on `feature`.** `main` is only touched at the end (final merge). Ask before pushing.
4. **Only your own voice / consent.** No real personal data (phone numbers, Aadhaar, PAN).
5. **Be honest:** "AI-dubbed", no lip-sync, translations not yet checked by native speakers.

## Known limits / open items

- **No lip-sync** (out of scope). The voice fills ~70–78 % of the original speaking time.
- **Gemini free tier** runs out after heavy use (per-minute and per-day limits). Ekswar switches models automatically; worst case, wait for the daily reset.
- **Gnani REST** sometimes returns 504; those lines are marked "not checked" and retried on re-run.
- **Before submission:** regenerate both API keys (they were shared in a chat), and get a native Tamil/Bengali speaker to check a few lines if possible.
- **Not built:** other directions (e.g. Tamil → Hindi), editing a single line in the page.

## Stage 12 to-do

- [ ] Each member's contribution (true, written by us)
- [ ] README (models, contributions, how to run, honest limits)
- [ ] Written explanation + architecture diagram
- [ ] Demo video (2–3 min): problem → upload → timing agent table → side-by-side result → honest limits
- [ ] LinkedIn / X post with #GnaniAI #GreatIndianAIInternshipChallenge
- [ ] Regenerate keys · merge `feature` → `main` · submit
