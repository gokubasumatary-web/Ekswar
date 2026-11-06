# Stage 1: Voice test (Gnani voice cloning)

**Status:** ✅ Done. **GO**: cloned voice accepted for Tamil, Bengali and Marathi (team listening test, 2026-11-06)
**Depends on:** [Stage 0: Foundation](STAGE_00_foundation.md)
**Next stage:** Stage 2: Audio prep (extraction + music separation)

---

## 1. What we built

The first real Gnani integration:
- turn a creator's voice recording into a **voice embedding**,
- use that embedding to **speak any text in the creator's voice**,
- a test script that speaks one sentence each in **Tamil, Bengali and Marathi**.

## 2. Why Ekswar needs it

The cloned voice is what makes Ekswar *Ekswar*: the creator sounds like themselves in every language. But Gnani's docs only show a **Hindi** example, and cloning has **no language setting**. Nobody knows if it pronounces Tamil, Bengali and Marathi well. If it doesn't, we switch that language to Gnani's **Timbre v3.0** stock voices, and later stages change. So we test this **before** building anything around it.

## 3. How it works

### What is a voice embedding?
A list of numbers that describes *how a voice sounds* (pitch, tone, texture), not *what* is said. Gnani's model listens to the 5–30 s sample and produces a **[1 × 768]** array: 768 numbers. They arrive packed as a 4,096-character text string, plus the shape and data type. We send this embedding with every sentence we want spoken.

### The flow
```
samples/ref_voice_raw.mpeg   (22.4 s WhatsApp recording, MP3 inside)
        │  ffmpeg: mono, 16-bit, 44.1 kHz WAV, trim leading silence
        ▼
outputs/voice_test/ref_clean.wav   (21.6 s)
        │  POST /api/v1/tts/voice-clone/embeddings   (multipart: audio_file)
        ▼
speaker_embedding {embedding: "...", shape: [1,768], dtype: "torch.bfloat16"}  → cached
        │  POST /api/v1/tts/inference
        │  {text, model: "vachana-vc-v1", audio_config, speaker_embedding}
        ▼
WAV audio in the cloned voice   → cached → outputs/voice_test/<lang>.wav
```

### Safety built in
- **Cache:** the embedding is keyed by the reference file's fingerprint; each clip by text + model + settings + embedding. Second runs cost **0 credits** (verified).
- **Retry rules:** 429/503 → back off; 401/402/403 → stop; 500 → one retry (from Stage 0).
- **Response checks:**
  - The embedding parser accepts both possible response shapes and fails loudly on anything else.
  - The TTS result must really start with `RIFF…WAVE`. A JSON error disguised as a 200 is rejected, not saved as "audio".

## 4. Files

| File | Purpose |
|---|---|
| [src/audio.py](../../src/audio.py) | ffmpeg/ffprobe helpers: `to_wav()`, `duration()`, `duration_of_bytes()` |
| [src/gnani.py](../../src/gnani.py) | `GnaniClient.create_voice_embedding()`, `GnaniClient.synthesize_cloned()`, plus pure parsers |
| [scripts/voice_test.py](../../scripts/voice_test.py) | Runs the voice test, prints a table |
| [tests/test_gnani_parsing.py](../../tests/test_gnani_parsing.py) | 5 offline tests for response parsing |

## 5. How we tested it

```powershell
.venv\Scripts\python -m pytest -q                                      # offline
.venv\Scripts\python -m scripts.voice_test samples\ref_voice_raw.mpeg  # real API
```

## 6. Results (2026-11-06)

**Reference sample check** (before any API call):

| Check | Value |
|---|---|
| Length | 22.4 s raw → 21.6 s after trimming leading silence |
| Speech level | mean −15.8 dB, peak −0.9 dB (loud, not clipped) |
| Background noise | −63.6 dB (≈48 dB below speech: very clean) |

**Offline tests:** 18/18 passed (13 foundation + 5 parsing).

**Real API run:**
```
Embedding: shape=[1, 768] dtype=torch.bfloat16 length=4096 chars

lang   chars   secs  chars/s  file
ta-IN    146   8.26     17.7  outputs\voice_test\ta-IN.wav
bn-IN     96   7.11     13.5  outputs\voice_test\bn-IN.wav
mr-IN    108   7.33     14.7  outputs\voice_test\mr-IN.wav

Real Gnani API calls this run: 4 (cache hits: 0, misses: 4)
```
- Output format: 16-bit PCM WAV, 44,100 Hz, mono.
- Embedding response was the **wrapped** form (`data.voice_clone_embedding`), as the docs show.
- **Second run: 0 API calls, 4 cache hits.** The cache works.

**About the chars/s numbers:** these are *one sentence per language*, so they're only a first rough hint for the translation length budget (Stage 6). Note that characters ≠ sounds: Tamil script uses more characters per syllable, so its chars/s looks higher. We'll measure more lines later before relying on this.

## 7. Problems hit

None in the API calls; everything worked first time and matched the docs.

## 8. ⏸ The go/no-go decision (team)

Listen to:
- `outputs/voice_test/ta-IN.wav` (Tamil)
- `outputs/voice_test/bn-IN.wav` (Bengali)
- `outputs/voice_test/mr-IN.wav` (Marathi)
- and compare with `outputs/voice_test/ref_clean.wav` (your real voice).

For each language, judge:
1. **Does it sound like you?**
2. **Is the pronunciation natural?** Ideally ask someone who speaks the language.
3. **Any glitches** (robotic parts, wrong words, cut-offs)?

**Verdict (2026-11-06):** the team listened and judged all three "okay".

| Language | Decision |
|---|---|
| Tamil | ✅ cloned voice (`vachana-vc-v1`) |
| Bengali | ✅ cloned voice (`vachana-vc-v1`) |
| Marathi | ✅ cloned voice (`vachana-vc-v1`) |

**What we can honestly claim:** the team found the cloned voice acceptable in all three languages on one test sentence each. Not yet checked by native speakers of Tamil, Bengali or Marathi, so don't claim "native-quality pronunciation". Timbre v3.0 stays available as a fallback if longer content reveals problems.

## 9. How this connects to the rest of Ekswar

- Stage 7 (timing agent) calls `synthesize_cloned()` for every line, and again for each rewrite.
- The embedding is created **once** per voice sample and reused for all lines and languages.
- If a language fails the listening test, we add a Timbre v3.0 function to `gnani.py` for it.
