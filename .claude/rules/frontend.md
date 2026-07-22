# CLAUDE.md — docs/ (Public Web Frontend)

Scope: the GitHub Pages dashboard served from this folder (`app.htm`, `assets/`, `charts.js`, `captain/`, `data/`). The root `index.htm` is the landing page (`assets/landing-map.js` + `assets/landing.css`, tokens-only — it does **not** load `v2.css`); any URL carrying a dashboard state param redirects from `index.htm` to `app.htm`. Auto-loaded by Claude Code CLI when editing files under `docs/`. For pipeline, schema, git, and file-editing rules see the project-root `CLAUDE.md`. This file is itself served by GitHub Pages — keep it free of secrets and PII (it contains only frontend conventions).

## UI & Design
* Conform to existing breakpoints — the 880px mobile-drawer breakpoint in `assets/v2.css` is the canonical switch; the captain layer's CSS matches it deliberately. Don't introduce a competing breakpoint.
* Route every server-supplied string through `esc()` before it reaches `innerHTML`. `esc()` is the single XSS trust boundary — keep it the only path. Re-render paths build markup through `buildTouchesHtml()` + `DOMParser`, not `insertAdjacentHTML`, so the escape funnel isn't bypassed.

## Captain layer (localhost decoration)
* `captain/captain-mode.js` decorates the public page; it boots only when `127.0.0.1:8000/health` responds and exits silently otherwise. The public deploy is **structurally inert** — no backend URL, no API key, no path to real voter data. Never commit a backend URL or token into the frontend; auth replaces inertness only once a real host exists.
* The roster/notes UI is precinct-scoped by design (one precinct, one tap). County/district routes exist in the API but are not exposed in the captain UI — that's a future "candidate viewer," not this surface.

## Data loading
* Charts read precomputed JSON from `data/` (flat-file pattern). Do **not** re-aggregate whole precinct files at runtime — that double-counted partial cross-county precincts (the Kettering over-count). City/jurisdiction views point at the precomputed `data/city/`-style files, which already carry the single correct totals.
* URL scope is `?level=<lvl>&id=<slug>&county=<county_slug>`; send the raw URL slug to the roster API (it normalizes slug-vs-slug), and read display names from the hierarchy row's `data-precinct-name`, not by un-slugging (lossy on hyphens).