# CLAUDE.md – Ohio Voter Registration Parser

## Project Overview

Data processing pipeline to convert historical and current raw voter registration data into meaningful presentations and insights for Civic Tech startup & consulting business development. Prototype starts with Montgomery County’s boundaries, but different subregions per source data must be organized and visualized, including precincts, school, city, congressional districts etc. Once the interface is resolved, we replicate across all Ohio counties statewide analysis. Subsequent work includes on unregistered resident matching (for GOTV initiatives) and GIS visualization.

## Data Processing Philosophy

- **Preserve traceability**: all data should be easily traceable to source database, including column and row labels, file titles and Ohio BoE publication timestamps
- **Speed is paramount**: Vectorized operations, batch processing, efficient I/O for very large future datasets
- **Tool selection**: Python for heavy lifting (speed, flexibility); Excel for exploratory analysis and stakeholder deliverables and chart beautification.  
- **Output formats**: Raw CSV/Parquet for analysis pipelines; Excel with charts/summaries for stakeholders; interactive maps/dashboards for deep dives  
- **PII and Bandwidth protection**: never upload raw data to GitHub. Keep paths relative to ensure interoperability across different machinces & users

## UX/UI Considerations

- **Hosting:** Initially [github.io](http://github.io). Website data auto-updates on Push.  
- **Interface:** Dark and Light mode switching on all presentable data. Menus should be hidable to not interfere with chart visualization, especially on mobile. All charts must have a Full-screen option for screencaps or printing. Source data timestamps should be associated with all presented data for timeliness.

## Geographic & Temporal Scope

- **Current phase**: Montgomery County (prototype validation)  
- **Phase 2:** Deep dive into countywide jurisdictions & subregions (precincts, wards, school boards, city districts, etc) for every county  
- **Phase 3**: Full Ohio statewide and transcounty regions dataset, including state and federal districts, zip codes.  
- **Phase 4:** Attempts to ascertain non-voters based on other databases (property records, census, etc)  
- **Phase 5:** Comparisons across time, different elections for the same subregions, as applicable.

## Key Deliverables

1. Precinct-level demographic and registration trend analysis tables  
2. GIS-enabled visualizations (choropleth maps, heatmaps, density plots)  
3. Executive summaries with actionable insights for stakeholders  
4. Unregistered resident identification and matching algorithms

## File Editing Rules

For files >300 lines, edit via Python script (`encoding='utf-8'`). To prevent exact-match assertion failures, target small, unique code blocks (<10 lines) for the `old_string`. Assert `src.count(old_string) == 1` before replacing. Print only the replaced line numbers. Do not output diffs.

## How to Work With Me

- **Show plans before writing code:** We want to avoid repeating work  
- **Do over explain**: Once plan is approved, run tools and skip narration unless explanation is needed for a decision. Explain bugs to me as if I were a novice.  
- **Be direct**: Assert positions; flag uncertainty only for facts postdating May 2025 knowledge  
- **Cite everything**: All factual claims need active DOI or URL  
- **End cleanly**: After task completion, surface unresolved dependencies, unconfirmed assumptions, or observations that would change the next action  
- **No excessive formatting**: Brief prose by default; headers/lists as needed

## File Locations

- **Raw source data**: `D:\vibe\election-data\source\`  
- **Working/intermediate files**: `D:\vibe\election-data(1)\`  
- **Final deliverables** (user-visible): `D:\vibe\election-data (1)\`

## Data Schema Reference

Column definitions and data mapping: [https://docs.google.com/spreadsheets/d/1VKeXthMF658x-YKcRU4Gv5T2l8pLGJQdOmhZxd6pPcA/edit](https://docs.google.com/spreadsheets/d/1VKeXthMF658x-YKcRU4Gv5T2l8pLGJQdOmhZxd6pPcA/edit)

## Known Project State

- Prototype focused on Montgomery County  
- Exploring fastest methods for raw→insight conversion  
- Data will need to be presented per subregion, starting with precincts.  
- GIS visualization planned as core output type for all subregions

---

*Last updated: 2026-05-02*  
