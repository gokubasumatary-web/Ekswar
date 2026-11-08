# Ekswar: what it does today, and what comes next

## What Ekswar does today

| | Today |
|---|---|
| **Source language** | Hindi only |
| **Target languages** | 3: Tamil, Bengali, Marathi |
| **Direction** | One way: Hindi → Tamil, Bengali or Marathi. It **cannot** dub a Tamil, Bengali or Marathi (or any other regional-language) video into Hindi or English. |
| **Speakers** | One speaker per video |
| **Length** | Up to 3 minutes |
| **Sync** | **Timing sync only.** The voice starts and stops with the original speaker, but the lips in the video don't change. **No lip-sync.** |
| **Voice** | Covers about 89–92 % of the original speaking time, so small silences remain |
| **Translation check** | Checked automatically by Gnani Prisma (95–98 % match). Native Tamil and Bengali speakers have **not** reviewed them yet. |
| **Speed** | Runs on CPU. Separating the voice from the music takes about as long as the video itself. |

## Future plan

### 1. Lip-sync (top priority)
- Add an **optional** lip-sync step after the dub, using an open-source lip-sync model that redraws the mouth to match the new audio.
- It needs a GPU and is slow, so it stays off by default and is marked **experimental**.
- The **AI-dubbed** label and the consent rules stay in place, because lip-sync makes a video look more real.

### 2. More target languages
- Gnani's voice models list **10 languages**: Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati and Punjabi.
- Next we add **Telugu, Kannada, Malayalam, Gujarati, Punjabi and English** as targets, after testing how well the cloned voice pronounces each one and checking Prisma speech-to-text support for each language.

### 3. Any language to any language (including regional → Hindi and English)
- Today the source has to be Hindi. The plan is to accept a source video in **any supported language**, for example **Tamil → Hindi**, **Bengali → English** or **Marathi → Tamil**.
- To do this, the source language becomes a choice (or is detected automatically), and the transcription, punctuation and translation steps become language-neutral. The timing agent already works for any language.
- This lets regional creators reach Hindi and English audiences too, not just the other way round.

### 4. Several speakers
- Detect who is speaking when (speaker diarization), clone each person's voice with their consent, and dub each speaker in their own voice.

### 5. Longer videos
- Go past 3 minutes by processing the video in chunks and resuming a run that stopped partway.

### 6. Better quality and review
- **Native-speaker review:** a reviewer can edit any line on the web page, and only that line gets re-rendered.
- **Fewer gaps:** close the remaining 8–11 % of silence with better pacing.
- **Pronunciation fixes:** a list of names and terms with their correct pronunciation.

### 7. Speed and scale
- GPU support for voice separation (and lip-sync).
- Run lines in parallel, plus a queue so several videos can be processed at once.

## Order of work

| Phase | Work |
|---|---|
| **Next** | More target languages · edit one line and re-render it · fewer gaps |
| **Then** | Any language to any language (regional → Hindi/English) · several speakers |
| **Later** | Optional lip-sync (GPU) · longer videos · queue and scale |
