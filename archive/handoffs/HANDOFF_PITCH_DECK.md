# HANDOFF — Precincts.info HGL Pitch Deck Build

**Written:** 2026-06-05
**From:** Claude Code CLI session (review-pbc-formation-handoff)
**To:** Fresh Claude Code CLI session with full repo access
**Deadline:** June 7, 2026 11:59 PM ET (HGL Open Call closes)

---

## 1. Objective

Populate a blank Google Slides presentation with 12 investor-grade slides for the HGL 2026 Agentic AI Open Call application.

The deck content is fully written and locked. The task is purely execution — get the content into slides, apply the design spec, make it shareable, and hand back a link for Q13 of the HGL form.

---

## 2. Key Files

| File | Purpose |
|------|---------|
| `D:\vibe\election-data\HGL_PITCH_DECK.md` | **Primary source** — all 12 slides with headlines, bullets, speaker notes, design spec |
| `D:\vibe\election-data\HGL_Q1Q2_INTERROGATION-answered.md` | Full application answers Q1–Q12 for context |
| `C:\Users\motorbikematt\.claude\projects\D--vibe-election-data\memory\project_hgl_application.md` | Application status memory |

---

## 3. Google Slides File

**Already created:**
- Title: `Precincts.info — HGL 2026 Pitch Deck`
- URL: `https://docs.google.com/presentation/d/1xQWlqW7RHceNXrL-NmKUZ6RQru_lT_uSQQgvrpo4luM/edit`
- Owner: motorbikematt@gmail.com
- Status: **Empty** — title only, no slides yet

---

## 4. Design Spec (from HGL_PITCH_DECK.md)

| Element | Value |
|---------|-------|
| Background | Off-white `#F8F7F4` |
| Primary color | Deep navy `#1B2A4A` |
| Accent | Warm gold `#C9A84C` |
| Headline font | Playfair Display |
| Body font | Inter |
| Format | 16:9 widescreen |
| Slides | 12 |

---

## 5. The 12 Slides (summary)

1. **Cover** — Precincts.info / Agentic organizing infrastructure for the last mile of American democracy
2. **The Problem** — Captain knocks on a door. They have no idea what's behind it.
3. **The Insight** — The real bottleneck isn't voters. It's the captain.
4. **The Contrarian Insight** — Captains don't start with persuasion. They start with ally recruitment.
5. **The Product (Live)** — 26 years of Ohio voter history. Every precinct. Every cohort. Right now.
6. **The Agentic Stack** — The captain doesn't manage the pipeline. They receive a briefing, open a map, and knock.
7. **Traction** — The largest incoming captain cohort in Montgomery County history was sworn in today.
8. **Go-to-Market** — We don't have to sell our way in. We have authorization.
9. **Competitive Landscape** — VAN is expensive, outdated, and hated. We're built to replace it.
10. **Business Model** — B2B SaaS. Parties and campaigns pay. Captains never do.
11. **The Ask** — $125,000. 18 months. First revenue by Q4 2026.
12. **Vision** — Not a product vision. A civic one.

Full content (headlines + bullets + speaker notes) in `HGL_PITCH_DECK.md`.

---

## 6. Build Approach Options

### Option A — Google Apps Script (recommended, zero setup)
1. Open the Google Slides URL in browser
2. Extensions → Apps Script
3. Paste and run the script from `D:\vibe\election-data\HGL_PITCH_DECK_APPSCRIPT.js`
4. All 12 slides populate automatically

### Option B — Google Slides API via Python
Requires OAuth credentials setup. Use `google-api-python-client`. More setup but fully automated from CLI.

### Option C — Manual
Open Google Slides, build slides by hand from `HGL_PITCH_DECK.md`. ~30-45 min.

---

## 7. After Building

1. Open the presentation and review all 12 slides
2. Apply navy/gold color scheme if not already applied by script
3. Share → "Anyone with the link can view"
4. Submit the shareable link for Q13 of the HGL form
5. Update `project_hgl_application.md` memory with Q13 status

---

## 8. HGL Form Submission Checklist

| Q | Status |
|---|--------|
| Q1 — Workflow | ✅ Ready to submit |
| Q2 — Pain point | ✅ Ready to submit |
| Q3 — Agentic AI | ✅ Ready to submit |
| Q4 — Metrics | ✅ Ready to submit |
| Q5 — Validation | ✅ Ready to submit |
| Q6 — GTM | ✅ Ready to submit |
| Q7 — Guardrails | ✅ Ready to submit |
| Q8 — Revenue | ✅ Ready to submit (zero) |
| Q9 — Traction | ✅ Ready to submit |
| Q10 — Business model | ✅ Ready to submit |
| Q11 — 2026 goals | ✅ Ready to submit |
| Q12 — Vision | ✅ Ready to submit |
| Q13 — Pitch deck | 🔴 Needs deck link |

**If Mel Rodriguez commits as co-founder/advisor before June 7:** Revise Q11 to add her title and role before submitting.
