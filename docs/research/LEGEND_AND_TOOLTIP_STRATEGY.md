# Executive Briefing: Data Visualization Strategy
**Project:** Ohio Voter Registration Analysis Dashboard
**Date:** May 8, 2026
**Subject:** Optimization of Radial Chart Interactivity and Legend Scalability

---

## 1. Executive Summary
The current implementation of Donut (Radial) charts within the dashboard requires optimization to resolve a known tooltip rendering issue and to support a more complex, multi-column legend layout. Research into industry-standard libraries confirms that while the current library (**Chart.js**) is the optimal choice for mobile performance, it requires a "Hybrid-DOM" approach to achieve the desired visual clarity and semantic grouping of voter cohorts.

---

## 2. Key Findings

### A. The "Wrong Number" Tooltip Bug
*   **Root Cause:** The interaction `mode: 'index'` and `intersect: false` (standard for bar/line charts) is incompatible with radial geometries. It causes the tooltip to "snap" to indices rather than pixel-perfect mouse coordinates.
*   **Resolution:** Transitioning to `mode: 'nearest'` and `intersect: true` ensures the data wedge under the cursor is the one represented in the tooltip.

### B. Legend Layout Constraints
*   **Limitation:** Chart.js does not natively support multi-column layouts when legends are positioned to the left or right of a chart.
*   **Strategic Recommendation:** Implement an **HTML-Syncing Legend Plugin**. By moving the legend from the `<canvas>` to the DOM, we gain 100% control over layout using CSS Grid, allowing for the requested 3-column partisan grouping.

### C. Competitive Landscape (ECharts vs. ApexCharts)
*   **Mobile Weight:** **Chart.js** (approx. 60KB) is significantly lighter than ECharts (200KB+), making it the superior choice for low-bandwidth mobile environments.
*   **Visual Clarity:** While ECharts offers native SVG rendering, the clarity of Chart.js can be matched on high-density displays by utilizing HTML for text rendering (legends) while keeping the Donut itself on the Canvas.

---

## 3. Preserved Strategy: The "Hybrid-DOM" Architecture

To preserve the longevity and maintainability of the dashboard, the following technical path is recommended:

1.  **Architecture:** Maintain Chart.js as the core rendering engine to preserve the lightweight mobile footprint.
2.  **Plugin Development:** Develop a generalized `GridLegend` plugin that:
    *   Hides the default Canvas legend.
    *   Generates a CSS Grid-based HTML legend.
    *   Enables **Semantic Sorting**: Grouping cohorts by partisan type (Republican, Democratic, Unaffiliated) into distinct columns.
3.  **Responsiveness:** Use CSS Media Queries to switch from a **3-column right-aligned legend** (Desktop) to a **2-column bottom-aligned legend** (Mobile).

---

## 4. Implementation Difficulty & Impact
*   **Implementation Effort:** Low-Moderate (requires surgical refactoring of `charts.js`).
*   **Performance Impact:** Negligible (HTML legends are more efficient for accessibility/SEO than Canvas text).
*   **Maintenance:** Improved (non-technical contributors can adjust legend styling via CSS without touching JavaScript logic).

---

**Technical Lead Note:** 
*The proposed transition to HTML legends is a one-time architectural shift that solves the current layout limitations while future-proofing the dashboard for additional data cohorts (Phase 3).*
