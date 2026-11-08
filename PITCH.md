# Ekswar: one voice, every Indian language

**Problem.** A Hindi creator reaches only part of India. Subtitles get skipped on phones, human dubbing is costly and replaces the creator's voice, and automatic dubbing drifts out of sync, because a translated line rarely takes as long to say as the original.

**Solution.** Ekswar takes a short Hindi video and a 20-second voice sample and returns the **same video dubbed into Tamil, Bengali or Marathi, in the creator's own cloned voice**, with every line timed to where it was originally spoken and the **background music kept**. It also writes subtitles and a per-line report. It runs as a web app and a command-line tool.

**The innovation: a timing agent.** Each dubbed line is spoken, **measured**, and fixed with the gentlest option that fits: a fuller rephrasing if it's far too short, a slight slow-down, a pitch-preserving speed-up, or an **LLM rewrite** if it's too long. Lines that still don't fit are flagged; speech is never cut. Long source lines are first split at the speaker's natural pauses.

**Built on Gnani**
- **Prisma v2.5 (Batch STT):** Hindi transcript with timestamps, the base for every time slot.
- **Prisma v2.5 (REST STT):** exact text when splitting at pauses, and an **automatic check of every dubbed line**.
- **Voice cloning (`vachana-vc-v1`):** every line spoken in the creator's voice.

Also: Google Gemini (translation, rewriting), Demucs (voice/music separation), ffmpeg.

**Results (our own 2-minute video, 3 languages, 63 lines):** 0 failed, 0 flagged. Gnani's recognition matched the intended text at **95–98 %**. The cloned voice fills **89–92 %** of the original speaking time.

**Honest limits.** No lip-sync (timing only); translations not yet reviewed by native speakers; Hindi source only, 3 target languages, one speaker, ≤ 3 minutes. It cannot yet dub regional languages into Hindi or English.

**Next.** More Indian languages (Telugu, Kannada, Malayalam, Gujarati, Punjabi, English); any direction, including regional → Hindi/English; several speakers; optional lip-sync.

**Reliability.** Every API result is cached (re-runs cost no credits); a failed line never stops a run; 173 automated tests.

**Links:** code and docs in this repository · demo video and post linked in the submission form.
