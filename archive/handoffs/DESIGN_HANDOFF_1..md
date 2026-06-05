# Precincts.info V2 Redesign — Session Handoff

## Mission
Redesign the precincts.info dashboard (currently at https://precincts.info/, source: https://github.com/motorbikematt/ohio_voter_registration_parser) following the design direction in DESIGN_SYNTHESIS.md.

**Approach:** Option A — Fresh restart leveraging existing website infrastructure (index.html, charts.js, manifest.json, 65k+ data JSON files).

---

## Design Direction (from DESIGN_SYNTHESIS.md)

### Three-Part Layout
1. **Left Sidebar (200–300px):** Jurisdictional hierarchy navigation
   - Breadcrumb spine: Ohio → County → City/Township → Precinct
   - Shows child counts at each level
   - Click any breadcrumb to zoom out
   - Support for Electoral Districts tab (State House/Senate/Congressional)

2. **Center (Main Content):** Two-column data dashboard
   - **Left column:** Partisan composition (bar chart: D/R/UNC) + voter count
   - **Right column:** Demographics stack (scrollable: decade distribution, party×decade, generation distribution, party×generation, etc.)
   - Responsive: stacks on mobile

3. **Right Sidebar (300–400px):** Interactive geospatial map
   - Vector map of Ohio (GeoJSON) showing county boundaries
   - Currently selected county/city/precinct highlighted
   - Click-to-select jurisdictions
   - Color-coded by party affiliation

### Key Principles
- Spatial awareness (map always visible)
- Clear hierarchy (no ambiguity about jurisdiction relationships)
- Focused data (partisan + demographic context side-by-side)
- Comparability (easy to compare adjacent jurisdictions)
- Mobile-first (responsive stacking)

---

## Existing Codebase Foundation

### Live Website
- **URL:** https://precincts.info/
- **Source Repo:** https://github.com/motorbikematt/ohio_voter_registration_parser
- **Local Mirror:** D:\vibe\election-data\docs

### Key Files to Leverage

**index.html** (`election-data/docs/index.html`)
- Current dashboard HTML structure
- Uses Chart.js for rendering
- County dropdown, scope tabs (County/City/Precinct), geographic filter
- Already wired to load manifest.json + data files

**charts.js** (`election-data/docs/charts.js`, ~1570 lines)
- Modular chart rendering engine
- `ChartDashboard.init(config)` bootstraps dashboard from manifest
- Handles scope switching (county → city → precinct)
- URL state preservation (deep-linking support)
- Already supports doughnut + bar charts

**manifest.json** (`election-data/docs/manifest.json`)
- Index of all 88 counties + datasets
- Each county has multiple data files (party_affiliation.json, decade_distribution.json, etc.)
- chartConfig objects define labels, data, colors, chart type
- ~7554 lines, complete structure already defined

**Data Files** (`election-data/docs/data/`)
- 65k+ JSON files, one per geography per dataset type
- Example: `hamilton_party_affiliation.json` has doughnut chartConfig with 7-category party breakdown:
  - Pure R, UNC–Lashed R, Mixed–Active, Mixed–Lashed, UNC–No Primary, UNC–Lashed D, Pure D
- Updated as of 2026-05-09

### Data Pipeline (Python)
- **Backend:** `election-data/ohio_voter_pipeline.py` (main entry point)
- **Engine:** `election-data/voter_data_cleaner_v2.py` (Polars-based analysis)
- **Output:** Dashboard JSON + optional Excel workbooks
- Uses Ohio Secretary of State SWVF (7.9M voters, 26-year election history)
- Classifies voters into 7-cohort partisan spectrum

---

## What Needs to Be Built

### Phase 1: Layout & Navigation (Foundation)
- [ ] Create three-pane layout (left hierarchy sidebar | center data | right map)
- [ ] Build jurisdictional hierarchy tree component
  - Expandable/collapsible counties → cities/townships → precincts
  - Show child counts
  - Click to navigate + update URL state
- [ ] Add breadcrumb spine showing current path
- [ ] Integrate GeoJSON map (right sidebar)
  - Load Ohio county boundaries
  - Highlight selected county
  - Click-to-select jurisdictions
  - Color-code by party affiliation

### Phase 2: Data Integration (Use Existing Infrastructure)
- [ ] Load manifest.json + county list (reuse charts.js logic)
- [ ] Wire county/city/precinct selection to data file loading
- [ ] Render partisan composition chart (doughnut, 7 categories) in left column
- [ ] Render demographic charts (bar + grouped bar) in right column scrollable stack
- [ ] Preserve URL state (so deep links work: `?county=Hamilton&geo=precinct&precinct=CINCINNATI%201A`)

### Phase 3: Responsive & Polish
- [ ] Mobile: sidebars collapse to drawers, data stacks vertically
- [ ] Accessibility: ARIA labels, keyboard navigation, color contrast
- [ ] Loading states + error handling
- [ ] Optional: comparison mode (side-by-side view of 2 jurisdictions)

---

## Technical Constraints & Notes

### Data Source
- **Manifest URL:** `docs/manifest.json`
- **Data files:** `docs/data/{county}_{type}.json` (e.g., `hamilton_party_affiliation.json`)
- **Party Categories:** Always 7 (Pure R, UNC–Lashed R, Mixed–Active, Mixed–Lashed, UNC–No Primary, UNC–Lashed D, Pure D)
- **Geography Levels:** County, City/Township, Precinct, Electoral Districts (optional expansion)

### Chart Types in Use
- **Doughnut:** Party affiliation (7 categories)
- **Bar:** Decade distribution, generation distribution
- **Grouped bar:** Party by decade, party by generation
- **Table:** City/precinct summary (if applicable)

### GeoJSON for Map
- **Source:** Need to source Ohio boundary GeoJSON (county + optional districts)
- **Option 1:** Use TopoJSON from Natural Earth or US Census Bureau
- **Option 2:** Extract from election-data if GeoParquet file exists

### Existing URL Pattern (from charts.js)
```
?county=Hamilton&geo=county
?county=Hamilton&geo=city
?county=Hamilton&geo=precinct&precinct=CINCINNATI%201A
?geo=jurisdiction&jurType=cities&jurCounty=Hamilton&jurName=cincinnati
```
Preserve this pattern to maintain deep-linking.

---

## Files to Keep in Mind

**Ohio-Specific Nomenclature** (from CLAUDE.md)
- County-scoped jurisdictions (township, village, school district) use composite keys: `(COUNTY_NUMBER, name)` to avoid name collisions
- Display format: `{name} ({County} Co.)`
- Example: "Washington Township (Adams Co.)" vs "Washington Township (Ashland Co.)"

**Git Push Rule** (from CLAUDE.md)
- **NEVER** push `docs/data/` (~65k files) via GitHub MCP
- Data is too large; use manual `git push` from PowerShell
- Code changes (HTML, JS, config, markdown) can use MCP

---

## Success Criteria

✅ Three-pane layout renders correctly  
✅ Hierarchy navigation works (click breadcrumb to zoom out)  
✅ Map displays and responds to selection  
✅ Partisan chart renders for selected jurisdiction (7 categories)  
✅ Demographic charts stack and scroll in right column  
✅ URL state preserved (deep links work)  
✅ Mobile responsive (sidebars collapse, data stacks)  
✅ Matches DESIGN_SYNTHESIS.md visual direction  

---

## References

- **DESIGN_SYNTHESIS.md** — Full design direction + layout mockup
- **charts.js** — Existing chart rendering engine (study how it works)
- **manifest.json** — Data index + chartConfig definitions
- **Live site:** https://precincts.info/

Start by reading index.html + charts.js to understand how the current dashboard works, then redesign the layout to match DESIGN_SYNTHESIS.md while reusing the data infrastructure.
