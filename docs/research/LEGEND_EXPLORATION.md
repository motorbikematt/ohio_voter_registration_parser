# Doughnut Chart Legend Layout Exploration

## Your Understanding: CORRECT ✓

**Chart.js built-in legend does NOT support multi-column layouts when positioned left/right.**

When you set `position: 'right'`, Chart.js renders a single vertical column. There is no built-in option to split it into 3 columns.

---

## Proposed Layout

```
┌──────────────────────────────────────────────────┐
│  Doughnut Chart (left)    │  Legend (right, 3 cols)   │
│                           │                            │
│        [pie]              │  Col 1      Col 2   Col 3 │
│                           │  ────      ────    ────   │
│                           │  Pure R     Unc-M   D-Cross│
│                           │  R-Cross    Unc-NH  Pure D │
│                           │  Unc-LR             Unc-LD │
│                           │                            │
└──────────────────────────────────────────────────┘
```

---

## Your Three Cohort Groupings

1. **Democratic types**: Pure D, D-Crossover
2. **Mixed & Unaffiliated**: UNC-Lifetime-R, UNC-Mixed, UNC-No-History, UNC-Lifetime-D
3. **Republican types**: Pure R, R-Crossover

(Note: 8 cohorts → 3 columns means uneven distribution. See recommendations below.)

---

## Solutions: Ranked by Feasibility + Dark/Light Mode Support

### **Option 1: Disable Chart.js Legend + Custom HTML Legend (RECOMMENDED)**

**Approach:** Turn off Chart.js's built-in legend. Render a completely custom HTML legend next to the chart.

**Pros:**
- Full control over layout, columns, spacing
- Easy to implement responsive grids
- Dark/light mode: Just read `_themeColors()` from your existing code
- Works perfectly with tooltips (no conflict)

**Cons:**
- Manual synchronization if data changes (but it doesn't in your use case—JSON is static)

**Implementation sketch:**
```javascript
// In charts.js, around line 773
const container = document.createElement('div');
container.style.display = 'flex';
container.style.gap = '20px';

const canvasWrapper = document.createElement('div');
canvasWrapper.style.flex = '1';

const legendWrapper = document.createElement('div');
legendWrapper.style.flex = '1';
legendWrapper.style.display = 'grid';
legendWrapper.style.gridTemplateColumns = '1fr 1fr 1fr';
legendWrapper.style.gap = '15px';

// Build legend items
data.chartConfig.datasets[0].forEach((color, i) => {
  const item = document.createElement('div');
  // Color square + label + value
});

container.appendChild(canvasWrapper);
container.appendChild(legendWrapper);
wrapper.appendChild(container);

// Disable Chart.js legend
instances[id] = new Chart(canvas, {
  options: {
    plugins: {
      legend: { display: false }  // ← Disable built-in
    }
  }
});
```

**Dark/Light Mode:** Use your existing `_themeColors()` function to set text color on legend items.

---

### **Option 2: Chart.js Plugin with Custom Legend Layout**

**Approach:** Write a Chart.js plugin that renders a custom legend instead of the default.

**Pros:**
- Legend stays tightly integrated with Chart.js lifecycle
- Automatically redraws when chart updates
- Still full layout control

**Cons:**
- Slightly more complex plugin code
- Requires understanding Chart.js plugin system

**Reference:**
- https://www.chartjs.org/docs/latest/api/classes/Chart.html#plugins
- https://github.com/chartjs/chartjs-plugin-datalabels (example plugin)

**Sketch:**
```javascript
const multiColumnLegendPlugin = {
  id: 'multiColumnLegend',
  afterDatasetsDraw(chart) {
    const container = document.getElementById('legend-container');
    const dataset = chart.data.datasets[0];
    const labels = chart.data.labels;
    const colors = _themeColors();
    
    // Build 3-column grid
    container.style.display = 'grid';
    container.style.gridTemplateColumns = '1fr 1fr 1fr';
    // ... render items
  }
};
```

---

### **Option 3: Hybrid—Semantic Grouping with Headers**

**Approach:** Custom HTML legend with section headers above each column.

**Layout:**
```
┌─────────────────────────────────────┐
│  Doughnut  │  Republican  Mixed  Dem  │
│            │  ────────────────────     │
│  [pie]     │  Pure R    Unc-LR Pure D │
│            │  R-Cross   Unc-Mixed D-Cr│
│            │             Unc-NH       │
│            │             Unc-LD       │
└─────────────────────────────────────┘
```

**Pros:**
- Clear semantic grouping
- Easier to scan
- Still responsive

**Cons:**
- More HTML to manage

---

## Dark/Light Mode Implementation

**Current approach in charts.js (lines 744–748):**
```javascript
var tc = _themeColors();
chart.options.plugins.legend.labels.color = tc.text;
```

**For custom legend, do the same:**
```javascript
const colors = _themeColors();
legendItem.style.color = colors.text;
legendItem.style.backgroundColor = colors.bg;  // if you add a background
```

The `_themeColors()` function already returns `{ text, bg, grid }`. Use `text` and `bg` for your custom legend.

---

## Recommendations

**For your Ohio voter dashboard, I recommend Option 1:**

1. **Why:** Your charts are static (JSON-driven). No dynamic updates. A simple custom HTML legend is zero-overhead.
2. **Implementation:** ~50 lines of code in `charts.js`.
3. **Flexibility:** You can reorder cohorts by column without touching Chart.js.
4. **Dark/Light:** Leverages your existing `_themeColors()`.

**Next steps:**
- Decide final column arrangement (3 equal columns, or semantic grouping?)
- Decide if you want section headers per column
- I can write the implementation for your charts.js

---

## Reference: Chart.js Legend Documentation

- https://www.chartjs.org/docs/latest/configuration/legend.html
- No mention of multi-column layouts—confirms your understanding.

