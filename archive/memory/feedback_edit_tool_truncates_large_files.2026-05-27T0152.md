---
name: edit-tool-truncates-files-near-and-above-the-150-line-threshold
description: Observed silent truncation in two files this session; CLAUDE.md flag is correct but stricter than 150 lines in practice
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ab2db091-e6b0-4b4b-bca7-a546efec98ec
---

The Edit tool silently truncates the tail of files at or above CLAUDE.md's 150-line threshold. Observed twice in the 2026-05-26 narrative-planning session:

- `docs/assets/v2.js` (1446 lines): an Edit that added a `renderNarrative` block dropped 22 lines off the tail. Recovered via `git show HEAD:docs/assets/v2.js | sed -n '<range>p'`.
- `tools/narrative/templates.py` (321 lines after a regenerate via Python heredoc; the truncation occurred on an Edit that expanded `_format_jurisdiction_subject` by ~5 lines). The file's `metrics_hash` tail was cut mid-payload. Recovered by full rewrite via `Path.write_text(content)` inside a Python heredoc.

**Why:** The CLAUDE.md rule "Edit tool for files ≤150 lines; Python patch script for anything longer" is correct, and the failure mode is exactly what CLAUDE.md predicts ("a failed write looks identical to a successful one until parsing fails downstream"). The repeated incidents in this session prove the rule applies in practice, not just in theory; treat it as load-bearing.
**How to apply:** For any source file at or above ~150 lines — particularly `docs/assets/v2.js`, `voter_data_cleaner_v2.py`, `ohio_voter_pipeline.py`, `jurisdictional_groupings.py`, `tools/narrative/templates.py` — use the patch-script template in CLAUDE.md (small `assert count == 1` replacements) or full rewrite via `Path.write_text(content)` from inside a `python3 <<'PYEOF' … PYEOF` heredoc. Never use the Edit tool on these. After every patch, validate via `python3 -m py_compile <path>` (Python) or `node --check <path>` (JS). If a patch goes wrong, recovery path is `git show HEAD:<path>` to grab the lost region. Related: [[feedback_state_archive_rule]] (archive memory/CLAUDE.md before similar destructive ops).
