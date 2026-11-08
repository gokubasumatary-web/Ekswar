# Demo video script for two people (about 3:00)

**Who:** **Guthal (G)**, whose voice gets dubbed, and **Ananya (A)**, who explains the tech. Swap the names if you want to switch roles.
**Setup:** the Streamlit page is running (`.venv\Scripts\streamlit run app.py`) with the cached 2-minute Diwali run, so it finishes in seconds. Record the screen at 1080p. Keep `.env`, terminals and dashboards off screen.

---

### 1. Hook (0:00–0:15) · both on camera
**G:** I make videos in Hindi. But most of India doesn't speak Hindi.
**A:** So we built **Ekswar**. It dubs his video into Tamil, Bengali and Marathi, in **his own voice**.
**G:** And I don't speak any of those languages.

### 2. The problem (0:15–0:30) · hero section on screen
**A:** Subtitles get skipped on phones. Human dubbing costs a lot and replaces the creator's voice. And auto-dubbing drifts out of sync, because a translated line almost never takes as long to say as the original.

### 3. How it works (0:30–0:50) · scroll through the 4 steps
**A:** Ekswar listens with **Gnani Prisma**, translates with **Gemini**, and speaks every line with **Gnani voice cloning**.
**G:** Then a **timing agent** fits every line to my original timing, and the background music stays.

### 4. Live run (0:50–1:10) · upload, pick 3 languages, tick consent, click Dub
**G:** I upload my video and a 20-second voice sample. Consent is required: it has to be my own voice.
**A:** *(progress steps on screen)* It separates the voice from the music, transcribes, splits lines at his natural pauses, translates, speaks, times, checks quality, and mixes.

### 5. The result (1:10–1:40) · Tamil tab: original for 8 s, then the dub for 10 s
**G:** That's me in Hindi… *(play dub)* …and that's me in Tamil. Same video, same music.
**A:** Same voice, too.

### 6. Timing agent (1:40–2:05) · "What the timing agent did" table, point at the rows
**A:** This is the main part. Every dubbed line is spoken, **measured**, and fixed in the gentlest way that works.
**A:** This one was too long, so it got a slight **speed-up**. This one was still too long, so Gemini **rewrote it shorter**. These were short, so they were **slowed a little**.
**G:** So my voice starts and stops when I do. No words are ever cut.

### 7. Other languages (2:05–2:20) · Bengali tab 5 s, then Marathi tab 5 s
**G:** Bengali… *(play)* …Marathi. *(play)*
**A:** On our 2-minute video that was 63 lines in 3 languages, and none failed.

### 8. Honest limits (2:20–2:35) · QA column and the AI-dubbed label
**A:** Gnani Prisma listens back to every dubbed line to check it says what we meant. That came out at 95 to 98 percent.
**G:** It's labelled AI-dubbed. It matches **timing, not lip movement**, and native speakers haven't checked the translations yet.

### 9. What's next (2:35–2:50) · both on camera, or the README "Future work" section
**G:** Right now it's Hindi in, and three languages out.
**A:** Next we're adding more Indian languages, and the other direction too: Tamil or Bengali **into Hindi and English**. Then several speakers, and optional **lip-sync**.

### 10. Close (2:50–3:00) · both on camera, or the GitHub page
**A:** Built on Gnani Prisma and Gnani voice cloning.
**G & A:** **Ekswar: one voice, every Indian language.**

---

**Tips**
- Rehearse once together. Speak slowly. Keep each clip short.
- If one of you is camera-shy, record the voice over the screen only.
- Make sure the **rewritten** row is on screen (in Tamil). It's the clearest proof the timing agent works.
- Post with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**, tag Gnani's official page, and tag each other (see [LINKEDIN_POST.md](LINKEDIN_POST.md)).
