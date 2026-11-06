"""Stage 1 voice test: one cloned-voice sentence each in Tamil, Bengali, Marathi.

Usage:
    .venv\\Scripts\\python -m scripts.voice_test samples\\ref_voice_raw.mpeg

Cost: 1 embedding call + 1 TTS call per sentence, the first time only.
Re-running is free (everything is cached).
Output: outputs/voice_test/<lang>.wav + a table of durations.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.audio import duration, duration_of_bytes, to_wav
from src.config import OUTPUT_DIR
from src.gnani import GnaniClient

# Same meaning in each language; numbers avoided on purpose (see TTS docs).
# "Hello friends, today I'm going to tell you about something new.
#  We all watch videos on our phones every day."
SENTENCES = {
    "ta-IN": "வணக்கம் நண்பர்களே, இன்று நான் உங்களுக்கு ஒரு புதிய விஷயத்தைப் பற்றி சொல்லப் போகிறேன். "
             "நாம் அனைவரும் தினமும் நம் போனில் வீடியோக்களைப் பார்க்கிறோம்.",
    "bn-IN": "নমস্কার বন্ধুরা, আজ আমি তোমাদের একটা নতুন জিনিসের কথা বলব। "
             "আমরা সবাই রোজ আমাদের ফোনে ভিডিও দেখি।",
    "mr-IN": "नमस्कार मित्रांनो, आज मी तुम्हाला एका नवीन गोष्टीबद्दल सांगणार आहे. "
             "आपण सगळे रोज आपल्या फोनवर व्हिडिओ पाहतो.",
}


def main(ref_path: str) -> None:
    out_dir = OUTPUT_DIR / "voice_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Clean reference: mono 16-bit WAV, leading silence trimmed.
    ref_wav = to_wav(ref_path, out_dir / "ref_clean.wav", sample_rate=44100, channels=1,
                     trim_leading_silence=True)
    print(f"Reference: {ref_wav.name}  {duration(ref_wav):.2f} s")

    client = GnaniClient()

    # 2. Voice embedding (cached after the first run).
    emb = client.create_voice_embedding(ref_wav)
    print(f"Embedding: shape={emb['shape']} dtype={emb['dtype']} length={len(emb['embedding'])} chars")

    # 3. One sentence per language.
    print(f"\n{'lang':6} {'chars':>5} {'secs':>6} {'chars/s':>8}  file")
    for lang, text in SENTENCES.items():
        wav = client.synthesize_cloned(text, emb, what=f"voice test {lang}")
        path = out_dir / f"{lang}.wav"
        path.write_bytes(wav)
        secs = duration_of_bytes(wav)
        print(f"{lang:6} {len(text):5d} {secs:6.2f} {len(text) / secs:8.1f}  {path.relative_to(OUTPUT_DIR.parent)}")

    print(f"\nReal Gnani API calls this run: {client.api_calls} "
          f"(cache hits: {client.cache.hits}, misses: {client.cache.misses})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.voice_test <reference audio>")
    main(sys.argv[1])
