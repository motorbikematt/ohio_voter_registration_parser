---
name: hgl-q1q2-interrogation-answered
description: Completed grill-me session findings and final drafted answers for HGL Q1 (workflow) and Q2 (pain point)
metadata:
  type: project
  originSessionId: 9e83e185-2149-4543-8488-96565b7280f8
---

## Session status (as of 2026-06-05)

**COMPLETE.** Both Q1 and Q2 interrogations finished and answers drafted. Ready for founder manual review and form submission before June 7, 2026 11:59 PM ET.

---

## Q1 — FINAL DRAFT

> Precinct captains use Precincts.info in the two to three days before a canvass session — the planning window when four questions need answers in sequence: Who are the most agreeable neighbors to approach first? How many of them are there? What do I say to each type of voter? And how do I structure my time?
>
> Most captains don't start with persuasion. They start with ally recruitment — finding neighbors who already share their values and might become helpers or co-organizers. Those voters are identifiable from election history: someone who has consistently pulled one party's primary ballot in low-turnout elections is the strongest loyalty signal in the public voter file. Today, extracting that signal means downloading a raw CSV from the county Board of Elections and parsing it by hand — a task most captains skip or get wrong using stale party data. Precincts.info does that translation automatically: a ranked cohort list, plain-language descriptions for newer captains, full statistical breakdowns for experienced ones, and an LLM coaching layer that prepares them for each conversation type.
>
> But the data layer is the foundation, not the ceiling. Precinct captains are elected officials — their names, precincts, and contact information are public record. Precincts.info will use that infrastructure to connect captains horizontally, enabling peer mentorship, shared strategy, and coordinated organizing that doesn't depend on top-down party communication. That network is what makes this structurally different from every other campaign tool: a self-organizing captain layer with the data to act and the connections to move together.
>
> The founder is a sitting precinct captain and Communications Committee member for the Montgomery County Democratic Party, with direct access to all 200 active captains. A dozen captains, multiple candidates, current officeholders, and the full county party leadership have already seen the product.

---

## Q2 — FINAL DRAFT

> A precinct captain knocks on a door. The voter file says this household voted Democrat in the last primary. The captain has a walk list — a paper printout from the county Board of Elections — and a set of talking points pulled from a party newsletter that arrived three days late and led with national messaging about issues this precinct doesn't talk about. The door opens. The voter is fearful, or angry, or ready to interrogate why the captain even supports this party. The captain has no context for what's behind that door, no framework for the conversation that's unfolding, and no one to call.
>
> That is the current state for most precinct captains in America.
>
> The walk list tells them a name and an address. It doesn't tell them whether this voter has pulled a Democratic ballot in every primary since 2004 or just once in 2024. It doesn't tell them whether their neighbors are disengaged renters facing a housing crisis or longtime homeowners who've voted straight-ticket for twenty years. The county party's email list is stale. The newsletters repeat the same national talking points so many times, and from so many overlapping sources, that anything locally relevant gets buried. VAN shows houses as Democrat that open with a Trump flag. Captains either improvise or give up.
>
> What most teams building in this space misunderstand: precinct captains are not campaign staff executing a turnout operation. They are elected community members trying to have authentic conversations with their neighbors — many of whom distrust the party, some of whom have already left it. The pain isn't a data formatting problem. It's an isolation problem. Captains operate without reliable information, without peer support, and without a feedback channel that anyone upstream actually reads.
>
> On June 5, 2026 — today — Montgomery County, Ohio swore in the largest incoming cohort of precinct captains in its history. Most are first-timers. Many ran because they were fed up with the party they just joined. They are about to discover, in real time, exactly how broken the infrastructure is. Precincts.info exists because the founder is one of them.

---

## Q1 — Workflow findings

### Primary usage trigger
**2–3 days before canvass** — not same-day cramming, not daily. Planning mode: deciding who to visit and how to approach them before committing to a session.

### The 4-step workflow (in order)
1. **Who are the safest, most agreeable neighbors to introduce myself to?** (targeting)
2. **How many are there?** (scope/volume)
3. **What am I going to say?** (messaging)
4. **How much time do I need, including walking and talking?** (routing/logistics)

### Step 1 — Targeting (safety-first, then persuadability)
- "Safe" targets = **Pure D loyal primary voters** — identifiable from election history (always pulled one party ballot in primaries)
- Goal is **network building first**: lock down agreeable neighbors, find allies and potential helpers
- Only after base is solidified do captains move to harder persuadability targets (UNC, crossover)
- Ohio primary ballots declare party; consistent primary participation + single-party ballot = the most reliable safety signal

### Current workaround (targeting)
- County Board of Elections website allows download of walklist filtered by recent ballot choice or full voting history
- Output is CSV or PDF — **not human-readable**; requires significant manual effort to determine strong partisans vs. mixed voters
- Most captains cannot or will not do this analysis; they either skip it or use VAN (which is demonstrably outdated — houses showing as D that are now Trump supporters)

### Product response
- Precincts.info translates the raw BoE/SWVF data into an actionable cohort list
- **Depth spectrum**: easy mode (conversational descriptions) → expert mode (full statistical demographic breakdowns)
- Different users engage at different levels; both are served

### Step 3 — Messaging
- Captains **do not wing it** — they fall back on their own genuine convictions + national/state party positions
- Local county party rarely shares localized talking points (inconsistent, last-minute, or absent entirely)
- Result: messaging is based on what the captain believes, not what their precinct's voters actually care about
- A rural Montgomery County captain defaults to Dayton-centric talking points; rural concerns go unaddressed
- **Graduated difficulty model**: easy/agreeable targets first → progressively harder targets → explicit conversation guidance for the hard ones → skip impossible/potentially unsafe entirely
- Pushback at the door is obvious early; the system is designed to build captain competence and confidence over time

### Step 4 — Routing/logistics (resolved)
- Time estimation is a **training and mentorship problem**, not a data problem — captains learn from experienced peers
- Walk order already partially solved by BoE walk list downloads; Precincts.info will replicate and improve with mapping UI (**planned**)
- **Captain-to-captain networking is a core value proposition** — captains are desperate for it; enables base control and holds party leadership accountable
- Precinct captains are elected officials; names/precincts are public record — network is derivable from data already being processed (**planned feature, not yet live**)

---

## Q2 — Pain point findings

### Three failure moments (all three apply)
- **Before canvass**: no reliable data, stale party contact lists, no local talking points, no peer to ask
- **At the door**: no context for who's behind it, no framework for unexpected conversations, no coaching
- **Reporting up**: experienced captains have nowhere to surface what they learned; feedback disappears

### New captain cohort (sworn in June 5, 2026 — today)
- Largest incoming cohort in Montgomery County history
- Elected May 5, sworn in June 5 — 30 days of discovering how broken the hidden structure is
- Many ran as outsiders and critics; distrusted the party before joining it
- Will feel the pain acutely at preparation and at-the-door stages
- Many positions still unfilled — voter apathy and ignorance left precincts dark

### Existing captain pain
- Email lists stale and outdated
- Multiple overlapping newsletters with repetitive national talking points — signal buried in noise
- No functional feedback loop upward; reports disappear
- Feel pain most acutely when trying to report up

### The origin story (founder's own activation)
- Founder was a **lifetime UNC**, not a fan of any party
- Got activated because a Team Kettering captain knocked on his door, read a yard sign as a friendly signal, and made a human connection
- Without that knock, he would never have gotten involved
- That captain had the right signal; the product is designed to make more of those moments possible at scale
- The corollary: people who could be activated never get knocked on because captains can't identify them; captains who could do the knocking never get recruited because there's no network to find them

### Contrarian market insight
- Most campaign tech assumes the unit of work is a persuasion contact or turnout call
- Precinct captains' actual unit of work: **find my people → build my network → extend outward to persuadable targets**
- The pain is an **isolation problem**, not a data formatting problem
- The party communicates *at* captains, not *with* them — top-down, high-volume, low-relevance, no feedback loop

### Traction
- ~12 precinct captains have seen the product since the primary
- Current and former candidates, current officeholders, and full Montgomery County Democratic Party leadership have seen it
- Founder has direct communications access to all 200 active captains via Communications Committee role

---

## Key contrarian insight

The captain's first goal is **relationship-building and ally recruitment**, not persuasion or GOTV. Most campaign tech assumes the unit of work is a persuasion or turnout contact. The precinct captain's actual unit of work is: find my people, build my network, then extend outward. The product must serve that sequence, not override it.

The founder's own activation story is the proof: a lifetime UNC got pulled into organizing because one captain knocked on the right door. The product scales that moment.
