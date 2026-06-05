# HANDOFF — HGL Application: Q1 & Q2 Grill-Me Session

**Written:** 2026-06-04  
**From:** Claude Desktop Cowork session (Cowork UI — cannot be resumed; founder traveling)  
**To:** Fresh Claude Code CLI session with full repo access  
**Deadline:** June 7, 2026 11:59 PM ET (HGL Open Call closes)

---

## 1. Session Objective and Scope

The founder (Motorbike, precinct captain + technical founder of Precincts.info) is preparing answers for the **Higher Ground Labs 2026 Agentic AI Open Call** equity investment application.

**This session's scope:** Answer exactly two HGL form questions, and only these two:

> **Q1:** Briefly describe how your product fits into a customer's workflow. How will campaigns/organizations/users actually use this day-to-day?

> **Q2:** Describe what the pain point feels like on the ground for your customers today. What do your customers currently experience without your product? What do you understand about this problem or market that other teams building in this space don't?

Questions 3–13 from the HGL form are explicitly deferred to a subsequent session. **Do not address them here.**

**Method:** The `/grill-me` skill was invoked. The skill asks one bite-sized question at a time, offers a recommended answer as starting point, and lets the founder confirm/modify/debate. Walk down each branch of the design tree, resolve dependencies one by one, then draft the answer.

The session was interrupted before either answer was drafted. The resuming session must complete the interrogation and produce polished, investor-grade prose answers for both questions.

---

## 2. Source Materials

### Uploaded by founder (read at session start):
- `C:\Users\motorbikematt\AppData\Roaming\Claude\local-agent-mode-sessions\...\uploads\HGL_HANDOFF_BRIEF.md`  
  *(Not accessible in CLI session — content summarized in Section 4 below)*

### Key reference files in repo (read these first):
- `D:\vibe\election-data\HGL_Q1Q2_INTERROGATION.md` — working memory copy of interrogation findings (this is the primary source of truth for what's been established)
- `D:\vibe\election-data\CLAUDE.md` — project rules, file editing protocol, schema reference
- Memory index: load via `MEMORY.md` in the Cowork memory directory — specifically `project_hgl_q1q2_interrogation.md` and `project_precinct_captain_thesis.md`

### HGL application form:
- URL: https://forms.gle/uBuFXWJMcLWZf6Vj9  
- Deadline: June 7, 2026 11:59 PM ET

---

## 3. Full Q1 Interrogation Record

### Branch 1 — Primary usage trigger
**Question asked:** Is the primary usage trigger night-before cramming, or earlier?  
**Recommended answer:** Night-before cramming.  
**Founder's answer:** Neither — it's **2–3 days before canvass**. Planning mode, not cramming. The captain is deciding *who to visit* and *how to approach them* before committing to a session.  
**Decision:** Trigger = 2–3 days out. "Day-to-day" framing in Q1 is wrong; correct framing is episodic, canvass-cycle usage.

---

### Branch 2 — The 4-step workflow
**Question asked:** What is the first thing a captain tries to answer in that planning session — targeting or situational awareness?  
**Recommended answer:** "Who should I knock on?" (targeting first).  
**Founder's answer:** Confirmed targeting first, but provided the complete 4-step sequence:

1. **Who are the safest, most agreeable neighbors I need to introduce myself to?**
2. **How many are there?**
3. **What am I going to say?**
4. **How much time do I need to dedicate to this, including walking and talking?**

**Decision:** This 4-step sequence is the canonical structure for Q1's answer. Every product feature maps to one of these steps.

---

### Branch 3 — Step 1: What does "safe" mean?
**Question asked:** Is "safest, most agreeable" about emotional safety (avoiding hostile voters) or persuadability (targeting soft D / UNC), or both?  
**Recommended answer:** Both simultaneously.  
**Founder's answer:** **Safety first, persuadability second — and they are sequential, not simultaneous.**  
- First goal: lock down neighbors who are **already agreeable** — find friends and potential helpers. This is **network building**, not persuasion or GOTV.
- Only *after* the base is solidified does the captain move to harder persuadability targets.
**Decision:** The primary use case of the product is ally and helper recruitment, not voter persuasion. This is a contrarian insight vs. how most campaign tech frames the problem.

---

### Branch 4 — How "safe" voters are identified
**Question asked:** Is identifying agreeable neighbors based on personal knowledge (people they already know), or are captains trying to use party data to find friendlies they don't know personally?  
**Recommended answer:** Mostly personal knowledge + gut check against VAN.  
**Founder's answer:** More specific and more data-grounded than assumed:  
- In Ohio, primary voters **declare a party** by which ballot they pull.
- Voters who **always pull one party's ballot** in primaries = the most reliable "safe" signal. They invested time in low-turnout elections and always chose one side.
- This is **data-derivable from the voter file** — it's exactly what the cohort classifier produces (Pure D = always pulled D primary ballot).
- Captains *can* get a filtered walklist from the **county Board of Elections website**, but the output (CSV or PDF) is **not human-readable** — requires significant manual effort to identify strong partisans vs. mixed voters.
- VAN is an alternative but demonstrably outdated: houses flagged as Democrat sometimes turn out to be Trump supporters, which is "scary."

**Current workaround:** Download from BoE website → manually parse a non-human-readable export → most captains can't or won't do this, so they skip the analysis or rely on unreliable VAN data.

**Product response:** Precincts.info translates the raw SWVF/BoE data into an actionable cohort list. Depth spectrum: **easy mode** (plain conversational descriptions) → **expert mode** (full statistical demographic breakdowns). Both user types are served.

**Decision:** The BoE download workaround is the core before-state for Q1's workflow description. The product is the translation layer.

---

### Branch 5 — Step 3: Messaging
**Question asked:** Do captains wing it at the door, use party talking points, or something else?  
**Recommended answer:** They use party-provided materials if available, otherwise improvise.  
**Founder's answer:** Refined:  
- Captains **do not wing it** — they fall back on their own **genuine convictions** + **national/state party positions**.
- The local county party **rarely provides localized talking points** — communication is inconsistent, last-minute, or absent entirely.
- Result: messaging reflects what the captain personally believes, not what their specific precinct's voters actually care about.
- Example: a captain in a rural part of Montgomery County uses the same Dayton-centric talking points as someone in the city, even though rural neighbors have different concerns.

**Graduated difficulty model (confirmed by founder):**  
- System provides lists that start with **easy/agreeable** targets → progressively **harder** targets → explicit **conversation guidance** for the challenging ones → **skip** the impossible and potentially unsafe entirely.
- Pushback at the door is obvious immediately. The design philosophy is to build captain **competence and confidence** incrementally, not to throw them into hard conversations first.

**Decision:** The messaging gap is the bridge between Step 1 (targeting) and Step 3 (what to say). The product's content synthesis agent closes this gap by providing precinct-specific talking points, not generic party positions.

---

### Branch 6 — Step 4: Routing and logistics (UNRESOLVED — RESUME HERE)
**Question asked (last question before session paused):**  
*"When a captain is planning their session 2–3 days out, do they actively estimate how long it will take to knock their target list — or do they just pick a number of doors and go, without really knowing how long it'll run? And when they get it wrong, do they run out of time mid-route and quit early, or do they over-prepare and only hit half their list?"*

**Founder's answer:** NOT YET GIVEN. Session paused here.

**Resume instruction:** Ask this question first. After getting the answer, confirm whether route optimization (walk order, time estimates) is a current product capability, a planned feature, or out of scope. Then proceed to draft Q1.

---

## 4. Q2 Interrogation — NOT YET STARTED

All of Q2 is pending. After completing Step 4 of Q1 and drafting Q1's answer, begin Q2 interrogation.

**Q2 framing from the handoff brief:** The pain point interrogation should surface:
- What precinct captains are doing RIGHT NOW as workarounds
- Where party communication fails them most (infrequency? irrelevance? inconsistency?)
- What they improvise on their own and why
- The emotional/cognitive cost of inconsistent information (anxiety, paralysis, overconfidence in wrong assumptions)
- The specific moment they feel unprepared (before knocking? during the conversation? after?)

**Seed questions to use:**
1. "Tell me about a time a precinct captain had to handle a voter question and didn't know the answer. What happened? How did they feel? What would have helped?"
2. "What information are precinct captains currently trying to gather before canvass? Where do they find it? How long does that take? How confident do they feel about what they found?"
3. "If I gave you one precinct captain who's struggling, what's their biggest frustration right now?"

**Known Q2 material from handoff brief (use as interrogation starting points, not final answers):**
- VAN fear: "Houses that show as Democrat are sometimes Trump supporters and that's scary" — probe: scared of confrontation? embarrassment? physical safety?
- Party website is "garbage." Newsletters are inconsistent and often last-minute or expired.
- "I have no idea what issues matter most to my neighbors or how to talk about them"
- "I get dozens of newsletters a day — sometimes they say the same thing, sometimes slightly different. I don't know what to prioritize."
- "Precinct has 1,000 voters. Some live in houses, others in locked apartments I can't easily enter."
- "If I knew my precinct was 35% renters facing a housing crisis, I'd lead with that. But I have no way to know."
- The county party doesn't have enough precinct captains and may use that to their advantage to limit transparency.
- Many voters don't vote because they feel the party doesn't care about them.
- Democrats have voted Trump because they feel betrayed by local party/politicians.
- Rural Montgomery County captain: "all I ever hear about is Dayton Dayton Dayton."

---

## 5. Files Created/Modified This Session

| File | Action | Notes |
|------|--------|-------|
| `D:\vibe\election-data\HGL_Q1Q2_INTERROGATION.md` | Created | Working copy of interrogation findings; primary source of truth for resuming session |
| `D:\vibe\election-data\docs\archive\handoffs\HANDOFF_PBC_FORMATION.md` | Created | This file |
| `...\memory\project_hgl_q1q2_interrogation.md` | Created | Cowork auto-memory; inaccessible from CLI but content mirrored in HGL_Q1Q2_INTERROGATION.md |
| `...\memory\MEMORY.md` | Updated | Added index entry for project_hgl_q1q2_interrogation.md |

No code files were modified. No pipeline was run. No git push was made.

---

## 6. Current State

| Item | Status |
|------|--------|
| Q1 — Usage trigger | ✅ Resolved: 2–3 days before canvass |
| Q1 — 4-step workflow | ✅ Resolved: who/how many/what to say/how long |
| Q1 — Step 1 targeting (safety-first) | ✅ Resolved |
| Q1 — Step 1 current workaround (BoE CSV) | ✅ Resolved |
| Q1 — Step 1 product response | ✅ Resolved |
| Q1 — Step 3 messaging gap | ✅ Resolved |
| Q1 — Step 3 graduated difficulty model | ✅ Resolved |
| Q1 — Step 4 routing/logistics | 🔴 Unresolved — last question asked, no answer given |
| Q1 — Draft answer | 🔴 Not written |
| Q2 — Full interrogation | 🔴 Not started |
| Q2 — Draft answer | 🔴 Not written |

---

## 7. Exact Next Actions (in order)

1. **Read** `D:\vibe\election-data\HGL_Q1Q2_INTERROGATION.md` to orient on session state.
2. **Ask Step 4 question** (routing/logistics — exact text in Section 3, Branch 6 above). Get founder's answer.
3. **Confirm** whether route optimization is current, planned, or out of scope for the product.
4. **Draft Q1 answer** — synthesize all 4 steps into 150–250 word investor-grade prose. Framing: episodic use, canvass-cycle trigger, 4-step workflow, product maps to each step. Do not use "day-to-day."
5. **Show draft Q1 to founder** for review and revision.
6. **Begin Q2 interrogation** — use seed questions in Section 4. Ask one at a time. Establish the before-state (workarounds, cognitive cost, moment of failure) before drafting.
7. **Draft Q2 answer** — synthesize into 200–300 word prose. Framing: concrete pain moments, workaround specifics, what the market misunderstands about precinct captains.
8. **Show draft Q2 to founder** for review and revision.
9. **Finalize both answers** and confirm ready for form submission.
10. **Update** `HGL_Q1Q2_INTERROGATION.md` with Q2 findings and final answer drafts.

---

## 8. Open Questions and Unresolved Dependencies

- **Step 4 routing answer** — the session paused on this. It determines whether the Q1 answer mentions time/logistics as a product capability or frames it as a user-solved problem.
- **Q2 VAN fear flavor** — "scary" needs to be precisely defined (confrontation? embarrassment? physical safety?). This is the most emotionally resonant sentence in the application and needs to be specific.
- **Does the county party deliberately limit precinct captain access?** — the handoff brief mentions the party may use low captain count to avoid internal dissent. Confirm whether to include this in Q2 (it's politically sensitive but potentially the sharpest market insight).
- **What does "impossible and potentially unsafe" mean concretely?** — the graduated difficulty model skips these. Are they Pure R loyalists? Physically aggressive residents? Known hostile households? This needs definition before Q2 is drafted, as it speaks to guardrails (a separate HGL question but may surface in Q2 framing).
- **No revenue, no formal customers yet** — founder has shown to 9 precinct captains + 4 candidates + 2 city council members. Not paying customers. Q1/Q2 answers must be grounded but not overclaim adoption. Stay in "practitioner-validated, not yet commercialized" framing.

---

## 9. Key Contrarian Insight (Do Not Lose This)

The captain's **first goal is ally recruitment and network building**, not voter persuasion or GOTV. Most campaign tech assumes the unit of work is a persuasion contact or turnout call. The precinct captain's actual unit of work is: **find my people → build my network → extend outward to persuadable targets**. The product must serve that sequence. This is the sharpest differentiation from every other tool in the market and should be the spine of both Q1 and Q2 answers.
