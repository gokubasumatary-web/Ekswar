# Stage 11: Streamlit web page

**Status:** ✅ Built and tested (2026-11-07) · ⏸ team to try a full run in the browser
**Depends on:** [Stage 10](STAGE_10_pipeline_cli.md) (`pipeline.run()`)
**Next stage:** Stage 12: README, demo, submission

---

## 1. What we built

`app.py`: a web page for Ekswar, built with **Streamlit** (a Python library that turns a script into a web page; no HTML/JavaScript needed).

```powershell
.venv\Scripts\streamlit run app.py        # opens http://localhost:8501
```

## 2. Why Ekswar needs it

The CLI works, but judges and creators need to **see** it: upload, click, watch original and dub side by side, and see what the timing agent did.

## 3. What's on the page (all from the brief)

| Part | Details |
|---|---|
| Inputs | Hindi video (≤ 3 min); 5–30 s voice sample; languages (Tamil / Bengali / Marathi, one or more); names to keep; "no background music" |
| **Consent** | Required checkbox: "This is my voice, or I have permission to clone it." |
| Run | "Dub my video" button, **disabled** until video + voice + language + consent; progress bar "Step i/9: …" |
| Results per language | Original and dubbed videos **side by side**; metrics (lines, fit, slowed, sped up, rewritten, flagged, failed); QA summary; **line table** (time, Hindi, dub, timing status with tempo, QA %); **download MP4 and SRT** |
| Honesty | "🤖 AI-dubbed · voice cloned with consent · timing adjusted automatically · no lip-sync" shown at the top and on results; footer names the models |
| Details | Log and full `report.json` in expanders |

### Design
- **No dubbing logic in the page:** it calls `src.pipeline.run()`, the same function as `cli.py`, so both always behave the same.
- **Uploads saved by content hash** (`outputs/uploads/...`): re-uploading the same file reuses the cache (0 credits).
- Errors shown on the page (input problem / stopped / unexpected + log), never hidden.

## 4. Files

| File | Purpose |
|---|---|
| [app.py](../../app.py) | The page: `save_upload`, `line_table`, `can_run`, `show_results`, `main` |
| [tests/test_app.py](../../tests/test_app.py) | 4 tests incl. a headless render |
| `requirements.txt` | + `streamlit==1.67.0` |

## 5. Tests

**164/164 pass.** Page tests: button needs all inputs **including consent**; table statuses (slowed 0.90x, sped up 1.10x, failed, QA ⚠️, "not checked"); uploads are content-addressed; **headless render** (Streamlit AppTest): no exception, AI-dubbed label shown, button disabled with an info message.

**Results view with real data:** the 2-min demo's results were loaded into the page in test mode: 3 language sections, metrics (Tamil: 21 lines, 18 fit, 18 slowed, 2 sped up, 1 rewritten, 0 flagged, 0 failed), 21-row tables, download buttons, no errors. Example row: `5.0–11.8s | दिवाली है, 7 नवंबर है… | தீபாவளி, ஏழாம் தேதி… | ✅ fit (slowed 0.90x) | 96%` (the number 7 became the Tamil word for "seventh").

**Live server:** started with `streamlit run app.py`; health check `/_stcore/health` → 200.

## 5b. Professional redesign + motion (team request, 2026-11-07)

Team asked for a more professional look ("like Wispr Flow": clean, minimal, modern) with animation. **Original design**: no logos, names or exact layouts copied.

| Part | What |
|---|---|
| Theme | `.streamlit/config.toml`: warm off-white canvas, ink text, indigo accent; Streamlit chrome hidden |
| Type | Inter (UI), Instrument Serif (headlines), Noto Sans Tamil / Bengali / Devanagari for greetings |
| Hero | Two columns: headline with a moving saffron→indigo gradient; **"Dub preview" card** with animated HINDI / DUB waveforms and a greeting cycling **नमस्ते → வணக்கம் → নমস্কার → नमस्कार**; slowly floating glow |
| Layout | Full screen width (≤ 1520 px / 94 vw); keyed cards (`st.container(key="ek-card-…")` → CSS class); language pills; results in tabs; portrait videos capped at 62 vh |
| Load motion | Staggered fade-up of badge, headline, text, card, step cards |
| **Scroll motion** (pure CSS scroll-driven animations, Chrome/Edge; other browsers: no motion, nothing breaks) | thin progress bar; cards/sections reveal (rise + scale + blur→sharp); hero recedes; parallax glow; **"Why Ekswar" sentence pinned while each word lights up in turn**; two greeting rows sliding in opposite directions |
| Accessibility | `prefers-reduced-motion` turns animations off |

Files: [src/ui_style.py](../../src/ui_style.py) (all CSS + HTML), `app.py` (uses `st.html`, reloads the style module on each run), `.streamlit/config.toml`.

### Bugs found by taking real screenshots (Playwright + local Edge, headless)
| Bug | Cause | Fix |
|---|---|---|
| Design changes didn't show | Running server kept the OLD imported `ui_style` module | `importlib.reload(ui_style)` on each run |
| Hero layout broken (glow took a grid column) | `.ek-hero > div` overrode the blob's `position:absolute` | `:not(.ek-blob)` |
| Card corners/shadow never applied | Streamlit 1.67 renamed the bordered container | Keyed containers + `[class*="st-key-ek-card"]` |
| Tabs unstyled | Test id is now `stTab` | Updated selectors |
| Progress bar didn't move | Streamlit scrolls `stMain`, not the page | Named scroll timeline `--ekpage` on `stMain` |
| **Greeting card disappeared** after adding scroll motion | Scroll animation replaced the load fade-in that starts at opacity 0 | Separate layers: outer `.ek-col` recedes, inner fades in |

Verified with an automated browser run: upload → consent → Dub → results; measured progress 0→100 %, card opacity 0→1, words lit 0→20/20, greeting cycling every 2.5 s.

## 6. Security note

Streamlit prints Network/External URLs. The page uses **our** API keys on the server, so anyone who can reach it could spend our Gnani credits. **Run it only locally for the demo; don't share the network URL.**

## 7. Still to do

- [ ] Team: try a full run in the browser (e.g. upload `samples/chai_video.mp4` + voice sample; cached, so ~0 credits).
- [ ] Stretch (brief): edit one line and re-render just that line. Not built.
