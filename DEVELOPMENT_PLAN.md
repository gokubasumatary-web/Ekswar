# DEVELOPMENT_PLAN.md: Ekswar build plan and progress log

> Team: Arhant + Ananya. We build **one working, tested component at a time**, in dependency order.
> Approach: **Understand → Plan → Build → Test → Verify → next component.**
> This file is updated after every stage. For the full design, see [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md). For API surprises, see [NOTES.md](NOTES.md).

**Stage docs:** every stage gets its own detailed write-up in [docs/stages/](docs/stages/):
- [Stage 0: Foundation](docs/stages/STAGE_00_foundation.md) ✅
- [Stage 1: Voice test](docs/stages/STAGE_01_voice_test.md) ✅ GO: cloned voice for all 3 languages
- [Stage 2: Audio prep](docs/stages/STAGE_02_audio_prep.md) ✅ synthetic + real video (team listening pending)
- [Stage 3: Transcription](docs/stages/STAGE_03_transcription.md) ✅

**Status legend:** ✅ done and tested · 🔄 in progress · ⏸ waiting on something · ⬜ not started

---

## Why this order?

Two rules decide the order:

1. **Dependencies first.** You can't time a dubbed line before you can produce one, and you can't translate before you have a transcript.
2. **Riskiest unknown first.** The whole product depends on one thing nobody has verified: *does Gnani's cloned voice sound good in Tamil, Bengali and Marathi?* If not, we switch to Timbre voices, and that changes later stages. So we test the voice right after the foundation, before building anything around it.

```
Stage 0  Foundation ──► Stage 1  Voice gate (Gnani embedding + cloned TTS)  ◄── riskiest, test first
                              │
          ┌───────────────────┴──────────────┐
          ▼                                  ▼
Stage 2  Audio prep (ffmpeg + Demucs)   Stage 4  LLM layer (Gemini)
          ▼                                  │
Stage 3  Transcription (Prisma Batch)        │
          ▼                                  ▼
Stage 5  Units (cleanup + segmentation) ◄────┘
          ▼
Stage 6  Translation
          ▼
Stage 7  Timing Agent  ◄── core innovation
          ▼
Stage 8  QA check (Prisma REST + rapidfuzz)
          ▼
Stage 9  Mix + video + SRT
          ▼
Stage 10 Pipeline + CLI + report.json  ──► 30 s clip end-to-end ──► 2–3 min, all 3 languages
          ▼
Stage 11 Streamlit page
          ▼
Stage 12 Docs, README, demo, submission
```

---

## Stage 0: Foundation ✅

| | |
|---|---|
| **What** | Python environment, project skeleton, config/secrets loading, disk cache, retry rules, offline tests. |
| **Why** | Every later stage needs keys loaded safely, API results cached (5,000-credit budget), and failures handled the same way. |
| **How** | `.venv` (Python 3.13); `src/config.py` reads `.env`; `src/cache.py` stores results under `cache/<kind>/<sha256>.<ext>`; `src/retry.py` decides retry/stop per HTTP status. |
| **Files / tech** | `.gitignore`, `.env.example`, `requirements.txt`, `src/config.py`, `src/cache.py`, `src/retry.py`, `tests/test_foundation.py`; ffmpeg 9.0.2 (winget). |
| **Expected result** | Tests pass offline; `python -m src.config` reports the environment without showing secrets. |
| **Test** | `.venv\Scripts\python -m pytest -q` and `.venv\Scripts\python -m src.config` |

**Result (2026-11-06):** 13/13 tests passed. Environment check: Python 3.13.7 OK, ffmpeg/ffprobe OK (new terminals only), API keys **missing** (the team still has to create `.env`).

---

## Stage 1: Voice gate: Gnani embedding + cloned-voice TTS ⏸

| | |
|---|---|
| **What** | `src/gnani.py` functions: `create_voice_embedding(ref_audio)` and `synthesize_cloned(text, embedding)`, plus a small script to generate test sentences. |
| **Why** | Voice cloning is the product's identity, and its cross-language quality is undocumented. This is the go/no-go decision. |
| **How** | `POST /api/v1/tts/voice-clone/embeddings` (multipart `audio_file`) → cache the embedding; `POST /api/v1/tts/inference` with `model: vachana-vc-v1` + `speaker_embedding` → WAV bytes → cache; measure duration with ffprobe. |
| **Files / tech** | `src/gnani.py`, `src/audio.py` (duration helper), `scripts/voice_test.py`; requests, ffprobe. |
| **Expected result** | 3 WAV files (Tamil, Bengali, Marathi) in the team's voice + a short table of durations. |
| **Test** | The team **listens** and decides: cloned voice or Timbre fallback, per language. Re-running costs 0 credits (cache hit). |
| **Needs** | `GNANI_API_KEY` in `.env`; a 5–30 s clean voice sample. |

## Stage 2: Audio prep: extraction + separation ⬜

| | |
|---|---|
| **What** | `src/separate.py`: extract audio from the video; Demucs two-stem → `vocals.wav`, `no_vocals.wav`; `--no-music` path. |
| **Why** | Clean voice for STT; music without the Hindi voice for the final mix. |
| **How** | `ffmpeg -i video -vn audio.wav`; `demucs --two-stems=vocals`; GPU (RTX 2050) if CUDA PyTorch installs cleanly. |
| **Files / tech** | `src/separate.py`; ffmpeg, Demucs, PyTorch. |
| **Expected result** | Two WAVs for a 30 s test clip; listening confirms the voice is removed from `no_vocals.wav`. |
| **Test** | Durations match the source; listen to both stems. |
| **Risk** | Demucs install on Python 3.13 (will pin compatible torch/torchaudio). |

## Stage 3: Transcription: Prisma v2.5 Batch ⬜

| | |
|---|---|
| **What** | `gnani.transcribe_batch(wav, "hi-IN")`: create job → start → poll (≥10 s) → list files → download transcript. |
| **Why** | Hindi text **with timestamps** is the base for translation and timing. |
| **How** | Convert vocals to 16 kHz mono WAV; cache by file hash + config. |
| **Expected result** | Raw transcript JSON saved; we inspect segments, timestamps, punctuation. |
| **Test** | Run on the 30 s clip; compare the transcript with what was actually said; record findings in NOTES.md. |

## Stage 4: LLM layer: Gemini ⬜

| | |
|---|---|
| **What** | `src/llm.py`: one function `ask_json(prompt) -> dict`, model from `GEMINI_MODEL`, cached, with retry. |
| **Why** | Cleanup, translation and shortening all need an LLM; keeping it behind one function makes it swappable. |
| **Expected result / test** | A small JSON round-trip works; a second call is a cache hit. |

## Stage 5: Units: cleanup + segmentation ⬜

| | |
|---|---|
| **What** | `src/units.py`: raw segments → punctuated, sentence-sized units with `start, end, slot, gap`. |
| **Why** | Translate whole sentences, not fragments; each unit gets a time slot. |
| **Test** | Offline tests for merge/slot/gap math; real run on the 30 s transcript, shown as a table. |

## Stage 6: Translation ⬜

| | |
|---|---|
| **What** | `src/translate.py`: per-unit Gemini translation with full context, do-not-translate names, numbers as words, a character budget. |
| **Test** | Translations of the 30 s clip shown side by side with the Hindi; character counts vs budget. |

## Stage 7: Timing Agent ⬜ (core innovation)

| | |
|---|---|
| **What** | `src/timing.py`: pure decision functions (fit / sped_up / rewritten / flagged) + the loop that applies them (atempo, shorten via Gemini, re-synthesize). |
| **Why** | Keeps the dub in sync even though translations change length. |
| **Test** | Offline unit tests with fake durations for every branch; then a real timing table for the 30 s clip. |

## Stage 8: QA check ⬜

| | |
|---|---|
| **What** | `src/qa.py`: transcribe each final clip with Prisma REST (≤30 s), rapidfuzz similarity, `qa_flag` below a threshold. |
| **Test** | Scores on known-good clips, used to choose the threshold. |

## Stage 9: Mix + final video + subtitles ⬜

| | |
|---|---|
| **What** | `src/mix.py`: place clips at their start times, overlay on `no_vocals.wav`, loudnorm, mux with `-c:v copy`; write `.srt`. |
| **Test** | Watch the 30 s output; check the subtitles line up. |

## Stage 10: Pipeline + CLI + report ⬜

| | |
|---|---|
| **What** | `src/pipeline.py`, `cli.py`, `report.json`. |
| **Test** | `python cli.py --video clip30.mp4 --lang ta-IN --ref ref.wav` end-to-end; then a 2–3 min video in all 3 languages. |

## Stage 11: Streamlit page ⬜

Upload, consent checkbox, language picker, progress, side-by-side videos, unit table, metrics, downloads, "AI-dubbed" label.

## Stage 12: Docs, README, demo, submission ⬜

README (models, contributions, how to run, honest limits), architecture diagram, written explanation, demo video, LinkedIn/X post with #GnaniAI #GreatIndianAIInternshipChallenge. Deadline **Nov 10, 2026, 11:59 PM IST**.

---

## Progress log

| Date | Stage | What happened |
|---|---|---|
| 2026-11-07 | 3 | ✅ `transcribe_batch()` (create → start → poll 10 s → files → download; job id saved for resume). 1 real job on `chai_video.mp4`: **2 segments (14.5 s, 12.4 s)**, no punctuation, no word times, English transliterated. Found 3 silent retries → retries now logged; create job never re-sent except on 429. 30/30 tests. |
| 2026-11-07 | 2 | Real video `samples/chai_video.mp4` (27.6 s, 480×864) separated OK; music ~12 dB below voice; audio 0.28 s shorter than video. |
| 2026-11-06 | 2 | Built `src/separate.py` (extract → Demucs → 16 kHz STT file, `--no-music`, cached). Synthetic test (own voice + generated chords): voice SDR 0.4 → **17.1 dB**, music **16.7 dB**; Demucs 23.5 s for 21.6 s; cache 0.01 s. 21/21 tests. Waiting for a real 30 s Hindi video to listen. |
| 2026-11-06 | 2 (prep) | GPU PyTorch (2.6 + CUDA 12.4, 2.5 GB) download **failed** (network drop). pip then installed **Demucs 4.1.0 + CPU PyTorch 2.15**. Demucs 4.1 no longer needs torchaudio. CPU check: 22 s clip separated in ~17 s (≈0.8× real time; 42 s total incl. first-time model download). **Team decision: CPU** (GPU optional later). |
| 2026-11-06 | 1 | ✅ **GO.** Team listened: cloned voice "okay" for Tamil, Bengali, Marathi → use `vachana-vc-v1` for all three; Timbre stays as fallback. |
| 2026-11-06 | 1 | Built `src/audio.py`, `src/gnani.py` (embedding + cloned TTS), `scripts/voice_test.py`. 18/18 offline tests. Real run: 4 Gnani calls → embedding [1,768] + Tamil/Bengali/Marathi clips (44.1 kHz mono WAV). Re-run: 0 calls (cache). **Waiting for the team to listen.** |
| 2026-11-06 | 0 | Committed + pushed Stage 0 (`6c76d49`). |
| 2026-11-06 | 1 (prep) | Gnani key added to `.env`; verified with free `GET /stt/v3/batch/jobs` → HTTP 200, empty job list. Still need: voice sample. |
| 2026-11-06 | 0 | Created `.venv` (Python 3.13.7; 3.11 not installed, 3.14 too new for Demucs). Installed ffmpeg 9.0.2 via winget. Wrote config, cache, retry modules. 13/13 offline tests pass. Waiting for `.env` keys + voice sample to start Stage 1. |

## How to run what exists so far

```powershell
# one-time: create .env from the template and fill in your keys
copy .env.example .env

# run offline tests
.venv\Scripts\python -m pytest -q

# check the environment (never prints key values)
.venv\Scripts\python -m src.config
```
