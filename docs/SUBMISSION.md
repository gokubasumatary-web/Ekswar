# Ekswar: submission write-up

**Great Indian AI Internship Challenge by Gnani AI · Team of 2**

## 1. The problem

Most Indian video creators speak one language, and their audience speaks many. Subtitles are easy to skip on a phone. Human dubbing is slow and expensive, and it replaces the creator's voice with someone else's. Automatic dubbing has a less obvious problem: **a translated sentence rarely takes as long to say as the original**. Line after line the dub drifts out of step with the video.

## 2. What Ekswar does

Upload a Hindi video (one speaker, up to 3 minutes) and a 5–30 second sample of your voice, and pick Tamil, Bengali or Marathi. Ekswar returns:

- the **same video, dubbed in your own cloned voice**,
- every line **placed and timed where you originally said it**,
- your **background music preserved**,
- **subtitles** (.srt) and a **metrics report** showing what happened to every line.

It runs as a web page (Streamlit) and as a command-line tool.

## 3. The main idea: a timing agent

After each translated line is spoken in the cloned voice, Ekswar **measures it** and picks the gentlest fix that makes it fit:

1. fits → keep it. If it fills less than 75 % of the original time, ask the LLM once for a **fuller, natural** line (same meaning, no new facts), kept only if it still fits; then slow it slightly (never below 0.85×) if it's still short;
2. up to 15 % too long → speed it up without changing pitch;
3. more than 15 % too long → **ask the LLM to rewrite the line shorter**, speak it again, re-check (up to three times);
4. still too long → speed up to 1.25× on the shortest version, otherwise **flag it** for a human. Speech is never cut.

Long source segments are first **split at the speaker's natural pauses**, so each dubbed line starts where the speaker starts that part.

## 4. Gnani models and APIs used (all doing real work)

| Gnani model / API | What it does in Ekswar |
|---|---|
| **Prisma v2.5, Batch STT** (`/stt/v3/batch/jobs`) | Transcribes the Hindi voice track with timestamps: the base for every line and every time slot |
| **Prisma v2.5, REST STT** (`/stt/v3`) | (a) Gets the exact text of each piece when long segments are split at pauses; (b) **listens to every dubbed line** in Tamil/Bengali/Marathi as an automatic quality check |
| **Voice clone embeddings** (`/api/v1/tts/voice-clone/embeddings`) | Turns the creator's 5–30 s sample into a voice embedding (once, cached) |
| **Cloned-voice TTS `vachana-vc-v1`** (`/api/v1/tts/inference`) | Speaks every translated line, and every shortened rewrite, in the creator's voice |

Timbre v3.0 was kept as a fallback, but **was not needed**: the team's listening test accepted the cloned voice in all three languages.

Non-Gnani tools: Google Gemini (punctuation, translation, shortening), Demucs (voice/music separation), ffmpeg (audio/video).

## 5. Results

On our own 117-second Hindi test video, in all three languages (63 dubbed lines): **0 failed, 0 flagged**. Gnani's speech recognition matched the intended text with **95–98 % average similarity**. The timing agent made 39 lines fuller, slowed 49 slightly, sped up 2 and rewrote 1 (Tamil). The dubbed voice now fills **89–92 %** of the original speaking time (it was 69–78 % before the fuller-line step), so the voice starts and stops much closer to the speaker's mouth movements.

## 6. Engineering that made it reliable

- **Every API result is cached** by a hash of its inputs, so re-runs cost no credits. A crash while waiting for a batch job resumes the same job instead of paying for a new one.
- **Failures are contained:** a failed line is marked and the run continues; key/credit errors stop it immediately; HTTP 504s become "not checked", never "passed".
- **Gemini free-tier handling:** backup model chain; per-minute vs per-day quota detected from Google's own error details; answers in the wrong script are never cached and are retried on another model.
- **164 automated tests**, including the whole pipeline with fake Gnani/Gemini clients.
- Every place the real APIs differed from their docs is recorded in `NOTES.md`.

## 7. Honest limits

- **No lip-sync**: timing sync only; the lips in the video don't change.
- Translations **not yet reviewed by native speakers**; QA measures intelligibility, not fluency.
- Hindi source only; one speaker; up to 3 minutes.
- The cloned voice speaks faster than the original speaker, so some silence remains inside lines.

## 8. Team contributions

| Member | Contribution |
|---|---|
| Guthal Basumatary | *[to be filled in by the team]* |
| Ananya | *[to be filled in by the team]* |

Development was assisted by Claude Code (AI coding assistant).

## 9. Links

- Code: https://github.com/gokubasumatary-web/Ekswar
- Demo video: *[link]*
- LinkedIn / X post: *[link]*
