"""Visual style for the Streamlit page (CSS + HTML snippets). Original design:
warm off-white canvas, clean type, soft cards, a saffron->indigo accent, gentle motion."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=Noto+Sans+Tamil:wght@500&family=Noto+Sans+Bengali:wght@500&family=Noto+Sans+Devanagari:wght@500&display=swap');

:root {
  --ink: #18181B; --muted: #6B6B76; --line: #E6E3DA; --card: #FFFFFF;
  --accent: #4F46E5; --saffron: #F59E0B; --soft: #F1EFE8;
  --ease: cubic-bezier(.2,.7,.2,1);
}
html, body, [class*="css"], .stMarkdown, p, label, input, textarea, button {
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}
/* hide Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], header [data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stHeader"] { background: transparent; }
/* use the whole screen width (up to a comfortable maximum) */
[data-testid="stMainBlockContainer"], .block-container {
  max-width: min(1520px, 94vw) !important; padding-left: 2.5vw !important; padding-right: 2.5vw !important;
  padding-top: 1.6rem; padding-bottom: 4rem; }

/* ---------- motion ---------- */
@keyframes ek-up { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
@keyframes ek-shine { 0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; } }
@keyframes ek-float { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-30px,25px) scale(1.08); } }
@keyframes ek-wave { 0%,100% { transform: scaleY(.25); } 50% { transform: scaleY(1); } }
@keyframes ek-cycle { 0% { opacity: 0; transform: translateY(12px); } 4%,21% { opacity: 1; transform: none; }
                      25%,100% { opacity: 0; transform: translateY(-12px); } }
@keyframes ek-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(79,70,229,.35); } 50% { box-shadow: 0 0 0 8px rgba(79,70,229,0); } }
.ek-a { opacity: 0; animation: ek-up .8s var(--ease) forwards; }
.d1 { animation-delay: .05s; } .d2 { animation-delay: .18s; } .d3 { animation-delay: .32s; }
.d4 { animation-delay: .46s; } .d5 { animation-delay: .6s; } .d6 { animation-delay: .74s; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; }
  .ek-a { opacity: 1; } }

/* ---------- hero ---------- */
.ek-hero { position: relative; display: grid; grid-template-columns: 1.25fr 1fr; gap: 3vw; align-items: center;
  padding: 2.4rem 0 1.2rem 0; }
.ek-blob { position: absolute; right: 4%; top: -6%; width: 46vw; max-width: 640px; aspect-ratio: 1; z-index: 0;
  background: radial-gradient(closest-side, rgba(245,158,11,.22), rgba(79,70,229,.12) 55%, transparent 72%);
  filter: blur(12px); animation: ek-float 14s ease-in-out infinite; pointer-events: none; }
/* (not the blob: it must stay absolute, outside the grid) */
.ek-hero > div:not(.ek-blob) { position: relative; z-index: 1; }
.ek-badge { display: inline-flex; gap: .5rem; align-items: center; font-size: .8rem; font-weight: 600;
  color: var(--ink); background: rgba(255,255,255,.8); backdrop-filter: blur(6px); border: 1px solid var(--line);
  border-radius: 999px; padding: .36rem .9rem; }
.ek-dot { width: 8px; height: 8px; border-radius: 50%; background: linear-gradient(135deg, var(--saffron), var(--accent));
  animation: ek-pulse 2.4s ease-in-out infinite; }
.ek-title { font-family: 'Instrument Serif', Georgia, serif !important; font-weight: 400;
  font-size: clamp(2.8rem, 5.6vw, 5.4rem); line-height: 1.0; letter-spacing: -0.02em; color: var(--ink);
  margin: 1.1rem 0 .9rem 0; }
.ek-title em { font-style: italic; color: transparent; background-clip: text; -webkit-background-clip: text;
  background-image: linear-gradient(90deg, var(--saffron), #E9572F, var(--accent), var(--saffron));
  background-size: 200% auto; animation: ek-shine 6s linear infinite; }
.ek-sub { font-size: clamp(1rem, 1.2vw, 1.18rem); color: var(--muted); max-width: 660px; line-height: 1.6; margin: 0; }

/* live preview card */
.ek-preview { background: rgba(255,255,255,.82); backdrop-filter: blur(10px); border: 1px solid var(--line);
  border-radius: 24px; padding: 1.4rem 1.5rem; box-shadow: 0 20px 50px rgba(24,24,27,.08); }
.ek-preview .hd { display: flex; justify-content: space-between; align-items: center; font-size: .78rem;
  font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.ek-live { display: inline-flex; align-items: center; gap: .4rem; color: #16A34A; }
.ek-live::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #16A34A;
  animation: ek-pulse 1.8s ease-in-out infinite; }
.ek-row { display: flex; align-items: center; gap: .9rem; margin-top: 1.1rem; }
.ek-tag { font-size: .72rem; font-weight: 700; color: var(--muted); width: 64px; flex: none; }
.ek-wave { display: flex; align-items: center; justify-content: space-between; gap: 3px; height: 46px; flex: 1; }
.ek-wave span { display: block; flex: 1; max-width: 6px; min-width: 3px; height: 100%; border-radius: 3px; transform-origin: center;
  background: linear-gradient(180deg, var(--saffron), var(--accent)); animation: ek-wave 1.2s ease-in-out infinite; }
.ek-wave.alt span { background: linear-gradient(180deg, #A5B4FC, var(--accent)); }
.ek-greet { position: relative; height: 3.2rem; margin-top: 1.2rem; }
.ek-greet span { position: absolute; left: 0; top: 0; opacity: 0; font-size: 2.2rem; font-weight: 500; color: var(--ink);
  animation: ek-cycle 10s var(--ease) infinite; }
.ek-greet span small { font-size: .8rem; color: var(--muted); font-family: 'Inter', sans-serif; margin-left: .6rem;
  font-weight: 600; letter-spacing: .04em; }
.ek-greet .g1 { animation-delay: 0s; font-family: 'Noto Sans Devanagari', sans-serif; }
.ek-greet .g2 { animation-delay: 2.5s; font-family: 'Noto Sans Tamil', sans-serif; }
.ek-greet .g3 { animation-delay: 5s; font-family: 'Noto Sans Bengali', sans-serif; }
.ek-greet .g4 { animation-delay: 7.5s; font-family: 'Noto Sans Devanagari', sans-serif; }
.ek-foot-note { font-size: .8rem; color: var(--muted); margin-top: .6rem; }
@media (max-width: 900px) { .ek-hero { grid-template-columns: 1fr; } .ek-blob { width: 90vw; } }

/* ---------- steps ---------- */
.ek-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 2rem 0 2.4rem 0; }
.ek-step { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 1.15rem 1.2rem;
  transition: transform .35s var(--ease), box-shadow .35s var(--ease), border-color .35s; }
.ek-step:hover { transform: translateY(-6px); box-shadow: 0 16px 36px rgba(24,24,27,.08); border-color: #D7D2FF; }
.ek-step .n { font-size: .72rem; font-weight: 700; color: var(--accent); letter-spacing: .08em; }
.ek-step .t { font-weight: 600; color: var(--ink); margin: .3rem 0 .25rem 0; font-size: 1.02rem; }
.ek-step .d { font-size: .88rem; color: var(--muted); line-height: 1.5; }
@media (max-width: 900px) { .ek-steps { grid-template-columns: 1fr 1fr; } }

/* section labels */
.ek-label { font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  margin: .2rem 0 .6rem 0; }

/* cards (st.container(border=True)) */
[class*="st-key-ek-card"] { background: var(--card); border: 1px solid var(--line) !important;
  border-radius: 22px !important; box-shadow: 0 1px 2px rgba(0,0,0,.03), 0 10px 30px rgba(24,24,27,.05);
  animation: ek-up .7s var(--ease) both; }

/* uploaders */
[data-testid="stFileUploaderDropzone"] { background: var(--soft); border: 1.5px dashed #D6D2C6; border-radius: 16px;
  transition: border-color .25s, background .25s, transform .25s var(--ease); }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); background: #EEEDFB; transform: translateY(-2px); }

/* buttons */
.stButton > button, .stDownloadButton > button { border-radius: 999px !important; font-weight: 600 !important;
  padding: .6rem 1.4rem !important; border: 1px solid var(--line) !important;
  transition: transform .2s var(--ease), box-shadow .25s var(--ease), background .25s !important; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-2px); }
[data-testid="stBaseButton-primary"] { background: var(--ink) !important; color: #fff !important; border: none !important;
  box-shadow: 0 8px 22px rgba(24,24,27,.18); }
[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
  background: linear-gradient(90deg, #2A2A31, var(--accent)) !important; box-shadow: 0 10px 30px rgba(79,70,229,.35); }
[data-testid="stBaseButton-primary"]:disabled { background: #CFCCC3 !important; box-shadow: none; }

/* language pills */
[data-testid="stButtonGroup"] button { border-radius: 999px !important; transition: transform .2s var(--ease) !important; }
[data-testid="stButtonGroup"] button:hover { transform: translateY(-2px); }

/* metrics as stat tiles */
[data-testid="stMetric"] { background: var(--soft); border-radius: 16px; padding: .8rem 1rem;
  transition: transform .25s var(--ease); }
[data-testid="stMetric"]:hover { transform: translateY(-3px); }
[data-testid="stMetricLabel"] p { font-size: .76rem !important; color: var(--muted) !important; text-transform: uppercase;
  letter-spacing: .06em; font-weight: 600 !important; }
[data-testid="stMetricValue"] { font-size: 1.7rem !important; font-weight: 700; color: var(--ink); }

/* tabs (Streamlit 1.67 test id: stTab) */
[role="tablist"] { gap: .45rem; border-bottom: none !important; box-shadow: none !important; }
[data-testid="stTab"] { border-radius: 999px !important; padding: .4rem 1.15rem !important; background: var(--soft) !important;
  border: none !important; transition: background .25s, color .25s, transform .2s var(--ease); }
[data-testid="stTab"]:hover { transform: translateY(-2px); }
[data-testid="stTab"][aria-selected="true"] { background: var(--ink) !important; }
[data-testid="stTab"][aria-selected="true"] p { color: #fff !important; }
[data-testid="stTab"]::after, [data-testid="stTab"]::before { display: none !important; }

/* portrait phone videos: don't let them grow taller than ~60% of the screen */
[data-testid="stVideo"], video { max-height: 62vh; width: auto !important; max-width: 100%; display: block;
  margin: 0 auto; }

/* ---------- scroll-driven motion (pure CSS; Chrome/Edge). Other browsers: no motion, nothing breaks ---------- */
@keyframes ek-reveal { from { opacity: 0; transform: translateY(90px) scale(.92); filter: blur(6px); }
                       to { opacity: 1; transform: none; filter: none; } }
@keyframes ek-word { from { color: #CFCAC0; } to { color: var(--ink); } }
@keyframes ek-slide-r { from { transform: translateX(-28%); } to { transform: translateX(0%); } }
@keyframes ek-slide-l { from { transform: translateX(0%); } to { transform: translateX(-28%); } }
@keyframes ek-recede { from { opacity: 1; transform: none; } to { opacity: .4; transform: translateY(-24px) scale(.96); } }
@keyframes ek-parallax { to { translate: 0 260px; } }
@keyframes ek-progress { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.ek-progress { display: none; }
@supports (animation-timeline: view()) {
  /* things fade + rise in as they scroll into view */
  .ek-step, .ek-label, [class*="st-key-ek-card"], [data-testid="stMetric"],
  [data-testid="stDataFrame"], [data-testid="stTabs"], [data-testid="stExpander"], .ek-foot, .ek-chip {
    animation: ek-reveal linear both; animation-timeline: view(); animation-range: entry 0% cover 28%;
  }
  /* Streamlit scrolls an inner box (stMain), not the page: name its scroll timeline */
  [data-testid="stMain"] { scroll-timeline: --ekpage block; }
  /* the hero gently recedes as you scroll past it. Applied to the OUTER .ek-col wrappers only,
     so the inner load-in fade (.ek-a) and the greeting animation keep running. */
  .ek-hero > .ek-col { animation: ek-recede linear both; animation-timeline: view();
    animation-range: exit 10% exit 100%; }
  /* the glow drifts slower than the page (parallax), while still floating */
  .ek-blob { animation: ek-float 14s ease-in-out infinite, ek-parallax linear both;
    animation-timeline: auto, --ekpage; }
  /* story: the text stays pinned while each word lights up in turn */
  .ek-story { view-timeline: --ekstory block; }
  .ek-story .w { animation: ek-word linear both; animation-timeline: --ekstory; }
  /* greeting rows slide sideways with the scroll */
  .ek-marquee { view-timeline: --ekmarq block; }
  .ek-marquee .row.r { animation: ek-slide-r linear both; animation-timeline: --ekmarq; }
  .ek-marquee .row.l { animation: ek-slide-l linear both; animation-timeline: --ekmarq; }
  /* thin progress bar at the very top */
  .ek-progress { display: block; position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 999999;
    transform-origin: 0 50%; background: linear-gradient(90deg, var(--saffron), #E9572F, var(--accent));
    animation: ek-progress linear both; animation-timeline: --ekpage; }
}
@media (prefers-reduced-motion: reduce) { .ek-progress { display: none !important; } }

/* ---------- story section (below the form) ---------- */
.ek-story { position: relative; height: 210vh; margin-top: 4rem; }
.ek-story .pin { position: sticky; top: 18vh; }
.ek-story .eyebrow { font-size: .8rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 1rem; }
.ek-story .big { font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(2.2rem, 5vw, 4.6rem);
  line-height: 1.12; letter-spacing: -0.015em; max-width: 1100px; color: #CFCAC0; }
.ek-story .w { display: inline; }
.ek-story .w.hl { font-style: italic; }
.ek-marquee { overflow: hidden; padding: 2.5rem 0 1rem 0; margin: 0 -2.5vw; }
.ek-marquee .row { display: flex; gap: 3rem; white-space: nowrap; font-size: clamp(2.6rem, 6vw, 5.5rem);
  font-weight: 500; line-height: 1.25; }
.ek-marquee .row span { color: var(--ink); }
.ek-marquee .row span.o { color: transparent; -webkit-text-stroke: 1.2px #B9B3A6; }
.ek-marquee .row .ta { font-family: 'Noto Sans Tamil', sans-serif; }
.ek-marquee .row .bn { font-family: 'Noto Sans Bengali', sans-serif; }
.ek-marquee .row .dv { font-family: 'Noto Sans Devanagari', sans-serif; }

/* small print */
.ek-chip { display: inline-block; font-size: .8rem; color: var(--muted); background: var(--card); border: 1px solid var(--line);
  border-radius: 999px; padding: .28rem .75rem; margin: 0 .35rem .35rem 0; }
.ek-foot { color: var(--muted); font-size: .84rem; text-align: center; margin-top: 3.2rem; }
video { border-radius: 16px; }

/* title centred above each result video */
.ek-vhead { display: flex; align-items: baseline; justify-content: center; flex-wrap: wrap; gap: .5rem;
  margin: .2rem 0 .8rem 0; text-align: center; }
.ek-vname { font-size: 1.5rem; font-weight: 700; color: var(--ink, inherit); line-height: 1.2; }
.ek-ven { font-size: .95rem; font-weight: 600; color: var(--muted); }
.ek-vchip { font-size: .72rem; font-weight: 700; letter-spacing: .04em; padding: .2rem .6rem;
  border-radius: 999px; align-self: center; white-space: nowrap; }
.ek-chip-orig { background: rgba(127,127,127,.14); color: var(--muted); }
.ek-chip-ai { background: linear-gradient(90deg, var(--saffron), var(--accent)); color: #fff; }
/* download buttons sit under the dubbed video, as wide as it */
[class*="st-key-ek-dl"] { max-width: 420px; margin: .8rem auto 0 auto; }
</style>
"""


def _bars(n: int, seed: int) -> str:
    """Waveform bars with varied heights and delays (deterministic, no JS)."""
    out = []
    for i in range(n):
        h = 30 + ((i * 37 + seed * 11) % 70)          # 30..99 %
        delay = ((i * 53 + seed * 17) % 120) / 100    # 0..1.2 s
        out.append(f'<span style="height:{h}%;animation-delay:-{delay:.2f}s"></span>')
    return "".join(out)


HERO = f"""
<div class="ek-progress"></div>
<div class="ek-hero">
  <div class="ek-blob"></div>
  <div class="ek-col">
    <div class="ek-a d1"><span class="ek-badge"><span class="ek-dot"></span>Built on Gnani Prisma + Gnani voice cloning</span></div>
    <div class="ek-title ek-a d2">One voice.<br><em>Every Indian language.</em></div>
    <p class="ek-sub ek-a d3">Upload a short Hindi video. Ekswar dubs it into Tamil, Bengali or Marathi in
    <b>your own cloned voice</b>, fits every line to the original timing, and keeps your background music.</p>
  </div>
  <div class="ek-col"><div class="ek-a d4">
    <div class="ek-preview">
      <div class="hd"><span>Dub preview</span><span class="ek-live">Your voice</span></div>
      <div class="ek-row"><span class="ek-tag">HINDI</span><div class="ek-wave">{_bars(38, 1)}</div></div>
      <div class="ek-row"><span class="ek-tag">DUB</span><div class="ek-wave alt">{_bars(38, 2)}</div></div>
      <div class="ek-greet">
        <span class="g1">नमस्ते<small>HINDI</small></span>
        <span class="g2">வணக்கம்<small>TAMIL</small></span>
        <span class="g3">নমস্কার<small>BENGALI</small></span>
        <span class="g4">नमस्कार<small>MARATHI</small></span>
      </div>
      <div class="ek-foot-note">Same voice, same timing, new language.</div>
    </div>
  </div></div>
</div>
"""

STEPS = """
<div class="ek-steps">
  <div class="ek-step ek-a d3"><div class="n">01 · LISTEN</div><div class="t">Understand the Hindi</div>
    <div class="d">Separates voice from music and transcribes it with timestamps (Gnani Prisma).</div></div>
  <div class="ek-step ek-a d4"><div class="n">02 · TRANSLATE</div><div class="t">Natural, spoken lines</div>
    <div class="d">Each line translated with the full video as context, numbers as words.</div></div>
  <div class="ek-step ek-a d5"><div class="n">03 · YOUR VOICE</div><div class="t">Spoken by your clone</div>
    <div class="d">Every line is spoken in your cloned voice (Gnani vachana-vc-v1).</div></div>
  <div class="ek-step ek-a d6"><div class="n">04 · FIT THE TIMING</div><div class="t">The timing agent</div>
    <div class="d">Measures each line: fits, gently speeds up or slows down, or rewrites it shorter.</div></div>
</div>
"""

def _story(text: str, highlight: set[str]) -> str:
    """Big statement whose words light up one by one while the section scrolls past (CSS only)."""
    words = text.split()
    n = len(words)
    spans = []
    for i, w in enumerate(words):
        start = 4 + 82 * i / n
        end = start + 82 / n * 1.6
        cls = "w hl" if w.strip(".,") in highlight else "w"
        spans.append(f'<span class="{cls}" style="animation-range: contain {start:.1f}% contain {end:.1f}%">{w}</span>')
    return " ".join(spans)


_GREETS = [("नमस्ते", "dv"), ("வணக்கம்", "ta"), ("নমস্কার", "bn"), ("नमस्कार", "dv")]


def _marquee_row(outline_every: int, offset: int) -> str:
    items = (_GREETS * 4)[offset:offset + 12]
    return "".join(f'<span class="{c}{" o" if (i % outline_every == 0) else ""}">{g}</span>'
                   for i, (g, c) in enumerate(items))


STORY = f"""
<div class="ek-marquee">
  <div class="row r">{_marquee_row(2, 0)}</div>
  <div class="row l">{_marquee_row(3, 1)}</div>
</div>
<div class="ek-story">
  <div class="pin">
    <div class="eyebrow">Why Ekswar</div>
    <div class="big">{_story("Your words. Your voice. Now in Tamil, Bengali and Marathi, timed to every pause, with your music still playing underneath.", {"voice", "Tamil", "Bengali", "Marathi", "pause"})}</div>
  </div>
</div>
"""

FOOT = """<div class="ek-foot">Ekswar · Gnani Prisma (speech-to-text) · Gnani voice cloning · Google Gemini (translation)<br>
Every output is AI-dubbed. Ekswar adjusts timing, not lip movements.</div>"""
