# Ekswar: dub Indian-language videos in the creator's own voice

Tagline: One voice. Every Indian language.

## Context (read first)
- Entry for the Great Indian AI Internship Challenge by Gnani AI. Deadline: **Nov 10, 2026, 11:59 PM IST**. Today is Nov 6. Team of 2 students.
- Rule: the app must be a working application built on at least one Gnani model or API. The submission needs a demo video, a written explanation, the Gnani models used with each member's contribution, and a link to a public LinkedIn/X post (#GnaniAI #GreatIndianAIInternshipChallenge).
- Do not use real personal data: no real phone numbers, Aadhaar, PAN, or recorded calls. Only my own voice and synthetic content. No misleading demos; be honest about limits.
- STATUS: [fill in: voice test done? result for Tamil/Bengali/Marathi?]
- STATUS: [fill in: Gnani key and Gemini key working? yes/no]

## What it does
Takes a short Hindi video and produces the same video dubbed in Tamil, Bengali or Marathi. The dub is in the creator's cloned voice, each line is timed to fit the original, and the background music is kept. Also outputs subtitles and a metrics report.

The tricky part, and the main thing to demo: translated lines often run longer than the original, so a timing agent measures every dubbed line and shortens or adjusts it until it fits.

## Scope (4 days, keep it small)
IN: videos of 3 minutes or less, one speaker, Hindi source into Tamil, Bengali and Marathi. CLI pipeline first, then a Streamlit page. Caching of every API result. Metrics.
OUT: lip-sync, multiple speakers, long videos, live dubbing, user accounts, a database. Do not build any of these.

## Models
Gnani (all required to do real work):
- Prisma v2.5: speech-to-text. Batch API for the original video, REST API to re-check each dubbed line.
- Gnani Voice Cloning (`vachana-vc-v1`): speaks every translated line in the creator's voice.
- Timbre v3.0 (`timbre-v3.0`): backup voice if cloning sounds wrong in a language.

Not Gnani:
- LLM for cleanup, translation, shortening: Gemini on the free tier. Keep it behind one function (`llm.py`) so it can be swapped. Model name comes from the env var `GEMINI_MODEL`; check the current model names in Google AI Studio rather than guessing.
- Demucs (open-source): splits voice from background music.
- ffmpeg: audio and video processing. Optional: IndicF5 only if Gnani cloning fails for a language.

Gnani's LLM, Evon, is NOT on the API. Do not use it.

## Gnani API facts (from docs.gnani.ai; re-check there, start from https://docs.gnani.ai/llms.txt)
Base URL: `https://api.vachana.ai`. Auth header on every request: `X-API-Key-ID: <GNANI_API_KEY>`.

**Batch STT** (original video):
1. `POST /stt/v3/batch/jobs`, multipart: field `config` (JSON, type application/json) + field `files`. Config: `{"model":"gnani-prisma-v2.5","language_code":"hi-IN","mode":"transcribe","with_diarization":false,"is_multi_channel":false}`. Optional `with_denoise`, `bias_list` (single words, letters only, max 100), `bias_score`.
2. `POST /stt/v3/batch/jobs/{job_id}/start`. Creating a job does NOT start it.
3. Poll `GET /stt/v3/batch/jobs/{job_id}` every 10 s until COMPLETED (terminal states also include FAILED, PARTIAL_FAILURE).
4. `GET /stt/v3/batch/jobs/{job_id}/files?status=COMPLETED` gives `transcript_url`; then `GET` that URL (expires in 1 hour).
5. The transcript JSON has `full_transcript` and segments with `start_time`, `end_time`, `text`, `speaker_id`. The docs' sample download shows only `full_transcript`, so inspect the real output and handle both cases. Do not rely on `segment_id` (the sample shows 0 for all).
- Direct upload max is 10 MB per file. Convert the voice track to 16 kHz mono WAV before uploading (`ffmpeg -ar 16000 -ac 1`); 3 minutes is about 5.8 MB.
- Batch languages include hi-IN, ta-IN, bn-IN, mr-IN, en-IN. Batch output has no punctuation and no number formatting.

**STT REST** (quality check, clips up to 60 s): `POST /stt/v3`, multipart `audio_file` and `language_code`, response has `transcript`. Verify exact fields in the docs.

**Voice clone embedding** (once per voice, cache it): `POST /api/v1/tts/voice-clone/embeddings`, multipart `audio_file` (WAV/MP3, 5-30 s of clean speech). The docs show the response two ways: `{embedding, shape, dtype}` directly, or wrapped in `data.voice_clone_embedding`. Handle both.

**Cloned-voice TTS:** `POST /api/v1/tts/inference`, JSON:
```json
{"text": "...", "model": "vachana-vc-v1",
 "audio_config": {"sample_rate": 44100, "encoding": "linear_pcm", "container": "wav"},
 "speaker_embedding": {"embedding": "...", "shape": [1,768], "dtype": "torch.bfloat16"}}
```
Returns binary audio. There is NO language field. Whether the cloned voice speaks Tamil/Bengali/Marathi well is undocumented; that's what the voice test checks. Errors: 400, 429 (rate limit; back off), 500, 503.

**Timbre v3.0 backup:** same endpoint, JSON with `text`, `model:"timbre-v3.0"`, `voice` (e.g. Shivani, Avinash, Lakshmi), `language` (`ta-IN`, `bn-IN`, `mr-IN`, `hi-IN`...), `speed` (0.85-1.15), `audio_config`. Every v3.0 voice speaks all 10 languages.

**TTS input tip from the docs:** write numbers, dates and currency as spoken words in the target language; raw digits get mispronounced.

## Pipeline
1. Extract audio from the video (ffmpeg). Run Demucs two-stem separation: `vocals.wav` and `no_vocals.wav` (the music). Provide a `--no-music` flag that skips Demucs.
2. Convert `vocals.wav` to 16 kHz mono WAV. Send it to Prisma Batch (`hi-IN`). Save the raw JSON.
3. LLM cleanup: add punctuation and merge tiny segments into sentence-sized units. Each unit gets `start`, `end`, `slot = end - start`, and `gap` to the next unit.
4. Voice embedding from my reference sample (cached).
5. LLM translation, one call per unit, with the full transcript as context. Rules: keep names from a do-not-translate list, write numbers as words in the target language, return JSON, and stay under a character budget based on the slot.
6. Synthesize each translated unit with cloned-voice TTS. Measure each clip's duration.
7. **Timing agent**, per unit:
   - `budget = slot + 0.5 * gap`.
   - If duration <= budget: pad with silence. Status `fit`.
   - Elif duration <= budget * 1.15: speed up with ffmpeg `atempo`. Status `sped_up`.
   - Else: ask the LLM to shorten it (same meaning, target length about budget/duration of the current text), re-synthesize, and re-check. Up to 3 tries. Status `rewritten`.
   - If still too long: try `atempo` up to 1.25. If it fits, status `sped_up`. Otherwise keep the shortest version, status `flagged`. Never cut speech mid-word.
   - Thresholds are starting values, to be tuned by ear.
8. Quality check: transcribe each final clip with STT REST in the target language and compare it with the intended text (character-level similarity, e.g. rapidfuzz). Below a threshold, mark `qa_flag`. This is a flag, not a verdict, because the STT output formatting differs.
9. Mix: place each clip at its `start` time on a silent track, overlay on `no_vocals.wav`, normalize loudness, and mux onto the original video (copy the video stream, no re-encode). Write an `.srt` from the translated units.
10. Write `report.json`: total units, fit, sped_up, rewritten, flagged, qa_flags, average similarity, processing time, and Gnani credits used if visible.

## Files
```
ekswar/
  .env.example        # GNANI_API_KEY=  GEMINI_API_KEY=  GEMINI_MODEL=
  .gitignore          # .env, cache/, outputs/, *.wav, *.mp4
  README.md           # models used + each member's contribution + how to run
  NOTES.md            # every place the real API differed from the docs
  requirements.txt
  src/ gnani.py  llm.py  separate.py  units.py  translate.py  timing.py  qa.py  mix.py  pipeline.py
  cli.py              # python cli.py --video in.mp4 --lang ta-IN --ref ref_long.wav
  app.py              # Streamlit
  tests/              # timing.py logic tested without any API calls
```

## Streamlit page (build after the CLI works)
Upload video; upload a 5-30 s voice sample; pick Tamil / Bengali / Marathi; consent checkbox ("this is my voice or I have permission", required); Run with a progress display; show original and dubbed videos side by side; show the unit table (original, translation, status, QA score); show the metrics; download buttons for MP4 and SRT. Label every output "AI-dubbed". Stretch only: edit a line and re-render just that line.

## Rules for you (the coding agent)
1. Never hardcode or print API keys. Read them from env via `.env`. Never commit `.env`.
2. Read the Gnani docs before writing each client. Do not invent endpoints or parameters. If the real response differs from the docs, adapt the code and record it in NOTES.md.
3. Cache every API result on disk under `cache/` keyed by a hash of the input (embedding, transcript, each translation, each synthesized clip). I have limited credits (5,000), so never re-call for the same input.
4. Develop and test on a 30-second clip only. Run the full video only after that works.
5. Retry 429/5xx with backoff. A failed unit must not kill the whole run; mark it and continue.
6. Keep timing logic in pure functions so it can be tested without the network.
7. Show me results as you go (transcript JSON, one synthesized clip, a timing table), and ask before adding anything outside the scope above.
8. Do not claim lip-sync or perfect accuracy in the README. State the limits honestly.

## Day plan
- **Nov 6 (today):** setup, Prisma on a 30 s clip, embedding, one cloned line each in Tamil and Bengali. Stop and let me listen. This is the go/no-go gate.
- **Nov 7:** the full CLI pipeline on the 30 s clip: cleanup, translate, synthesize, timing agent, QA check, mix, export.
- **Nov 8:** Streamlit page, a 2-3 minute video in all 3 languages, metrics. I record the demo and post on LinkedIn.
- **Nov 9:** bug fixes, README, written explanation, architecture diagram. Submit in the evening.
- **Nov 10:** buffer only.

## Start here
Begin with Nov 6 only. First read the Gnani docs, set up the project skeleton and `.env.example`, then build `gnani.py` for the embedding endpoint and cloned-voice TTS, and generate one Tamil and one Bengali sentence from my reference sample. Do not start the other modules until I confirm the voices are good.
