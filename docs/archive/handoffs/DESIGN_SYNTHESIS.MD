# Precincts.info Menu Redesign — Design Synthesis

## Overview
Hybrid approach combining interactive discovery (V1 strengths) with clear jurisdictional hierarchy (V2 strengths).

---

## Element 1: Interactive Geospatial Sidebar
**Source:** V1 Tier Segmented + Typeahead  
**Feature:** Mini-map in top corner showing selected jurisdiction boundaries

### Purpose
- Real-time visual feedback of geographic selection
- Immediate spatial context ("where am I in Ohio?")
- Reduces cognitive load of abstract county/precinct names

### Implementation Notes
- Map type: Vector tiles (GeoJSON/TopoJSON) showing:
  - All 88 county boundaries (color-coded by party affiliation or engagement)
  - Currently selected county/city highlighted
  - Hover states showing adjacent jurisdictions
- Position: Right sidebar, sticky, 300–400px wide
- Interaction: Click on map to select jurisdiction, or use search/hierarchy below
- Data source: Ohio state geographic boundaries (GeoJSON from election-data folder if available)

---

## Element 2: Two-Column Data Dashboard
**Source:** V1 Tier Segmented + Typeahead  
**Feature:** Side-by-side presentation of breakdowns

### Left Column: Partisan Composition
- Large bar chart (D / R / UNC percentages)
- Color-coded to match Ohio political identity
- Voter count total below

### Right Column: Demographics & Trends
- Scrollable stack of breakdowns:
  - Voter age distribution (by decade or generation)
  - Party affiliation by age cohort
  - Turnout trends (if data available)
  - Eligible voter count vs. registered

### Layout
- Grid: `1fr 1fr` gap at medium+ breakpoints
- Stacks vertically on mobile
- Charts remain interactive (hover, click for detail)

---

## Element 3: Jurisdictional Hierarchy Navigation
**Source:** V2 Breadcrumb Spine  
**Feature:** Clear state → county → city/township → precinct navigation

### Hierarchy (Ohio-Specific Nomenclature)
```
State of Ohio
  ├── 88 Counties
  │   ├── ~1,200 Cities & Villages
  │   ├── ~1,300 Townships
  │   └── ~9,100 Precincts
  ├── 33 State Senate Districts
  ├── 99 State House Districts
  ├── 16 Congressional Districts
  └── 614 School Districts (various types)
```

### Navigation Metaphor
**Breadcrumb spine** (not classic crumbs, but a vertical/horizontal hierarchy tree):
```
Ohio (Statewide)
  └─ Hamilton County
       ├─ Cincinnati (city)
       │    └─ Ward 1
       │         └─ Precinct 101
       ├─ Norwood (city)
       └─ Sharonville (village)
```

### Interaction
- Click any level to "zoom out" to that jurisdiction
- Shows count of children at each level (e.g., "3 cities, 12 townships, 47 precincts")
- Selected path highlighted
- Shift context: can also navigate by Electoral Districts (State House / Senate / Congressional)

---

## Combined Layout Concept
```
┌─────────────────────────────────────────────┐
│ Precincts.info › Ohio                       │
├────────────┬──────────────────────────────────┤
│            │                                  │
│ Hierarchy  │                                  │
│ Breadcrumb │         Two-Column Dashboard    │
│ Spine      │                                  │
│            │  Left: Partisan Bars             │
│ ┌─────────┐│  Right: Demographics Stack      │
│ │ Ohio    ││                                  │
│ │ > Ham.  ││                                  │
│ │ > Cin.  ││                                  │
│ │ > Ward 1││                                  │
│ │ > Pre101││                                  │
│ └─────────┘│                                  │
│            │                                  │
│ ┌─────────┐│                                  │
│ │ Map     ││  (Recents, filters, export)     │
│ │         ││                                  │
│ └─────────┘│                                  │
└────────────┴──────────────────────────────────┘
```

---

## Key Design Principles

1. **Spatial Awareness:** Map always visible so user knows "where" they are in Ohio
2. **Clear Hierarchy:** Breadcrumb spine removes ambiguity about jurisdiction relationships
3. **Focused Data:** Two-column layout prioritizes partisan + demographic context
4. **Comparability:** Easy to compare adjacent or related jurisdictions
5. **Mobile-First:** Hierarchy can collapse; map can be drawer; data stacks vertically

---

## Next Steps for Design Session
- [ ] Confirm hierarchy structure (especially ward/precinct nomenclature)
- [ ] Source GeoJSON for Ohio county + district boundaries
- [ ] Define color palette (D/R/UNC + accessibility)
- [ ] Sketch interaction flows (selection, breadcrumb updates, map interaction)
- [ ] Determine which Electoral Districts to show (all three, or user choice?)
- [ ] Plan data refresh cadence (data updates every 2 weeks per manifest)

---

## Nomenclature Reference (Ohio-Specific)
- **County:** 88 total; traditional geographic divisions
- **City/Village:** Municipal incorporated areas
- **Township:** Rural/semi-rural unincorporated areas (overlaps with some cities)
- **Ward:** City subdivision (used in larger cities like Columbus, Cleveland, Cincinnati)
- **Precinct:** Smallest voting unit; ~9,100 total statewide
- **State Senate District:** 33 districts, multi-county in some cases
- **State House District:** 99 districts, mostly single-county
- **Congressional District:** 16 districts (federal), multi-county
- **School District:** Multiple types (local, exempted village, city); ~614 total
