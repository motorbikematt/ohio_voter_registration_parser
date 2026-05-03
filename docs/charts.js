/**
 * charts.js - Modular chart rendering engine for the Ohio Voter Registration dashboard.
 *
 * PUBLIC API
 * ----------
 * ChartDashboard.init(config)       Bootstraps the full dashboard from manifest.json.
 * ChartDashboard.renderSingle(opts) Renders one chart into any container on any page.
 */
const ChartDashboard = (() => {

  // ── State ────────────────────────────────────────────────────────────────
  let cfg          = {};
  let manifest     = null;
  let activeCounty = null;   // null = show all processed counties
  let activeGeo    = 'all';
  const instances  = {};

  // ── Entry point ──────────────────────────────────────────────────────────
  async function init(config) {
    cfg = config;
    _setupTheme();
    _setupScrollBehavior();
    _setupGeoFilter();

    try {
      manifest = await _fetchJSON(cfg.manifestUrl);
    } catch (e) {
      _showError(cfg.containerId, 'Failed to load ' + cfg.manifestUrl + ': ' + e.message);
      return;
    }

    _populateCountyDropdown();
    _renderAllSections();
    _updatePageDescription();
  }

  // ── County dropdown ──────────────────────────────────────────────────────
  function _populateCountyDropdown() {
    const sel = document.getElementById(cfg.countySelectId);
    if (!sel) return;

    // Only processed counties are listed. No "all" option, no greyed placeholders.
    const processedCounties = Array.from(
      new Set(manifest.processedCounties || manifest.counties || [])
    ).sort();

    sel.innerHTML = '';

    if (processedCounties.length === 0) {
      sel.appendChild(_el('option', {
        value: '',
        textContent: 'No counties processed yet',
        disabled: true
      }));
      return;
    }

    processedCounties.forEach(function(c) {
      sel.appendChild(_el('option', { value: c, textContent: c + ' County' }));
    });

    // Always default to the first processed county; the dashboard never shows
    // "all counties" at once.
    activeCounty = processedCounties[0];
    sel.value    = activeCounty;

    sel.addEventListener('change', function() {
      // Preserve the user's chart slot across the county switch so they can
      // compare chart-to-chart side-by-side. We use the browser's native
      // scrollIntoView anchor mechanism — that automatically respects the
      // CSS `scroll-margin-top` on .chart-section (which clears the sticky
      // header), handles mobile zoom and sub-pixel rounding correctly, and
      // updates the URL fragment so the dashboard view becomes shareable.
      //
      // We only anchor on CHART sections, not table sections. Tables are too
      // tall and their heights vary too much across counties for anchoring
      // to feel right; when the user is reading a table, we just preserve
      // absolute scrollY instead.
      var savedScrollY = window.scrollY;
      var anchor       = _focalChartSection();   // chart section slug, or null
      var anchorSuffix = anchor ? _slugSuffix(anchor.id, activeCounty) : null;

      activeCounty = sel.value;
      _updateHeaderLabel();
      _updatePageDescription();
      _filterSections();
      _renderVisibleSections();   // load any newly-revealed county's charts
      _rebuildNav();

      // Defer scroll-restore until after lazy chart construction has had a
      // chance to add layout (rAF inside _renderVisibleSections), otherwise
      // page height grows under our feet and the restore lands too high.
      requestAnimationFrame(function() {
        requestAnimationFrame(function() {
          if (anchorSuffix) {
            var newSlug = activeCounty.toLowerCase().replace(/ /g, '_');
            var target  = document.getElementById('section-' + newSlug + '-' + anchorSuffix);
            if (target && target.style.display !== 'none') {
              target.scrollIntoView({ behavior: 'auto', block: 'start' });
              return;
            }
          }
          // No chart anchor (user was reading a table) or target missing —
          // hold absolute scroll position so the page doesn't jump.
          window.scrollTo({ top: savedScrollY, behavior: 'auto' });
        });
      });
    });

    _updateHeaderLabel();
  }

  // Section ids that contain only chart visualisations (eligible for
  // chart-to-chart anchoring on county switch). Anything not in this list —
  // currently just precinct and city tables — is treated as a table section
  // and falls through to absolute-scrollY preservation.
  var _CHART_GEOGRAPHIES = { 'county': true, 'congressional': true };

  function _focalChartSection() {
    // Return the visible CHART section (not table) whose vertical midpoint is
    // closest to the viewport midpoint — i.e. the chart the user is actually
    // looking at. Returns the section element, or null if no chart section is
    // currently in view (user is reading a table or scrolled past all charts).
    var viewMid  = window.innerHeight / 2;
    var sections = document.querySelectorAll('.chart-section');
    var best     = null;
    var bestDist = Infinity;
    for (var i = 0; i < sections.length; i++) {
      var el = sections[i];
      if (el.style.display === 'none') continue;
      if (!_CHART_GEOGRAPHIES[el.dataset.geo]) continue;
      var rect  = el.getBoundingClientRect();
      // Only consider sections at least partially in the viewport.
      if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
      var elMid = rect.top + rect.height / 2;
      var dist  = Math.abs(elMid - viewMid);
      if (dist < bestDist) {
        best     = el;
        bestDist = dist;
      }
    }
    return best;
  }

  function _slugSuffix(sectionElementId, county) {
    // Given an element id like 'section-cuyahoga-party-affiliation' and the
    // active county name 'Cuyahoga', return 'party-affiliation' — the
    // county-independent suffix that identifies which CHART KIND this is.
    // Used to translate the user's focal section into the equivalent section
    // in the newly-selected county.
    var prefix = 'section-' + (county || '').toLowerCase().replace(/ /g, '_') + '-';
    if (sectionElementId.indexOf(prefix) === 0) {
      return sectionElementId.slice(prefix.length);
    }
    // Fallback: strip the leading 'section-' and the first slug-token.
    var trimmed = sectionElementId.replace(/^section-/, '');
    var dash    = trimmed.indexOf('-');
    return dash >= 0 ? trimmed.slice(dash + 1) : trimmed;
  }

  function _updateHeaderLabel() {
    const el = document.getElementById(cfg.headerCountyLabelId);
    if (el) el.textContent = activeCounty ? activeCounty + ' County' : '';
  }

  // ── Geography filter ─────────────────────────────────────────────────────
  function _setupGeoFilter() {
    document.addEventListener('click', function(e) {
      if (!e.target.classList.contains('geo-btn')) return;
      document.querySelectorAll('.geo-btn').forEach(function(b) { b.classList.remove('active'); });
      e.target.classList.add('active');
      activeGeo = e.target.dataset.geo;
      _filterSections();
      _rebuildNav();
    });
  }

  // ── Section rendering ────────────────────────────────────────────────────
  // Track which sections have already been rendered so we don't re-fetch and
  // re-construct charts every time the county dropdown changes.
  const _renderedSections = new Set();

  function _renderAllSections() {
    const container = document.getElementById(cfg.containerId);
    container.innerHTML = '';

    // Build the DOM scaffold for every section up front but DO NOT load chart
    // data yet — we render lazily after _filterSections() decides which
    // sections are visible. This avoids the Chart.js 0×0 sizing bug that
    // happens when a chart is constructed inside a display:none container.
    manifest.sections.forEach(function(section) {
      const wrapper = document.createElement('section');
      wrapper.className      = 'chart-section';
      wrapper.id             = 'section-' + section.id;
      wrapper.dataset.county = section.county;
      wrapper.dataset.geo    = section.geography;

      wrapper.innerHTML =
        '<div class="section-header">' +
          '<div class="section-meta">' +
            '<span class="geo-tag">' + _geoLabel(section.geography) + '</span>' +
            (section.county !== 'all' ? '<span class="county-tag">' + section.county + ' Co.</span>' : '') +
          '</div>' +
          '<h2 class="section-title">' + section.title + '</h2>' +
          (section.description ? '<p class="section-description">' + section.description + '</p>' : '') +
        '</div>' +
        '<div class="chart-wrapper" id="chart-wrapper-' + section.id + '">' +
          '<div class="chart-loading">Loading chart data&hellip;</div>' +
        '</div>' +
        '<div class="section-footer">' +
          '<span class="updated-label" id="updated-' + section.id + '"></span>' +
          '<a class="data-link" href="' + section.dataUrl + '" target="_blank" rel="noopener">View raw JSON &nearr;</a>' +
        '</div>';

      container.appendChild(wrapper);
    });

    _filterSections();           // hides everything not in the active county
    _renderVisibleSections();    // now load+render only what's actually shown
    _rebuildNav();
  }

  function _renderVisibleSections() {
    // Render any visible section that hasn't been rendered yet. Called both
    // on initial load and after a county switch to populate newly-revealed
    // sections. Using rAF so the DOM has reflowed and the chart-wrapper has
    // its real width before Chart.js measures it.
    requestAnimationFrame(function() {
      manifest.sections.forEach(function(s) {
        if (_renderedSections.has(s.id)) return;
        if (!_sectionVisible(s)) return;
        const el = document.getElementById('section-' + s.id);
        if (!el || el.style.display === 'none') return;
        _renderedSections.add(s.id);
        _loadAndRender(s);
      });
      // Re-fit any already-rendered charts that just became visible — the
      // canvas may have been sized while hidden if the user is switching
      // back to a county whose charts were rendered earlier.
      Object.keys(instances).forEach(function(id) {
        const wrap = document.getElementById('chart-wrapper-' + id);
        if (wrap && wrap.offsetParent !== null) {
          try { instances[id].resize(); } catch (e) {}
        }
      });
    });
  }

  async function _loadAndRender(section) {
    const wrapper = document.getElementById('chart-wrapper-' + section.id);
    try {
      const data  = await _fetchJSON(section.dataUrl);
      const updEl = document.getElementById('updated-' + section.id);
      if (updEl && data.updated) updEl.textContent = 'Updated ' + data.updated;
      _renderToWrapper(wrapper, data, section.id);
    } catch (e) {
      wrapper.innerHTML = '<p class="error">Could not load ' + section.dataUrl + '<br><small>' + e.message + '</small></p>';
    }
  }

  // ── Filter / show-hide ───────────────────────────────────────────────────
  function _filterSections() {
    manifest.sections.forEach(function(s) {
      const el = document.getElementById('section-' + s.id);
      if (!el) return;
      el.style.display = _sectionVisible(s) ? '' : 'none';
    });
  }

  function _sectionVisible(s) {
    const countyMatch = !activeCounty || s.county === activeCounty;
    const geoMatch    = activeGeo === 'all' || s.geography === activeGeo;
    return countyMatch && geoMatch;
  }

  // ── Nav ──────────────────────────────────────────────────────────────────
  function _rebuildNav() {
    const nav = document.getElementById(cfg.navId);
    if (!nav) return;
    nav.innerHTML = '';
    manifest.sections
      .filter(_sectionVisible)
      .forEach(function(s) {
        nav.appendChild(_el('a', {
          href:        '#section-' + s.id,
          textContent: s.navLabel || s.title,
          className:   'nav-link'
        }));
      });
  }

  // ── Chart rendering ──────────────────────────────────────────────────────
  function _renderToWrapper(wrapper, data, id) {
    wrapper.innerHTML = '';

    if (data.type === 'table') {
      _renderTable(wrapper, data, id);
      return;
    }

    const canvas = _el('canvas', { id: 'canvas-' + id });
    wrapper.appendChild(canvas);

    if (instances[id]) {
      instances[id].destroy();
      delete instances[id];
    }

    const colors   = _themeColors();
    const isRadial = data.type === 'pie' || data.type === 'doughnut';

    instances[id] = new Chart(canvas, {
      type: data.type,
      data: data.chartConfig,
      options: Object.assign({
        responsive:          true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            labels: { color: colors.text, font: { family: 'system-ui, sans-serif', size: 13 } }
          },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: isRadial ? {} : {
          x: {
            ticks: { color: colors.text, maxRotation: 45 },
            grid:  { color: colors.grid }
          },
          y: {
            beginAtZero: true,
            ticks: { color: colors.text, callback: function(v) { return v.toLocaleString(); } },
            grid:  { color: colors.grid }
          }
        }
      }, data.chartOptions || {})
    });
  }

  // ── Sortable table rendering ─────────────────────────────────────────────
  function _renderTable(wrapper, data, id) {
    var sortState = { col: null, dir: 1 };

    // Determine which columns are numeric
    var numericCols = {};
    if (data.rows && data.rows.length > 0) {
      data.rows[0].forEach(function(cell, ci) {
        var n = parseFloat(String(cell).replace(/,/g, ''));
        numericCols[ci] = !isNaN(n);
      });
    }

    function sortedRows() {
      if (sortState.col === null) return data.rows.slice();
      var col = sortState.col;
      var dir = sortState.dir;
      var isNum = numericCols[col];
      return data.rows.slice().sort(function(a, b) {
        var av = String(a[col]).replace(/,/g, '');
        var bv = String(b[col]).replace(/,/g, '');
        if (isNum) {
          return dir * ((parseFloat(av) || 0) - (parseFloat(bv) || 0));
        }
        return dir * av.localeCompare(bv);
      });
    }

    function render() {
      wrapper.innerHTML = '';
      var scroll = _el('div', { className: 'table-scroll' });
      var table  = _el('table', { className: 'data-table' });

      // Header
      var thead = document.createElement('thead');
      var hrow  = document.createElement('tr');
      data.headers.forEach(function(h, hi) {
        var indicator = (sortState.col === hi) ? (sortState.dir === 1 ? ' ▲' : ' ▼') : '';
        var th = _el('th', { textContent: h + indicator });
        th.style.cursor     = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', function() {
          if (sortState.col === hi) {
            sortState.dir *= -1;
          } else {
            sortState.col = hi;
            // Numbers default descending (largest first); text defaults ascending
            sortState.dir = numericCols[hi] ? -1 : 1;
          }
          render();
        });
        hrow.appendChild(th);
      });
      thead.appendChild(hrow);
      table.appendChild(thead);

      // Body
      var tbody = document.createElement('tbody');
      sortedRows().forEach(function(row, i) {
        var tr = _el('tr', { className: i % 2 === 0 ? 'row-even' : 'row-odd' });
        row.forEach(function(cell) { tr.appendChild(_el('td', { textContent: cell })); });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      scroll.appendChild(table);
      wrapper.appendChild(scroll);
    }

    render();
  }

  // ── Theme ────────────────────────────────────────────────────────────────
  function _setupTheme() {
    const saved = localStorage.getItem('vr-theme') || 'light';
    _applyTheme(saved);
    const btn = document.getElementById(cfg.themeToggleId);
    if (btn) {
      btn.addEventListener('click', function() {
        const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        _applyTheme(next);
        _recolorAllCharts();
      });
    }
  }

  function _applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('vr-theme', theme);
    const icon = document.querySelector('.theme-icon');
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }

  function _recolorAllCharts() {
    const colors = _themeColors();
    Object.values(instances).forEach(function(chart) {
      if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels)
        chart.options.plugins.legend.labels.color = colors.text;
      if (chart.options.scales && chart.options.scales.x) {
        chart.options.scales.x.ticks.color = colors.text;
        chart.options.scales.x.grid.color  = colors.grid;
      }
      if (chart.options.scales && chart.options.scales.y) {
        chart.options.scales.y.ticks.color = colors.text;
        chart.options.scales.y.grid.color  = colors.grid;
      }
      chart.update();
    });
  }

  function _themeColors() {
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
      text: dark ? '#e2e8f0' : '#1a202c',
      grid: dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)'
    };
  }

  // ── Scroll: compact header ───────────────────────────────────────────────
  function _setupScrollBehavior() {
    const header = document.getElementById('site-header');
    if (!header) return;
    window.addEventListener('scroll', function() {
      header.classList.toggle('compact', window.scrollY > 72);
    }, { passive: true });
  }

  // ── Page description ─────────────────────────────────────────────────────
  function _updatePageDescription() {
    const el = document.getElementById(cfg.descriptionId);
    if (!el || !manifest) return;
    const county = activeCounty ? activeCounty + ' County' : 'all processed counties';
    el.textContent = manifest.description
      ? manifest.description.replace('{county}', county)
      : 'Voter registration analysis for ' + county + '. Use the controls above to filter.';
    const noteEl = document.getElementById(cfg.dataNoteId);
    if (noteEl && manifest.dataNote) noteEl.textContent = manifest.dataNote;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  async function _fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  function _el(tag, props) {
    const el = document.createElement(tag);
    if (props) Object.assign(el, props);
    return el;
  }

  function _geoLabel(geo) {
    var map = {
      county:          'County',
      precinct:        'Precinct',
      city:            'City / Township',
      'city-precinct': 'City Precincts',
      congressional:   'Congressional Dist.',
      all:             'Statewide'
    };
    return map[geo] || geo;
  }

  function _showError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = '<p class="error">' + msg + '</p>';
  }

  // ── Public: embed a single chart on any page ─────────────────────────────
  async function renderSingle(opts) {
    const wrapper = document.getElementById(opts.containerId);
    if (!wrapper) {
      console.error('ChartDashboard.renderSingle: no element #' + opts.containerId);
      return;
    }
    try {
      const data = await _fetchJSON(opts.dataUrl);
      _renderToWrapper(wrapper, data, opts.containerId + '_embed_' + Date.now());
    } catch (e) {
      _showError(opts.containerId, 'Could not load ' + opts.dataUrl + ': ' + e.message);
    }
  }

  return { init: init, renderSingle: renderSingle };

})();
