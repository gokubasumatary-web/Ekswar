# Stage 12: README, demo, submission

**Status:** 🔄 Documents written (2026-11-08) · ⏸ waiting on the team (contributions, demo recording, post, key rotation, merge)
**Deadline:** Nov 10, 2026, 11:59 PM IST

## 1. What was written

| File | Audience | Content |
|---|---|---|
| [README.md](../../README.md) | Judges, developers | What/why, timing agent, **architecture diagram (Mermaid, renders on GitHub)**, tools table, real results, honest limits, how to run, layout, team, future work |
| [docs/SUBMISSION.md](../SUBMISSION.md) | Competition form | Problem, solution, timing agent, **each Gnani model and what it does**, results, engineering, limits, contributions, links |
| [docs/DEMO_SCRIPT.md](../DEMO_SCRIPT.md) | The team | 2–3 min scene-by-scene script with what to say and what to show |
| [docs/LINKEDIN_POST.md](../LINKEDIN_POST.md) | Public | LinkedIn and X drafts with the required hashtags |
| [HANDOFF.md](../../HANDOFF.md) | Ananya | One-page project guide |

All numbers come from the real 2-minute run (`outputs/runs/ekswar_demo/report.json`). Nothing unmeasured is claimed (e.g. Gnani credits per video are "not measured").

## 2. Honesty choices

- "No lip-sync" stated in README, write-up, page, post and demo script.
- QA described as **intelligibility**, not native quality; translations "not yet reviewed by native speakers".
- Timbre v3.0 listed as a fallback that **was not needed**, not as "used".
- **Team contributions left as placeholders.** Only the team can state them truthfully.
- AI assistance disclosed: "Development was assisted by Claude Code."

## 3. ✅ Final checklist (team)

- [ ] **Fill in contributions** in `README.md` §Team and `docs/SUBMISSION.md` §8 (true, specific)
- [ ] **Regenerate both API keys** (Gnani dashboard + Google AI Studio); put the new ones only in `.env`; re-run `python -m src.config`
- [ ] Optional: a native Tamil/Bengali speaker checks 3–4 lines; update the limits if they do
- [ ] **Record the demo** (`docs/DEMO_SCRIPT.md`); upload (YouTube unlisted / Drive with view access)
- [ ] **Post on LinkedIn/X** (public, #GnaniAI #GreatIndianAIInternshipChallenge); put the links in `docs/SUBMISSION.md` §9
- [ ] Check Gnani credit balance once more (optional: report credits used)
- [ ] **Merge `feature` → `main`** and push (only when the team says so)
- [ ] **Submit:** demo video + written explanation (SUBMISSION.md) + Gnani models used + contributions + post link
