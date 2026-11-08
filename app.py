"""Ekswar web page (Streamlit). Run:  .venv\\Scripts\\streamlit run app.py

The page only collects inputs, calls src.pipeline.run() (the same function as cli.py)
and shows the results. No dubbing logic lives here. Styling: src/ui_style.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit as st

import importlib

from src import ui_style
from src.config import OUTPUT_DIR, SUPPORTED_TARGETS

# Streamlit re-runs app.py on every change but keeps imported modules cached; reload the
# (tiny) style module so design edits show up on refresh without restarting the server.
ui_style = importlib.reload(ui_style)
CSS, FOOT, HERO, STEPS, STORY = ui_style.CSS, ui_style.FOOT, ui_style.HERO, ui_style.STEPS, ui_style.STORY

AI_LABEL = "AI-dubbed · voice cloned with consent · timing adjusted automatically · no lip-sync"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
STATUS_LABEL = {"fit": "Fit", "sped_up": "Sped up", "rewritten": "Rewritten",
                "flagged": "Flagged", "failed": "Failed"}


def save_upload(uploaded, kind: str) -> Path:
    """Store an upload under its content hash, so the same file always gets the same path
    (and the pipeline cache is reused instead of spending credits again)."""
    data = uploaded.getvalue()
    digest = hashlib.sha256(data).hexdigest()[:16]
    suffix = Path(uploaded.name).suffix.lower() or ".bin"
    path = UPLOAD_DIR / kind / f"{kind}_{digest}{suffix}"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path


def line_table(rows: list[dict]) -> list[dict]:
    """Rows for the on-page table (pure, tested)."""
    table = []
    for r in rows:
        tempo = r.get("tempo") or 1.0
        status = STATUS_LABEL.get(r["status"], r["status"])
        if r.get("expanded"):
            status = f"{status} · fuller line" + (f" · slowed {tempo:.2f}×" if tempo < 1.0 else "")
        elif r["status"] == "fit" and tempo < 1.0:
            status = f"Fit · slowed {tempo:.2f}×"
        elif tempo > 1.0:
            status = f"{status} · {tempo:.2f}×"
        qa = r.get("qa_similarity")
        table.append({
            "Time": f"{r['start']:.1f}–{r['end']:.1f}s",
            "Hindi (original)": r["original"],
            "Dub": r.get("final_text") or r.get("translation") or "",
            "Timing": status,
            "QA": "not checked" if qa is None and r["status"] != "failed" else
                  ("—" if qa is None else f"{qa:.0f}%" + (" ⚠" if r.get("qa_flag") else "")),
        })
    return table


def can_run(video, ref, langs, consent) -> tuple[bool, str]:
    """Whether the Dub button is enabled, and why not (pure, tested)."""
    if video is None:
        return False, "Upload a Hindi video."
    if ref is None:
        return False, "Upload a 5–30 s sample of your voice."
    if not langs:
        return False, "Pick at least one language."
    if not consent:
        return False, "Tick the consent box: it must be your voice, or you must have permission."
    return True, ""


def show_results(res) -> None:
    st.markdown('<div class="ek-label">Your dubs</div>', unsafe_allow_html=True)
    langs = list(res["langs"].items())
    tabs = st.tabs([f"{lr['report']['language_name']}" for _, lr in langs])
    for tab, (lang, lr) in zip(tabs, langs):
        rep = lr["report"]
        with tab:
            with st.container(border=True, key=f"ek-card-{lang}"):
                c1, c2 = st.columns(2, gap="large")
                with c1:
                    st.markdown('<div class="ek-label">Original · Hindi</div>', unsafe_allow_html=True)
                    st.video(res["video"])
                with c2:
                    st.markdown(f'<div class="ek-label">AI-dubbed · {rep["language_name"]}</div>',
                                unsafe_allow_html=True)
                    st.video(lr["mp4"])
                d1, d2, _ = st.columns([1, 1, 2])
                d1.download_button("Download MP4", Path(lr["mp4"]).read_bytes(), file_name=Path(lr["mp4"]).name,
                                   mime="video/mp4", key=f"mp4-{lang}", width="stretch")
                d2.download_button("Download subtitles", Path(lr["srt"]).read_bytes(),
                                   file_name=Path(lr["srt"]).name, mime="text/plain", key=f"srt-{lang}",
                                   width="stretch")

            st.markdown('<div class="ek-label" style="margin-top:1.4rem">What the timing agent did</div>',
                        unsafe_allow_html=True)
            m = st.columns(7)
            for col, (label, key) in zip(m, [("Lines", "total_units"), ("Fit", "fit"), ("Fuller", "expanded"),
                                             ("Slowed", "slowed"), ("Sped up", "sped_up"),
                                             ("Rewritten", "rewritten"), ("Failed", "failed")]):
                col.metric(label, rep.get(key, 0))
            if rep.get("speech_coverage") is not None:
                st.caption(f"Your dubbed voice fills {rep['speech_coverage']:.0%} of your original speaking time.")
            avg = rep["average_similarity"]
            st.markdown(
                f'<span class="ek-chip">Quality check: {avg}% average similarity</span>'
                f'<span class="ek-chip">{rep["qa_flags"]} flagged</span>'
                f'<span class="ek-chip">{rep["qa_not_checked"]} not checked</span>'
                f'<span class="ek-chip">{rep["processing_seconds"]} s</span>', unsafe_allow_html=True)
            st.caption("Gnani listens to every dubbed line and compares it with the intended text. "
                       "A flag is a warning, not a verdict.")
            st.dataframe(line_table(lr["units"]), width="stretch", hide_index=True)
    with st.expander("Full report (report.json)"):
        st.json(json.loads(Path(res["report"]).read_text(encoding="utf-8")))


def main() -> None:
    st.set_page_config(page_title="Ekswar · One voice, every Indian language", page_icon="🎙️",
                       layout="wide")
    # st.html (not st.markdown): raw HTML/CSS, so markdown can't mangle `*` selectors or indentation
    st.html(CSS)
    st.html(HERO)
    st.caption(AI_LABEL)
    st.html(STEPS)

    st.markdown('<div class="ek-label">Create a dub</div>', unsafe_allow_html=True)
    with st.container(border=True, key="ek-card-form"):  # key -> CSS class st-key-ek-card-form
        left, right = st.columns(2, gap="large")
        with left:
            video = st.file_uploader("**1 · Hindi video** — one speaker, 3 minutes or less",
                                     type=["mp4", "mov", "mkv", "webm"])
        with right:
            ref = st.file_uploader("**2 · Your voice** — 5–30 s of clean speech",
                                   type=["wav", "mp3", "m4a", "ogg", "mpeg"])
        langs = st.pills("**3 · Languages**", list(SUPPORTED_TARGETS), selection_mode="multi",
                         default=["ta-IN"], format_func=lambda c: SUPPORTED_TARGETS[c]) or []
        o1, o2 = st.columns([3, 1], vertical_alignment="bottom")
        names = o1.text_input(
            "Names in your video (optional)",
            placeholder="e.g. गुथल बसुमतारी (Guthal Basumatary), पूजा (Pooja)",
            help=("Names of people, places or brands that are spoken in the video. Ekswar keeps them as "
                  "names: it does not translate their meaning (e.g. 'Pooja' stays Pooja, not 'worship') and "
                  "spells them correctly in Tamil, Bengali or Marathi, even if the speech recognition misheard "
                  "them. Several names: separate them with commas. Tip: write the name in Hindi with the "
                  "English spelling in brackets. Leave empty if there are no names."))
        o1.caption("Type the names spoken in your video so they are **not translated** and are **spelled "
                   "correctly**. Several names → separate with commas ( , ). No names → leave it empty. "
                   "The grey text is only an example.")
        no_music = o2.toggle("No background music", help="Skip music separation (faster)")
        consent = st.checkbox("This is my voice, or I have permission to clone it.")

        ok, why = can_run(video, ref, langs, consent)
        b1, b2 = st.columns([1, 3], vertical_alignment="center")
        clicked = b1.button("Dub my video", type="primary", disabled=not ok, width="stretch")
        if not ok:
            with b2:
                st.info(why)

    if clicked:
        from src.gnani import GnaniClient
        from src.llm import LLM
        from src.pipeline import InputError, run
        from src.retry import FatalAPIError

        video_path, ref_path = save_upload(video, "video"), save_upload(ref, "voice")
        log_lines: list[str] = []
        with st.status("Dubbing your video…", expanded=True) as status:
            bar = st.progress(0.0, text="Starting…")

            def progress(i, n, msg):
                bar.progress(i / n, text=f"Step {i} of {n} · {msg}")
                status.update(label=f"{msg}…")

            try:
                result = run(video_path, langs, ref_path, gnani=GnaniClient(), llm=LLM(),
                             names=[n.strip() for n in names.split(",") if n.strip()], no_music=no_music,
                             progress=progress, log=log_lines.append)
            except InputError as e:
                status.update(label="Input problem", state="error")
                st.error(str(e))
                return
            except FatalAPIError as e:
                status.update(label="Stopped", state="error")
                st.error(str(e))
                return
            except Exception as e:  # show, don't hide
                status.update(label="Something went wrong", state="error")
                st.error(str(e))
                st.code("\n".join(log_lines[-200:]) or "(no log)")
                return
            bar.progress(1.0, text="Finished")
            status.update(label="Done · " + AI_LABEL, state="complete", expanded=False)
        with st.expander("Details (log)"):
            st.code("\n".join(log_lines[-200:]) or "(no log)")
        st.session_state["result"] = {
            "video": str(video_path), "report": str(result.report_path),
            "langs": {l: {"mp4": str(r.mp4), "srt": str(r.srt), "units": r.units, "report": r.report}
                      for l, r in result.langs.items()},
        }
    if "result" in st.session_state:
        show_results(st.session_state["result"])

    st.html(STORY)
    st.html(FOOT)


if __name__ == "__main__":
    main()
