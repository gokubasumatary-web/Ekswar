# PROJECT_CONTEXT.md: Ekswar

> **EKSWAR: One voice. Every Indian language.**
>
> This is the single source of truth for the project. Anyone (human or AI) should be able to read only this file and understand what Ekswar is, how it works, what has been verified, and what is still open.
>
> **Last updated:** 2026-11-06 (Day 1, before any code was written)
> **Original brief:** [PROJECT.md](PROJECT.md) (kept unchanged for reference)

---

## How to read this file: confidence labels

Every important claim is tagged with where it comes from. Do not treat a lower-confidence tag as fact.

| Tag | Meaning |
|---|---|
| **[DOCS]** | Verified against the official Gnani docs (docs.gnani.ai) on 2026-11-06. Still re-check if behaviour looks wrong. |
| **[BRIEF]** | Stated in our original project brief. A decision or requirement, not necessarily a verified fact. |
| **[TEST]** | Unknown until we try it with real API calls. Must be tested. |
| **[SUGGESTION]** | A recommendation from the coding assistant. Not agreed yet unless marked *(agreed)*. |
| **[ASSUMPTION]** | A reasonable guess that has not been verified. |

When something gets tested or decided, update its tag and record the result in [Section 27](#27-current-implementation-status) (and in `NOTES.md` if the real API differed from the docs).

---

## 1. Project overview

Ekswar takes a short **Hindi video of one person speaking** and produces **the same video dubbed into Tamil, Bengali or Marathi**, where:

- the new speech is in **the creator's own (cloned) voice**, not a stock voice,
- each dubbed line is **timed to fit the moment it was originally spoken**,
- the **background music is preserved** under the new speech,
- it also produces **subtitles (.srt)** and a **metrics report (report.json)**.

It is an entry for the **Great Indian AI Internship Challenge by Gnani AI**, built by a team of 2 students between **Nov 6 and Nov 10, 2026**. **[BRIEF]**

**The core idea in one sentence:** translation changes how *long* a sentence takes to say, so Ekswar has a **timing agent** that measures every dubbed line and, if it runs too long, speeds it up slightly or asks an LLM to rephrase it shorter and tries again, until it fits.

---

## 2. Problem statement

India has hundreds of millions of viewers who prefer content in their own language. A creator who speaks Hindi reaches only part of that audience. Today the options are:

| Option | Problem |
|---|---|
| Subtitles | Many viewers don't read subtitles comfortably, especially on mobile and for long content. |
| Human dubbing | Expensive and slow, and it uses a *different person's* voice, so the creator's identity is lost. |
| Generic AI dubbing with stock voices | Sounds like a robot or a stranger, and lines often drift out of sync with the video because translations are longer or shorter than the original. |

**The specific problem Ekswar tackles:** produce a dub that (a) still sounds like the creator, and (b) stays in sync with the original video, even though Tamil, Bengali and Marathi sentences rarely take the same time to say as the Hindi ones.

**Why timing is the hard part:** if a Hindi line takes 2.0 s and its Tamil translation takes 3.1 s, you either cut it off (bad), let it overlap the next line (bad), or let the whole dub drift further out of sync with every line (bad). Ekswar's timing agent is the answer to this.

---

## 3. Project objectives

1. Build a **working** end-to-end pipeline: Hindi video in, dubbed video + subtitles + report out. **[BRIEF]**
2. Use Gnani models **meaningfully**: Prisma (speech-to-text) and Voice Cloning are core to the pipeline, not decorations. **[BRIEF]**
3. Demonstrate the **timing agent** clearly. This is the main thing to show in the demo. **[BRIEF]**
4. Be **honest about limits**: no lip-sync claims, no "perfect accuracy" claims. **[BRIEF]**
5. Stay within the **5,000-credit budget** by caching every API result. **[BRIEF]**
6. Submit by **Nov 10, 2026, 11:59 PM IST** with all required deliverables. **[BRIEF]**

---

## 4. Target users

- **Primary:** individual Indian content creators (YouTube, Instagram Reels, educators, explainers) who speak Hindi and want to reach Tamil, Bengali and Marathi audiences without losing their own voice.
- **Secondary (future):** small media teams, ed-tech companies, NGOs producing awareness videos.
- **For this competition:** the "user" in the demo is a team member dubbing **their own voice** (consent rule, see [Section 19](#19-security-and-privacy-requirements)).

---

## 5. Core features

| # | Feature | Status in scope |
|---|---|---|
| F1 | Hindi speech-to-text with timestamps (Gnani Prisma Batch) | IN |
| F2 | Background music separation and preservation (Demucs) | IN (skippable with `--no-music`) |
| F3 | Transcript cleanup into sentence-sized "units" (Gemini) | IN |
| F4 | Translation into Tamil / Bengali / Marathi within a length budget (Gemini) | IN |
| F5 | Speech in the creator's cloned voice (Gnani Voice Cloning) | IN |
| F6 | Backup stock voice if cloning sounds wrong for a language (Gnani Timbre v3.0) | IN (fallback only) |
| F7 | **Timing agent**: fit, speed up, rewrite, or flag each line | IN (**core demo**) |
| F8 | Automatic quality check of each dubbed line (Gnani Prisma REST) | IN |
| F9 | Mixing dubbed speech over the original music, then muxing onto the original video | IN |
| F10 | Subtitles (.srt) in the target language | IN |
| F11 | Metrics report (report.json) | IN |
| F12 | Disk cache of every API result | IN |
| F13 | CLI | IN (built first) |
| F14 | Streamlit web page | IN (built after the CLI works) |
| F15 | Edit one line and re-render only that line | STRETCH only |

---

## 6. Input and output specifications

### Inputs **[BRIEF]**

| Input | Requirements |
|---|---|
| Source video | Hindi speech, **one speaker**, **≤ 3 minutes**. Typical formats: mp4. |
| Voice reference sample | **5–30 seconds of clean speech** by the same person (WAV or MP3 per the brief). Used once to create the voice embedding. Docs recommend 5–30 s; they do not list accepted formats. **[DOCS]** |
| Target language | One of `ta-IN` (Tamil), `bn-IN` (Bengali), `mr-IN` (Marathi). |
| Consent (Streamlit only) | Checkbox: "this is my voice or I have permission". Required. |
| Optional flags | `--no-music` (skip Demucs when there is no background music). |

Planned CLI shape **[BRIEF]**:
```bash
python cli.py --video in.mp4 --lang ta-IN --ref ref_long.wav
```

### Outputs **[BRIEF]**

| Output | Description |
|---|---|
| Dubbed MP4 | Original video stream (copied, not re-encoded) + new audio track (dubbed speech over the original music). Labelled "AI-dubbed" in the UI. |
| `.srt` subtitles | Translated text, timed to each unit's start/end. |
| `report.json` | Total units; counts of `fit` / `sped_up` / `rewritten` / `flagged`; number of `qa_flag`s; average similarity; processing time; Gnani credits used **if visible** (there is no documented credits API, see [Section 24](#24-api-limitations-and-things-requiring-testing)). |
| Intermediate files | Raw STT JSON, unit list, per-unit clips, all under `cache/` and `outputs/`, useful for debugging and the demo. |

---

## 7. Complete project workflow

This is the journey of one video. Each step lists **what goes in → what happens → what comes out → who does it**.

```
 video.mp4
    │
    ▼
[1] Extract audio ─────────────── ffmpeg ──────────► audio.wav
    │
    ▼
[2] Separate voice / music ────── Demucs (local) ──► vocals.wav + no_vocals.wav
    │                                                (skipped with --no-music)
    ▼
[3] Transcribe Hindi ──────────── Gnani Prisma v2.5 Batch (cloud)
    │   vocals → 16 kHz mono WAV ─► upload ─► start ─► poll ─► download
    │                                                ► raw transcript JSON (segments + timestamps)
    ▼
[4] Clean up + build units ────── Gemini (cloud) + our code
    │                                                ► units: text, start, end, slot, gap
    ▼
[5] Voice embedding ───────────── Gnani Voice Clone Embeddings (cloud, once, cached)
    │                                                ► speaker_embedding
    ▼
[6] Translate each unit ───────── Gemini (cloud) ──► translated text within a char budget
    │
    ▼
[7] Synthesize each unit ──────── Gnani Voice Cloning TTS (cloud) ──► clip.wav + duration
    │
    ▼
[8] TIMING AGENT (per unit) ───── our code + ffmpeg atempo + Gemini (shorten) + Gnani TTS (re-synth)
    │                                                ► final clip + status (fit/sped_up/rewritten/flagged)
    ▼
[9] Quality check ─────────────── Gnani Prisma REST (cloud) + rapidfuzz (local)
    │                                                ► similarity score + qa_flag
    ▼
[10] Mix audio ────────────────── ffmpeg ──────────► dubbed speech placed at each start time,
    │                                                  overlaid on no_vocals.wav, loudness-normalised
    ▼
[11] Final video ──────────────── ffmpeg ──────────► dubbed.mp4 (video stream copied)
    │
    ▼
[12] Subtitles + report ───────── our code ────────► dubbed.srt + report.json
```

### Step-by-step detail

**[1] Audio extraction.** *In:* video file. *Does:* ffmpeg pulls the audio track out as WAV. *Out:* `audio.wav`. *Why:* every later step works on audio, not video.

**[2] Voice/music separation.** *In:* `audio.wav`. *Does:* Demucs "two-stem" mode splits audio into the human voice and everything else. *Out:* `vocals.wav` (voice only), `no_vocals.wav` (music/ambience). *Why:* (a) STT is more accurate on clean voice; (b) we need the music *without* the Hindi voice so we can put the new voice on top. With `--no-music`, Demucs is skipped and the "music" track is just silence. **[BRIEF]**

**[3] Speech-to-text (Hindi).** *In:* `vocals.wav`. *Does:* convert to 16 kHz mono WAV (`ffmpeg -ar 16000 -ac 1`; 3 min ≈ 5.8 MB, under the 10 MB upload limit), create a Prisma v2.5 batch job, start it, poll every ≥10 s until a terminal state, list files, download the transcript from the pre-signed URL. *Out:* raw transcript JSON with `segments` (`start_time`, `end_time`, `text`) and `full_transcript`. Save it as-is. *Why batch, not REST:* REST only accepts ≤30 s of audio **[DOCS]**; our video is up to 3 min.

**[4] Cleanup and unit building.** *In:* raw segments. *Does:* Prisma batch output is lowercase/unpunctuated with no number formatting, so Gemini adds punctuation and we merge tiny fragments into sentence-sized **units**. Each unit gets:
- `start`, `end`: from the segment timestamps,
- `slot = end - start`: how long the original line took,
- `gap`: silence between this unit's end and the next unit's start.

*Out:* `units.json`. *Why:* translating fragments gives bad translations; translating whole sentences gives good ones. Timing needs sentence-level slots. **[BRIEF]**

**[5] Voice embedding.** *In:* reference sample (5–30 s). *Does:* one call to the embeddings endpoint. *Out:* `speaker_embedding` = `{embedding (base64 string), shape (e.g. [1,768]), dtype (e.g. "torch.bfloat16")}`. Cached forever for that sample. **[DOCS]**

**[6] Translation.** *In:* one unit + the full transcript as context + do-not-translate names list + a character budget derived from the slot. *Does:* one Gemini call per unit. Rules: keep listed names unchanged, write numbers as words in the target language, return JSON, stay under the character budget. *Out:* translated text per unit. **[BRIEF]**

**[7] Synthesis.** *In:* translated text + speaker embedding. *Does:* call Gnani cloned-voice TTS (`vachana-vc-v1`), receive binary WAV, measure duration. *Out:* `clip.wav` + `duration`. **[DOCS]** for the API; **[TEST]** for whether the cloned voice pronounces Tamil/Bengali/Marathi well.

**[8] Timing agent.** See [Section 14](#14-detailed-timing-agent-logic). *Out:* a final clip per unit + a status.

**[9] Quality check.** *In:* final clip + intended translated text. *Does:* transcribe the clip with Prisma REST in the target language and compute character-level similarity (rapidfuzz) between what STT heard and what we intended. Below a threshold, set `qa_flag`. *Out:* similarity score + flag. This is a **warning light, not a verdict**: STT spelling/formatting differences lower the score even when the audio is fine. **[BRIEF]**

**[10] Mixing.** *In:* final clips with start times + `no_vocals.wav`. *Does:* place each clip at its `start` on a silent track the length of the video, overlay it on the music, normalize loudness. *Out:* `dubbed_audio.wav`.

**[11] Final video.** *In:* original video + `dubbed_audio.wav`. *Does:* ffmpeg muxes the new audio onto the original video, copying the video stream (no re-encode: fast and lossless). *Out:* `dubbed.mp4`.

**[12] Subtitles + report.** *Out:* `.srt` from translated units; `report.json` with metrics.

---

## 8. Technical architecture

Ekswar is a **single Python application** that runs on the developer's laptop. There is no separate server, no database, and no user accounts. **[BRIEF]**

```
┌──────────────────────────────────────────────────────────────┐
│  INTERFACE LAYER                                             │
│   cli.py (first)               app.py (Streamlit, second)    │
│   - parse args                 - upload, consent, progress   │
│   - print progress             - side-by-side video, table   │
└───────────────┬──────────────────────────────┬───────────────┘
                │   both call the same function │
                ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│  ORCHESTRATION LAYER: src/pipeline.py                        │
│   runs steps 1–12 in order, collects statuses, writes report │
└───┬───────────────┬────────────────┬────────────────┬────────┘
    ▼               ▼                ▼                ▼
┌─────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐
│ AUDIO / │  │ LOGIC        │  │ AI / LLM      │  │ GNANI API    │
│ VIDEO   │  │ (pure code)  │  │ LAYER         │  │ LAYER        │
│ separate│  │ units.py     │  │ llm.py        │  │ gnani.py     │
│ mix.py  │  │ timing.py    │  │ translate.py  │  │ - batch STT  │
│ (ffmpeg,│  │ qa.py (score)│  │ (Gemini)      │  │ - REST STT   │
│ Demucs) │  │              │  │               │  │ - embedding  │
└─────────┘  └──────────────┘  └───────┬───────┘  │ - TTS (VC +  │
   LOCAL         LOCAL                 │          │   Timbre)    │
                                       │          └──────┬───────┘
                                       ▼                 ▼
                               ┌─────────────────────────────────┐
                               │  CACHE LAYER: cache/ on disk    │
                               │  key = hash(input) → result     │
                               └─────────────────────────────────┘
                                   CLOUD calls happen only on a cache miss
```

### Local vs cloud processing

| Runs locally (free, no credits) | Runs in the cloud (costs credits / quota) |
|---|---|
| ffmpeg (extract, convert, atempo, mix, mux) | Gnani Prisma Batch STT |
| Demucs (separation; can use the RTX 2050 GPU if CUDA PyTorch is installed) | Gnani Prisma REST STT (QA) |
| Unit building, timing decisions, similarity scoring | Gnani Voice Clone embedding |
| SRT and report writing | Gnani TTS (cloned voice / Timbre) |
| Cache lookups | Gemini (free tier, rate-limited) |

---

## 9. Frontend responsibilities

The "frontend" is **Streamlit** (`app.py`), a Python library that turns a script into a web page. It is built **only after the CLI works**. **[BRIEF]**

Responsibilities:
- Upload the video; upload the 5–30 s voice sample.
- Pick Tamil / Bengali / Marathi.
- **Consent checkbox** ("this is my voice or I have permission"), **required** before Run is enabled.
- Run button + progress display (which step, which unit).
- Show the original and dubbed videos side by side.
- Show the unit table: original text, translation, timing status, QA score.
- Show the metrics from `report.json`.
- Download buttons for the MP4 and SRT.
- Label every output **"AI-dubbed"**.
- *Stretch only:* edit a line and re-render just that line.

The frontend contains **no pipeline logic**. It calls the same `pipeline.run(...)` function the CLI calls. **[SUGGESTION]**

---

## 10. Backend responsibilities

There is no web server. "Backend" here means the **Python modules in `src/`** that do the work:

- Orchestrate the 12 steps (`pipeline.py`).
- Talk to Gnani (`gnani.py`) and Gemini (`llm.py`), with caching, retries and backoff.
- Do audio/video work via ffmpeg and Demucs (`separate.py`, `mix.py`).
- Make timing decisions (`timing.py`: pure functions, unit-tested without the network).
- Score quality (`qa.py`).
- Write outputs (`.mp4`, `.srt`, `report.json`).
- Never crash the whole run because one unit failed: mark it and continue. **[BRIEF]**

---

## 11. AI models and their individual roles

| Model / tool | Provider | Role in Ekswar | Why we need it | Required? |
|---|---|---|---|---|
| **Prisma v2.5** (Batch) | Gnani | Transcribe the Hindi source audio with timestamps | Timestamps tell us *when* each line was said, which is the basis for all timing. | Core |
| **Prisma v2.5** (REST) | Gnani | Transcribe each dubbed clip in the target language for QA | Automatic "does this sound like what we meant?" check | Core |
| **Voice Cloning `vachana-vc-v1`** | Gnani | Speak every translated line in the creator's voice | This is the product's identity: *your* voice in every language. | Core |
| **Timbre v3.0 `timbre-v3.0`** | Gnani | Stock-voice fallback, per language | If cloning sounds wrong in a language, we still produce a dub. It accepts an explicit `language` field; voice cloning does not. | Fallback |
| **Gemini** (free tier, model from `GEMINI_MODEL`) | Google | (a) punctuation + unit merging, (b) translation, (c) shortening during timing | Gnani's own LLM (Evon) is not available on the API. **[BRIEF]** | Core (swappable) |
| **Demucs** | Open-source (Meta) | Separate vocals from music | Keep the music and remove only the Hindi voice | Core (skippable) |
| **IndicF5** | Open-source | Only if Gnani cloning fails for a language | Last-resort option; **not planned** | Optional |

**Gnani Evon must NOT be used**: it is not on the API. **[BRIEF]**

### How STT and TTS work in our pipeline (plain English)

- **STT (speech-to-text)** listens to audio and writes down the words. We use it twice: once to *understand the source* (Hindi, with timestamps), and once to *check our output* (each dubbed clip, in the target language).
- **TTS (text-to-speech)** reads text aloud. Normal TTS uses a stock voice (Timbre). **Voice cloning** is TTS that copies a specific person's voice: first you turn a short sample of their speech into an **embedding** (a list of numbers that captures what their voice sounds like), then you send that embedding with every piece of text you want spoken.

---

## 12. Gnani API integrations and endpoints

**Base URL:** `https://api.vachana.ai` **[DOCS]**
**Auth header on every request:** `X-API-Key-ID: <GNANI_API_KEY>` **[DOCS]**
**Docs index:** https://docs.gnani.ai/llms.txt

### 12.1 Batch STT: source transcription **[DOCS]**

| Step | Method + path | Notes |
|---|---|---|
| Create job | `POST /stt/v3/batch/jobs` | multipart: `config` (JSON part, `type=application/json`) + `files`. Returns `job_id`, status `CREATED`. **Does not start the job.** |
| Start job | `POST /stt/v3/batch/jobs/{job_id}/start` | Returns status `STARTING`. |
| Poll | `GET /stt/v3/batch/jobs/{job_id}` | Poll **no more often than every 10 s**. No transcript text here. |
| List files | `GET /stt/v3/batch/jobs/{job_id}/files?status=COMPLETED` | Each file has `transcript_url` (pre-signed S3 URL, **expires in 1 h**; re-call this endpoint to refresh). |
| Download | `GET <transcript_url>` | **No API key** needed (pre-signed). |
| Cancel | `POST /stt/v3/batch/jobs/{job_id}/cancel` | Not needed normally. |

Config we plan to send:
```json
{"model": "prisma-v2.5", "language_code": "hi-IN", "mode": "transcribe",
 "with_diarization": false, "is_multi_channel": false}
```
> ⚠️ **Differs from the brief:** the brief says `"gnani-prisma-v2.5"`. The docs' examples (marked live-verified) use **`prisma-v2.5`** (case-insensitive). We will use `prisma-v2.5` and record this in `NOTES.md`. **[DOCS]**

Optional v2.5 fields: `with_denoise` (adds processing time), `bias_list` (≤100 single words, letters only), `bias_score` (0.0/0.5/1.0/1.5/2.0). Sending v3.0-only fields with v2.5 → `400 INVALID_CONFIG`. **[DOCS]**

Job states: in progress = `CREATED, STARTING, QUEUED, IN_PROGRESS, CANCELLING`; **terminal = `COMPLETED, PARTIAL_FAILURE, FAILED, START_FAILED, CANCELLED`**. **[DOCS]** (The brief listed only three terminal states.)

Limits: 10 MB per file on direct upload; 0.1 s to 4 h duration; ≤5,000 segments; formats wav, mp3, mp4, flac, ogg, opus, m4a, aac, webm, amr. **[DOCS]**

Transcript document (documented example for v2.5, abbreviated):
```json
{
  "language_code": "en-IN", "duration_seconds": 6.01, "model": "prisma-v2.5", "mode": "transcribe",
  "segments": [
    {"segment_id": 0, "start_time": 0.0,  "end_time": 0.71, "text": "hello", "speaker_id": 1,
     "confidence": null, "language_detected": null, "sentiment": null, "emotion": null},
    {"segment_id": 0, "start_time": 0.71, "end_time": 2.36, "text": "how can i help you today", "speaker_id": 2, "...": "..."}
  ],
  "full_transcript": "hello how can i help you today ..."
}
```
- `segment_id` is **0 for every segment** in the docs' example → **do not rely on it**; use list order. **[DOCS]**
- Text is lowercase with no punctuation in the example. Punctuation behaviour is **not documented**. Inverse text normalization (number formatting) is **not supported on Batch**. **[DOCS]**
- Code must still handle a transcript that has only `full_transcript` and no segments (the brief saw such a sample elsewhere). **[BRIEF] [TEST]**

### 12.2 REST STT: QA check per dubbed clip **[DOCS]**

`POST /stt/v3`, `multipart/form-data`:

| Field | Required | Notes |
|---|---|---|
| `audio_file` | yes | wav, mp3, ogg, flac, aac, m4a (detected by extension) |
| `language_code` | yes | `ta-IN`, `bn-IN`, `mr-IN`, … (one code for v2.5) |
| `model` | no | omit → Prisma v2.5 (default) |
| `format` | no | default `verbatim` (numbers spelled out as words, which suits our QA comparison) |

Response (key fields): `success`, `request_id`, `transcript` (string; empty = no speech, not an error), `model`, `processing_time`, optionally `truncated`.

> ⚠️ **Differs from the brief:** the brief says "clips up to 60 s". The docs say **max 30 seconds** per request (`400 MAX_AUDIO_DURATION_EXCEEDED`). Each unit is one sentence, so this should be fine, but the code must check and skip QA for any clip > 30 s. **[DOCS]**

### 12.3 Voice clone embedding **[DOCS]**

`POST /api/v1/tts/voice-clone/embeddings`, multipart, field `audio_file` (5–30 s clean speech recommended).

Documented response:
```json
{"success": true, "message": "Voice embeddings generated successfully",
 "data": {"voice_clone_embedding": {"embedding": "<base64 string>", "shape": [1, 768], "dtype": "torch.bfloat16"}}}
```
- The docs page shows **only the wrapped form**. The brief mentions an unwrapped `{embedding, shape, dtype}` form too. Code handles **both**. **[DOCS] + [BRIEF]**
- Accepted formats, max size and error codes are **not documented**. **[TEST]**
- "Generate once per voice and cache it." **[DOCS]**

### 12.4 Cloned-voice TTS **[DOCS]**

`POST /api/v1/tts/inference`, `Content-Type: application/json`:
```json
{
  "text": "...",
  "model": "vachana-vc-v1",
  "audio_config": {"sample_rate": 44100, "encoding": "linear_pcm", "container": "wav"},
  "speaker_embedding": {"embedding": "<base64>", "shape": [1, 768], "dtype": "torch.bfloat16"}
}
```
- Response: **raw binary audio** (`audio/wav` for the wav container), no JSON wrapper.
- **No `language` field.** The page's only example is Hindi. Cross-language quality is **undocumented**. **[TEST]**
- `audio_config.sample_rate`: schema says 8000–44100 for VC (the TTS page allows up to 48000). Use **44100**.
- Max text length: **not documented**; too-long text returns **500**. **[DOCS]**

### 12.5 Timbre v3.0 TTS (fallback) **[DOCS]**

Same endpoint `POST /api/v1/tts/inference`:
```json
{"text": "...", "model": "timbre-v3.0", "voice": "Shivani", "language": "ta-IN", "speed": 1.0,
 "audio_config": {"sample_rate": 44100, "encoding": "linear_pcm", "container": "wav"}}
```
- v3.0 voices (13): Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika, Harshad. **Each speaks all 10 languages.**
- `language`: `auto`, `hi-IN`, `en-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `bn-IN`, `gu-IN`, `hi-en`.
- `speed`: 0.85–1.15 (default 1.0). This could also help the timing agent when we're on the Timbre fallback. **[SUGGESTION]**
- Note: the input-formatting page lists short codes (`ta`, `mr`, …) while the inference page lists `ta-IN` style. Use the inference page's form; verify on first call. **[TEST]**

### 12.6 Error formats (shared) **[DOCS]**

| HTTP | Body shape | Meaning | Our handling |
|---|---|---|---|
| 400 / 422 | flat `{success:false, message}` or `{error:{type,message}}` / `{detail:[...]}` | Bad request | **Don't retry.** Fix the input; mark the unit failed. |
| 401 | `{detail:{error_code: MISSING_API_KEY / INVALID_API_KEY}}` | Key problem | **Stop the run** with a clear message. |
| 402 | `{detail:{...}}` | **Insufficient credit** | **Stop the run.** Retrying cannot help. |
| 403 | `SCOPE_NOT_ALLOWED` | Key lacks access to this service | Stop; check the key's scopes in the dashboard. |
| 429 | `RATE_LIMITED`, **no `Retry-After` header** | Too many requests; some accounts allow **one active request at a time** | Retry with exponential backoff. Send requests **one at a time**. |
| 500 | flat | Unexpected error, **including text too long** or a bad embedding | Retry **at most once**, then mark the unit failed (retrying a too-long text forever would waste time). **[SUGGESTION]** |
| 503 / 504 | varies | Temporarily unavailable / upstream timeout | Retry with backoff. |

### 12.7 TTS input formatting **[DOCS]**

- Gnani runs **automatic text normalization** (numbers, currency, dates) on synthesis. Language detection for this is driven by **script** when `language` is `auto`: **Devanagari → Hindi** (you must pass `mr` explicitly for Marathi).
- English, Hindi, Marathi and Tamil have the deepest normalization coverage; Bengali is "fully supported, still being refined".
- Max input length and sentence-splitting rules: **not documented**.
- The brief's rule "write numbers as words in the target language" remains our policy. It avoids depending on normalization, especially for cloned voice where we **cannot** pass a language. **[BRIEF]**

---

## 13. Other third-party tools and libraries

| Tool | What it is | What we use it for | Status |
|---|---|---|---|
| **ffmpeg** | Command-line audio/video Swiss-army knife | Extract audio, convert to 16 kHz mono, measure duration, `atempo` speed-up, pad silence, overlay/mix, loudness normalize (`loudnorm`), mux audio onto video with `-c:v copy` | **Not installed yet** on the dev machine |
| **Demucs** | Open-source music source separation model | `--two-stems=vocals` → `vocals.wav` + `no_vocals.wav` | Not installed. Needs PyTorch. |
| **PyTorch** | ML framework (Demucs dependency) | Runs Demucs; the RTX 2050 GPU can speed it up with the CUDA build | Not installed |
| **Gemini SDK** | Google's LLM API client | Cleanup, translation, shortening (behind `llm.py`) | Model name from `GEMINI_MODEL`, chosen in Google AI Studio |
| **requests** (or httpx) | HTTP client | Gnani API calls | [SUGGESTION] |
| **python-dotenv** | Loads `.env` | API keys from the environment | [SUGGESTION] |
| **rapidfuzz** | Fast string similarity | QA: intended text vs STT transcript | [BRIEF] |
| **Streamlit** | Python → web UI | `app.py` | [BRIEF] |
| **pytest** | Test runner | `tests/` for timing logic | [SUGGESTION] |

> **Environment (decided 2026-11-06):** the project uses a **Python 3.13** virtual environment (`.venv`). 3.11 is not installed on the dev machine, and 3.14 is too new for Demucs's dependencies. Demucs + PyTorch on 3.13 is still **[TEST]** (Stage 2); we may need to pin compatible torch/torchaudio versions.

---

## 14. Detailed Timing Agent logic

### The problem it solves

The translated line must fit the time the original line occupied, or the dub drifts out of sync. Different languages need different numbers of syllables to say the same thing, so lengths almost never match.

### Inputs per unit

- `slot = end - start`: how long the original Hindi line took.
- `gap`: silence after this unit before the next one starts (for the last unit, time until the end of the video). **[ASSUMPTION]** for the last-unit rule.
- `duration`: measured length of the synthesized clip.

### The budget

```
budget = slot + 0.5 * gap
```
Plain English: the dubbed line may use its own slot **plus up to half of the pause after it**. That still leaves some breathing room before the next line, so lines never overlap.

### Decision ladder **[BRIEF]**

```
duration <= budget                → pad with silence                     → status "fit"
duration <= budget * 1.15         → speed up with ffmpeg atempo (≤1.15×) → status "sped_up"
otherwise:
    repeat up to 3 times:
        ask Gemini to shorten (same meaning, target length ≈ len(text) * budget / duration)
        re-synthesize (Gnani TTS), re-measure
        if it now fits (directly, or with atempo ≤ 1.15) → status "rewritten"
    still too long:
        if duration <= budget * 1.25 → atempo up to 1.25×   → status "sped_up"
        else keep the SHORTEST version produced             → status "flagged"
Never cut speech mid-word.
```

```
            ┌───────────────┐
            │ synthesize    │
            │ measure dur   │
            └──────┬────────┘
                   ▼
        dur ≤ budget? ──yes──► FIT (pad)
                   │no
                   ▼
   dur ≤ budget×1.15? ──yes──► SPED_UP (atempo)
                   │no
                   ▼
  ┌──► shorten via Gemini ─► re-synth ─► fits? ──yes──► REWRITTEN
  │                                        │no
  └──────── tries < 3 ◄────────────────────┘
                   │ tries exhausted
                   ▼
   dur ≤ budget×1.25? ──yes──► SPED_UP (atempo ≤1.25)
                   │no
                   ▼
            FLAGGED (keep shortest)
```

### Open details to settle while building **[TEST]/[SUGGESTION]**

- After a rewrite, if the new clip fits **only with** a ≤1.15 speed-up, is the status `rewritten` or `sped_up`? Suggestion: `rewritten` (record the tempo used too).
- Thresholds (1.15, 1.25, 0.5×gap, 3 tries) are **starting values, to be tuned by ear**. **[BRIEF]**
- **Cost of the ladder:** each rewrite = 1 Gemini call + 1 Gnani TTS call. Worst case per unit: 1 + 3 = 4 TTS calls. Caching makes re-runs free.
- **Design rule:** the *decisions* are pure functions (numbers in, decision out) in `timing.py`, so they can be unit-tested without any API. The *actions* (call Gemini, call TTS, run ffmpeg) are passed in from outside. **[BRIEF]**

---

## 15. Data flow between components

| From → To | Data | Format |
|---|---|---|
| video → `separate.py` | audio | WAV |
| `separate.py` → `gnani.py` (batch) | 16 kHz mono vocals | WAV ≤10 MB |
| `gnani.py` → `units.py` | raw transcript | JSON (`segments[]`, `full_transcript`) |
| `units.py` ↔ `llm.py` | segments → punctuated, merged units | JSON |
| `units.py` → `translate.py` | units (`id, text, start, end, slot, gap`) | Python list / `units.json` |
| `translate.py` ↔ `llm.py` | unit + context + budget → translated text | JSON |
| ref sample → `gnani.py` (embedding) | speaker embedding | `{embedding, shape, dtype}` |
| `translate.py` → `gnani.py` (TTS) | text + embedding → audio | JSON → binary WAV |
| `timing.py` ↔ ffmpeg / `llm.py` / `gnani.py` | durations, shorten requests, re-synth | numbers, text, WAV |
| `timing.py` → `qa.py` | final clip + intended text | WAV + string |
| `qa.py` ↔ `gnani.py` (REST STT) | clip → transcript → similarity | WAV → JSON → float |
| all units → `mix.py` | clips + start times + `no_vocals.wav` | WAV |
| `mix.py` → output | dubbed MP4, SRT | files |
| `pipeline.py` → output | `report.json` | JSON |

---

## 16. Proposed folder structure and file responsibilities

The brief shows an `ekswar/` root; **the repository root is `D:\Ekswar` itself**, so these files live directly in it. **[SUGGESTION]**

```
D:\Ekswar\
  PROJECT.md          # original brief (unchanged)
  PROJECT_CONTEXT.md  # this file: source of truth
  .env.example        # GNANI_API_KEY=  GEMINI_API_KEY=  GEMINI_MODEL=
  .env                # real keys. NEVER committed.
  .gitignore          # .env, cache/, outputs/, *.wav, *.mp4
  README.md           # models used + each member's contribution + how to run + honest limits
  NOTES.md            # every place the real API differed from the docs
  requirements.txt
  cli.py              # entry point: python cli.py --video in.mp4 --lang ta-IN --ref ref.wav
  app.py              # Streamlit UI (after CLI works)
  src/
    gnani.py          # all Gnani calls: batch STT, REST STT, embedding, VC TTS, Timbre TTS; retries; cache
    llm.py            # ONE function wrapping Gemini (swappable); model from GEMINI_MODEL
    separate.py       # ffmpeg extract + Demucs separation (+ --no-music path)
    units.py          # raw segments → punctuated, merged units with start/end/slot/gap
    translate.py      # per-unit translation prompts, char budget, do-not-translate list
    timing.py         # timing agent: pure decision functions + the loop that applies them
    qa.py             # REST STT on final clips + rapidfuzz similarity + qa_flag
    mix.py            # place clips, overlay music, loudnorm, mux, write SRT
    pipeline.py       # orchestrates steps 1–12, writes report.json
  tests/
    test_timing.py    # timing logic with fake durations, no network
  cache/              # API results keyed by input hash (git-ignored)
  outputs/            # final MP4/SRT/report per run (git-ignored)
```

---

## 17. Caching strategy

**Why:** we only have **5,000 Gnani credits** **[BRIEF]** and a rate-limited free Gemini tier. Re-running the pipeline while debugging must not re-spend them.

**How [BRIEF + SUGGESTION]:**
- Before any API call, compute a **key = SHA-256 hash of everything that affects the result** (e.g. for TTS: model + text + embedding hash + audio_config; for STT: file bytes hash + config; for Gemini: model + full prompt).
- Look in `cache/<kind>/<key>.<ext>`. If present → return it, **no API call**.
- If absent → call the API, and **only on success** write the result to the cache.
- Cached kinds: embedding (`.json`), batch transcript (`.json`), REST STT result (`.json`), each translation / cleanup / shortening (`.json`), each synthesized clip (`.wav`).
- Never cache errors.
- Write atomically (temp file, then rename) so a crash never leaves a half-written cache file. **[SUGGESTION]**
- Count cache hits vs real calls per run → useful for `report.json` and for tracking credits. **[SUGGESTION]**

---

## 18. Error handling and fallback mechanisms

| Situation | Handling |
|---|---|
| 429 / 503 / 504 | Exponential backoff (e.g. 2 s, 4 s, 8 s, …, capped), limited attempts. **[BRIEF]** |
| 500 | Retry once, then fail the unit (might be "text too long"). **[SUGGESTION]** |
| 400 / 422 | No retry. Log the message, fail the unit. |
| 401 / 403 / 402 | **Abort the run** with a clear message (key, scope, or no credits). |
| One unit fails (TTS, translation) | Mark the unit `failed`, keep going; it is left silent in the mix (subtitle still written) and counted in the report. **[BRIEF]** Leaving it silent is a [SUGGESTION]. |
| Batch job ends `FAILED` / `START_FAILED` / `PARTIAL_FAILURE` | Abort (no transcript = nothing to dub). Show the `error_message` from the files endpoint. |
| `transcript_url` expired | Call the files endpoint again for a fresh URL. **[DOCS]** |
| Transcript has no segments | Fall back to `full_transcript` (timing quality degrades; warn loudly). **[TEST]** |
| QA clip > 30 s | Skip QA for that unit, mark "not checked". **[DOCS]** limit |
| Cloned voice bad in a language | Switch that language to **Timbre v3.0** (decided after the Nov 6 voice test). **[BRIEF]** |
| Gnani cloning fails entirely for a language | IndicF5 as last resort, only if needed. **[BRIEF]** |
| Gemini rate limit | Backoff; caching avoids repeats. |
| Gemini returns non-JSON | Re-ask once with a stricter instruction, then fail the unit. **[SUGGESTION]** |

---

## 19. Security and privacy requirements

- **API keys:** read from environment via `.env`; **never hardcoded, never printed, never logged, never committed**. `.env` is in `.gitignore`; `.env.example` holds empty placeholders only. **[BRIEF]**
- **No real personal data:** no real phone numbers, Aadhaar, PAN, or recorded calls. Only the team's own voice and synthetic content. **[BRIEF]**
- **Consent:** voice cloning only with the voice owner's consent; required checkbox in the UI. **[BRIEF]**
- **Transparency:** every output labelled **"AI-dubbed"**. **[BRIEF]**
- **Honesty:** no misleading demo; README states limits (no lip-sync, imperfect translation/pronunciation). **[BRIEF]**
- **Data leaving the machine:** source audio goes to Gnani; transcript text goes to Google (Gemini). State this in the README. **[SUGGESTION]**

---

## 20. Functional requirements

| ID | Requirement |
|---|---|
| FR1 | Accept a Hindi video ≤3 min with one speaker. |
| FR2 | Separate vocals and music with Demucs; `--no-music` skips it. |
| FR3 | Transcribe with Prisma v2.5 Batch in `hi-IN`; save the raw JSON. |
| FR4 | Produce sentence-sized units with `start, end, slot, gap`. |
| FR5 | Create and cache a voice embedding from a 5–30 s reference. |
| FR6 | Translate each unit to `ta-IN` / `bn-IN` / `mr-IN` with context, a do-not-translate list, numbers as words, JSON output, and a char budget. |
| FR7 | Synthesize each unit with cloned-voice TTS (or Timbre fallback per language). |
| FR8 | Apply the timing agent; assign each unit `fit / sped_up / rewritten / flagged` (or `failed`). |
| FR9 | QA each final clip with REST STT + rapidfuzz; set `qa_flag` below a threshold. |
| FR10 | Mix clips over `no_vocals.wav`, normalize loudness, mux onto the original video without re-encoding. |
| FR11 | Write `.srt` and `report.json`. |
| FR12 | CLI first; then a Streamlit page with the features in Section 9. |

## 21. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | **Credit efficiency:** no repeated API call for the same input (cache). |
| NFR2 | **Robustness:** one failed unit never kills the run. |
| NFR3 | **Testability:** timing logic is pure and unit-tested offline. |
| NFR4 | **Swappability:** all LLM use goes through `llm.py`. |
| NFR5 | **Security:** keys only in `.env`. |
| NFR6 | **Honesty:** claims in README/demo match reality. |
| NFR7 | **Simplicity:** no database, no accounts, no server; runs locally. |
| NFR8 | **Processing time:** a 3-min video should finish in a reasonable time for a demo (target TBD after the 30 s test). **[TEST]** |

---

## 22. Project scope

**IN [BRIEF]:** videos ≤3 min; one speaker; Hindi → Tamil, Bengali, Marathi; CLI then Streamlit; caching; metrics.

**OUT. Do not build [BRIEF]:**
- Lip-sync
- Multiple speakers / diarization-based dubbing
- Long videos
- Live/real-time dubbing
- User accounts
- A database

**Future possibilities (not for this competition):** more languages (Gnani supports 10); multi-speaker dubbing using diarization; Prisma v3.0; lip-sync; per-line editing UI beyond the stretch goal.

Rule: **ask before adding anything outside scope.** **[BRIEF]**

---

## 23. Technical challenges and risks

| # | Risk | Why it matters | Approach | Basis |
|---|---|---|---|---|
| R1 | **Cross-language voice cloning quality.** Does a Hindi-trained clone speak Tamil/Bengali/Marathi naturally? | The core promise of the product. | Nov 6 go/no-go voice test; Timbre v3.0 fallback per language. | **[TEST]** (undocumented) |
| R2 | **Marathi with cloned voice.** VC has no `language` field, and Gnani's text normalization auto-detects language from script: **Devanagari → Hindi**. Marathi is written in Devanagari. | Marathi might be read with Hindi rules (numbers, some pronunciations). | Write numbers as words ourselves (already a rule); **include a Marathi line in the voice test**; Timbre (explicit `mr-IN`) as fallback. | **[DOCS]** for the auto rule; **[TEST]** for actual impact |
| R3 | **Translation length.** Tamil is often longer than Hindi. | Many units may need rewriting → more credits, more time. | Character budget in the translation prompt; calibrate **characters-per-second of the cloned voice per language** from the voice test. | **[ASSUMPTION]** / [SUGGESTION] |
| R4 | **Translation accuracy / meaning loss when shortening.** | A short but wrong line is worse than a long correct one. | Full-transcript context; "same meaning" instruction; manual spot-check; `flagged` rather than butchering. | [BRIEF] |
| R5 | **Segmentation.** Batch output has no punctuation; segment boundaries may cut mid-sentence. | Bad units → bad translations and bad slots. | Gemini punctuation + merge; keep each unit's `start` = first segment start, `end` = last segment end. | [DOCS] (no punctuation shown) / [TEST] |
| R6 | **Timestamp accuracy.** Segment times may include leading/trailing silence. | Slots could be wrong → wrong fit decisions. | Inspect the real transcript on the 30 s clip. | **[TEST]** |
| R7 | **Speed-up artifacts.** `atempo` above ~1.2× may sound rushed. | Unnatural audio. | Cap at 1.25 as specified; tune by ear. | [BRIEF] |
| R8 | **Music separation quality.** Demucs may leave faint Hindi "ghost" voice in `no_vocals.wav`, or muffle music. | The original voice bleeding under the dub sounds bad. | Test on our clip; `--no-music` for clips without music; consider lowering the music slightly under speech. | [TEST] / [SUGGESTION] |
| R9 | **Mix quality / loudness.** Cloned voice volume ≠ music level. | Dub too quiet or too loud. | ffmpeg `loudnorm`; check by ear. | [SUGGESTION] |
| R10 | **QA by STT is noisy.** Spelling variants and formatting lower the similarity for correct audio. | False alarms. | It's a flag, not a verdict; use `verbatim` format; normalize text (strip punctuation, spaces) before comparing; pick the threshold after seeing real scores. | [BRIEF] / [SUGGESTION] |
| R11 | **Rate limits.** Some accounts allow **1 active request at a time**; no `Retry-After`. | Parallel calls will fail. | Strictly sequential Gnani calls + backoff. | **[DOCS]** |
| R12 | **Credits.** 5,000 credits; **cost per call is not documented**; no credits API documented. | Could run out mid-project (402). | Cache everything; dev on 30 s clip; check the dashboard balance before/after the first calls to learn real costs. | [BRIEF] / **[TEST]** |
| R13 | **Gemini free-tier quotas.** Per-unit calls × 3 languages + rewrites + cleanup. | Could hit daily limits on Nov 8. | Cache; check current free-tier limits in AI Studio. | **[ASSUMPTION]** (limits not checked) |
| R14 | **Processing time.** Sequential TTS + STT per unit, plus rewrites, plus Demucs. | Demo-day waiting. | Measure on the 30 s clip, extrapolate. Demucs on GPU if available. | [TEST] |
| R15 | **Audio format mismatches.** 44.1 kHz TTS clips, 16 kHz STT input, Demucs output rate, video's audio rate. | Clicks, wrong speed, mixing errors. | Normalize everything to one internal format (e.g. 44.1 kHz) before mixing; 16 kHz mono only for STT uploads. | [SUGGESTION] |
| R16 | **Environment setup.** ffmpeg missing; Python 3.14 may not suit Demucs/PyTorch. | Lost hours on day 1–2. | Install ffmpeg; use a Python 3.11 venv. | [ASSUMPTION] / [TEST] |
| R17 | **TTS text-length limit unknown.** Too-long text → 500. | Long units fail. | Units are sentence-sized; on 500, retry once then split or flag. | **[DOCS]** |

---

## 24. API limitations and things requiring testing

### Must test before building the full pipeline (Nov 6 go/no-go)

1. **Auth works** for both keys (Gnani + Gemini). Check the Gnani key has scopes for STT, TTS and voice cloning (otherwise 403).
2. **Batch STT on a 30 s Hindi clip:** real transcript shape (segments present? punctuation? timestamp quality?).
3. **Embedding** from the reference sample: real response shape (wrapped or not), accepted format.
4. **Cloned-voice TTS:** one **Tamil** and one **Bengali** sentence (brief). **Recommended: also one Marathi sentence** (risk R2). Listen for voice similarity + pronunciation.
5. **Credit cost** of each call type (dashboard balance before/after).
6. **Rate behaviour:** do back-to-back calls get 429?

### Later tests

- REST STT on a dubbed clip in `ta-IN`/`bn-IN`/`mr-IN`: response fields, similarity scores on known-good audio (to choose the QA threshold).
- Timbre v3.0 call with `language` (only if needed as a fallback).
- Demucs quality on our real clip.
- Maximum TTS text length (only if a 500 shows up).

### Known documentation gaps **[DOCS]**

- No documented credit cost per call, and no credits/balance API.
- No numeric rate limits published.
- Embedding: accepted formats, size limits, errors undocumented.
- VC: supported languages undocumented; max text length undocumented.
- Batch: punctuation behaviour undocumented.

---

## 25. Development roadmap and day-wise plan

> **Superseded (2026-11-06):** the team dropped the fixed day-by-day schedule. Development now follows **dependency-ordered stages** in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), which also holds the progress log. The original day plan is kept below for reference only. The **Nov 10, 11:59 PM IST deadline still applies.**

### Original day plan (reference only) **[BRIEF]**

| Day | Goal | Exit criterion |
|---|---|---|
| **Nov 6 (Thu)** | Setup; Prisma Batch on a 30 s clip; embedding; one cloned line each in Tamil and Bengali (+ Marathi recommended). | **Go/no-go:** the team listens and decides cloned voice vs Timbre per language. **No other modules until confirmed.** |
| **Nov 7 (Fri)** | Full CLI pipeline on the 30 s clip: cleanup, translate, synthesize, timing agent, QA, mix, export. | `python cli.py ...` produces MP4 + SRT + report for the 30 s clip. |
| **Nov 8 (Sat)** | Streamlit page; a 2–3 min video in all 3 languages; metrics. Record the demo; post on LinkedIn. | Demo video recorded; post live. |
| **Nov 9 (Sun)** | Bug fixes, README, written explanation, architecture diagram. **Submit in the evening.** | Submission sent. |
| **Nov 10 (Mon)** | Buffer only. Deadline 11:59 PM IST. | n/a |

### Nov 6 detailed order

1. Project skeleton, `.env.example`, `.gitignore`, `requirements.txt`, Python environment, ffmpeg install.
2. `gnani.py`: embedding + cloned-voice TTS (with cache + retry).
3. Generate the test sentences → **stop, the team listens.**
4. Batch STT on the 30 s clip (also part of Nov 6 per the day plan).

---

## 26. Competition requirements and submission deliverables **[BRIEF]**

- A **working application** built on at least one Gnani model/API (we use Prisma STT + Voice Cloning, with Timbre as fallback).
- **Demo video.**
- **Written explanation.**
- **Gnani models used**, with **each team member's contribution**.
- Link to a **public LinkedIn/X post** with **#GnaniAI #GreatIndianAIInternshipChallenge**.
- Deadline **Nov 10, 2026, 11:59 PM IST**.

Supporting deliverables: README (how to run, models, contributions, honest limits), architecture diagram, NOTES.md.

---

## 27. Current implementation status

*Update this section as work progresses.*

| Item | Status | Notes |
|---|---|---|
| Brief saved | ✅ Done | [PROJECT.md](PROJECT.md) |
| This context file | ✅ Done | 2026-11-06 |
| Gnani docs reviewed | ✅ Done | Key pages read 2026-11-06; differences listed in §12 and NOTES.md |
| Development plan | ✅ Done | [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md): stages + progress log |
| **Stage 0: Foundation** | ✅ Done | `src/config.py`, `src/cache.py`, `src/retry.py`; 13/13 offline tests pass |
| Python env | ✅ Done | `.venv` with Python 3.13.7 |
| ffmpeg installed | ✅ Done | 9.0.2 via winget (visible in new terminals) |
| Gnani API key in `.env` | ✅ Valid | 2026-11-06: `GET /stt/v3/batch/jobs` → HTTP 200 (free, read-only). TTS / voice-clone scope confirmed at the first Stage 1 call. **Key was pasted in chat → regenerate it before submission.** |
| Gemini API key + model in `.env` | ✅ Valid | `GEMINI_MODEL=gemini-3.6-flash`, `GEMINI_FALLBACK_MODEL=gemini-3.5-flash` (3.8 was overloaded). **Key was pasted in chat → regenerate before submission.** |
| **Stage 9: Mix + video + subtitles** | ✅ Done | First dubbed videos in `outputs/final/` (ta/bn/mr). See docs/stages/STAGE_09_mix_video.md |
| **Stage 8: Quality check** | ✅ Done | Prisma REST QA: 93.7–98.3 % on 6 clips; threshold 80 %. See docs/stages/STAGE_08_quality_check.md |
| **Stage 7: Timing agent** | ✅ Done | Ladder works with real APIs (fit / sped_up / rewritten verified). See docs/stages/STAGE_07_timing_agent.md |
| **Stage 6: Translation** | ✅ Done | Tamil/Bengali/Marathi via Gemini, char budget per slot; not yet native-checked. See docs/stages/STAGE_06_translation.md |
| **Stage 5: Units** | ✅ Done | Option A (segment = unit) + Gemini punctuation with a same-words check. See docs/stages/STAGE_05_units.md |
| **Stage 4: LLM layer** | ✅ Done | `src/llm.py`, plain REST, cached. See docs/stages/STAGE_04_llm.md |
| PyTorch / Demucs | ✅ Installed | Demucs 4.1.0 + PyTorch 2.15 **CPU** (team decision). ~0.8× real time. |
| **Stage 2: Audio prep** | ✅ Synthetic | `src/separate.py`; SDR voice 17.1 dB / music 16.7 dB on a synthetic mix. Real-video listening pending. |
| 30 s Hindi test clip | ✅ Done | `samples/chai_video.mp4` (27.6 s, own voice, soft music; git-ignored) |
| **Stage 3: Transcription** | ✅ Done | Prisma v2.5 batch works; 2 long segments, no word times → Stage 5 design choice. See docs/stages/STAGE_03_transcription.md |
| 5–30 s voice reference sample | ✅ Done | `samples/ref_voice_raw.mpeg` (22.4 s, very clean; git-ignored) |
| **Stage 1: Voice test (Tamil / Bengali / Marathi)** | ✅ GO | Cloned voice judged "okay" by the team for all 3 (not yet native-speaker checked). See docs/stages/STAGE_01_voice_test.md |

---

## 28. Important development rules and decisions

### Rules (from the brief, binding)

1. Never hardcode or print API keys; read from `.env`; never commit `.env`.
2. Read the Gnani docs before writing each client. **Don't invent endpoints or parameters.** Record every difference between real behaviour and docs in `NOTES.md`.
3. Cache every API result under `cache/`, keyed by an input hash. Never re-call for the same input.
4. Develop and test on a **30-second clip** only; full video only after that works.
5. Retry 429/5xx with backoff. A failed unit must not kill the run.
6. Timing logic in **pure functions**, tested without the network.
7. Show results as we go (transcript JSON, a synthesized clip, a timing table). **Ask before adding anything outside scope.**
8. No lip-sync or perfect-accuracy claims in the README.
9. Do **not** use Gnani Evon.
10. CLI must work before Streamlit.

### Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-11-06 | Use `prisma-v2.5` (not `gnani-prisma-v2.5`) as the batch model string | Matches the live-verified docs example; verify on first call |
| 2026-11-06 | QA via REST STT only for clips ≤30 s | Docs limit is 30 s, not 60 s |
| 2026-11-06 | Gnani calls strictly sequential | Docs: some accounts allow 1 active request; 429 has no Retry-After |
| *pending* | Prisma v2.5 vs v3.0 | Brief says v2.5. v3.0 exists (auto language, extra options). Keeping v2.5 unless the team decides otherwise. |
| *pending* | Add Marathi to the Nov 6 voice test | Risk R2; costs about 1 TTS call |
| 2026-11-06 | Python **3.13** venv (`.venv`) | 3.11 not installed; 3.14 too new for Demucs deps |
| 2026-11-06 | Dropped the day-wise plan; follow dependency-ordered stages | Team decision, see DEVELOPMENT_PLAN.md |
| 2026-11-06 | 500 → retry once; 401/402/403 → stop the run; 429/503/504 → backoff | Implemented in `src/retry.py` |
| 2026-11-06 | **Cloned voice (`vachana-vc-v1`) for Tamil, Bengali and Marathi**; Timbre v3.0 = fallback only | Team listening test: all three "okay" |
| 2026-11-06 | Marathi included in the voice test | Done, passed |
