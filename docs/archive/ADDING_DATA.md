# Adding or Updating Chart Data

The dashboard is driven entirely by JSON files. You never need to edit `index.html`.

---

## Updating an existing chart

1. Edit the relevant file in `docs/data/`
2. Commit and push
3. Done — the dashboard fetches fresh data on every page load

---

## Adding a new chart

**Step 1.** Create a JSON file in `docs/data/` (see formats below).

**Step 2.** Add one entry to `docs/manifest.json` under `"sections"`:

```json
{
  "id":          "unique-slug-no-spaces",
  "title":       "Display Title",
  "navLabel":    "Short Nav Label",
  "description": "One sentence describing the chart.",
  "county":      "Montgomery",
  "geography":   "county",
  "dataUrl":     "data/your_file.json"
}
```

Valid `geography` values: `county`, `city`, `precinct`, `congressional`, `all`

---

## JSON formats

### Bar / Line / Pie / Doughnut

```json
{
  "title":     "Chart Title",
  "county":    "Montgomery",
  "geography": "county",
  "type":      "bar",
  "updated":   "YYYY-MM-DD",
  "chartConfig": {
    "labels": ["Label A", "Label B"],
    "datasets": [
      {
        "label":           "Series Name",
        "data":            [100, 200],
        "backgroundColor": ["#3b82f6", "#ef4444"]
      }
    ]
  }
}
```

For stacked bars, add:
```json
"chartOptions": {
  "scales": { "x": { "stacked": true }, "y": { "stacked": true } }
}
```

### Table

```json
{
  "title":     "Table Title",
  "county":    "Montgomery",
  "geography": "precinct",
  "type":      "table",
  "updated":   "YYYY-MM-DD",
  "headers": ["Column A", "Column B"],
  "rows": [
    ["Row 1 A", "Row 1 B"],
    ["Row 2 A", "Row 2 B"]
  ]
}
```

---

## Embedding a chart on another page

```html
<div id="my-chart"></div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="path/to/charts.js"></script>
<script>
  ChartDashboard.renderSingle({
    containerId: 'my-chart',
    dataUrl:     'data/montgomery_party_affiliation.json'
  });
</script>
```

---

## Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main` → Folder: `/docs`

Your dashboard will be live at:
`https://motorbikematt.github.io/ohio_voter_registration_parser/`
