# Chart.js Legend Plugins & Alternatives

## Official Chart.js Built-in Plugins

Chart.js 4.4.0 comes with these official plugins (all enabled by default):

1. **Legend plugin** (`plugins.legend`)
   - What it does: Renders the default legend
   - Limitations: Single-column layout when positioned left/right
   - Customizable: Yes, but not for multi-column layouts
   - Official docs: `https://www.chartjs.org/docs/latest/configuration/legend.html`

2. **Tooltip plugin** (`plugins.tooltip`)
   - What it does: Shows hover-over data labels
   - Relevant to legend: Tooltips can replace or supplement legend data
   - Your use: Disabled for doughnuts, enabled for bar charts

3. **Title plugin** (`plugins.title`)
   - Not directly related to legend, but worth knowing

---

## Community Chart.js Legend Plugins

The Chart.js community has created plugins specifically for legend customization:

### **1. chartjs-plugin-datalabels** (Official)
- **Purpose**: Display labels directly on chart elements
- **Why it matters for legends**: Complements or replaces the legend entirely
- **GitHub**: `chartjs/chartjs-plugin-datalabels`
- **Pros**: 
  - Moves data directly onto doughnut slices
  - Reduces dependency on separate legend
- **Cons**:
  - Not a legend solution per se
  - Can clutter small doughnuts
- **Relevance to your use case**: Medium (alternative approach, not legend layout)

---

### **2. chartjs-legend-position-plugin** (Community)
- **Purpose**: Allows positioning legend outside the chart area
- **Relevance to 3-column layout**: Very low (still single column)
- **Verdict**: Exists, but doesn't solve your multi-column requirement

---

### **3. chartjs-plugin-colorschemes** (Community)
- **Purpose**: Color palette management
- **Relevance to legend**: Only affects colors, not layout
- **Verdict**: Not relevant to your problem

---

## Ecosystem Alternatives (Non-Plugins)

### **A. Chart.js Legend Positioning + Custom CSS Grid**
This is what most developers do instead of plugins.

**How it works:**
1. Disable Chart.js legend: `legend: { display: false }`
2. Render your own HTML legend next to/below chart
3. Use CSS Grid to arrange in 3 columns
4. Manually build legend items from your data

**Pros:**
- Fully flexible layout
- No dependencies on external plugins
- Works great for static dashboards like yours

**Cons:**
- Manual HTML synchronization needed

---

### **B. Alternative Charting Libraries (Not Chart.js)**

If you're willing to switch away from Chart.js:

| Library | Multi-Column Legend? | Notes |
|---------|----------------------|-------|
| **ECharts** (Apache) | Yes, native | Powerful, heavy (~1MB) |
| **Plotly.js** | Yes, native | Great for interactive dashboards |
| **Nivo** | Yes, native | React-first, beautiful defaults |
| **Visx (Airbnb)** | Requires custom build | Lowest-level, most flexible |
| **D3.js** | Requires custom build | Maximum flexibility, steep learning curve |

---

## Known Issues / Limitations

### **Chart.js Legend Wrapping**
Some developers have reported that setting `maxWidth` on legend labels causes text wrapping but **not** column wrapping. It still renders as a single column, just with wrapped text inside each item.

**Status:** Won't fix in Chart.js core (by design).

---

## Recommendations for Your Use Case

### **Option 1: Custom HTML Legend (RECOMMENDED FOR YOU)**

**Why:** You're building a static, print-friendly dashboard. No dynamic updates needed.

**Implementation:**
- Disable Chart.js legend
- Build 3-column HTML grid adjacent to doughnut
- Populate from your JSON data
- Dark/light mode via `_themeColors()`

**Effort:** ~50 lines of JavaScript  
**Flexibility:** 100%  
**Maintenance:** Minimal (data is static)

---

### **Option 2: Upgrade to ECharts**

**Why:** Native multi-column legend support, handles dark/light mode automatically.

**Effort:** Full rewrite of chart rendering (~1-2 days)  
**Payoff:** Cleaner code, built-in legend layouts  
**Downside:** 1MB+ library load, change entire dashboard architecture

---

### **Option 3: Plugin + HTML Hybrid**

Use a hypothetical custom plugin that:
1. Hooks into Chart.js lifecycle
2. Renders legend items to a separate DOM container
3. You style that container as CSS Grid

**Effort:** ~100 lines of plugin code  
**Payoff:** Legend stays tightly integrated with Chart.js  
**Downside:** Still custom code; not much simpler than Option 1

---

## Search Terms for Further Research

If you want to explore on your own:

- `"chart.js" "multi column legend"` → Shows similar requests from other developers
- `site:github.com/chartjs/ legend positioning` → Official repo discussions
- `chart.js legend plugin custom` → Community solutions
- `echarts doughnut multi-column legend` → If you consider switching

---

## Conclusion

**No off-the-shelf Chart.js plugin provides multi-column legend layout.**

The three best paths forward are:
1. **Custom HTML legend** (recommended for you)
2. **Chart.js plugin you write** (moderate complexity)
3. **Switch to ECharts** (full rewrite, maximum flexibility)

Given your project scope (static, print-friendly, existing charts.js), **Option 1 is the fastest and cleanest path.**

