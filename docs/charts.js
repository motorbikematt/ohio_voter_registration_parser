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
      // Preserve the chart slot the user is looking at across the county switch
      // so they can compare side-by-side without the page jumping.
      //
      // Strategy: identify the visible chart-section nearest the top of the
      // viewport, record its offset from the viewport top (anchorOffset), swap
      // counties, then re-scroll so the equivalent section in the new county
      // sits at the same pixel offset. The "equivalent" section is matched by
      // (geography, position-among-visible) so the Nth city table in County A
      // becomes the Nth city table in County B.
      var anchor       = _topVisibleSection();
      var anchorOffset = anchor ? anchor.el.getBoundingClientRect().top : 0;
      var anchorGeo    = anchor ? anchor.el.dataset.geo : null;
      var anchorIndex  = anchor ? anchor.indexInGeo    : 0;
      var savedScrollY = window.scrollY;

      activeCounty = sel.value;
      _updateHeaderLabel();
      _updatePageDescription();
      _filterSections();
      _renderVisibleSections();   // load any newly-revealed county's charts
      _rebuildNav();

      // Scroll-restore is deferred to the next frame so the DOM has reflowed
      // (sections that were display:none take their real height back) before
      // we measure the target section's position.
      requestAnimationFrame(function() {
        if (anchorGeo) {
          var target = _nthVisibleSectionOfGeo(anchorGeo, anchorIndex);
          if (target) {
            var targetTop = target.getBoundingClientRect().top + window.scrollY;
            window.scrollTo({ top: targetTop - anchorOffset, behavior: 'auto' });
            return;
          }
        }
        // Fallback: nothing to anchor on. Preserve the absolute scroll
        // position so the page doesn't jump to top.
        window.scrollTo({ top: savedScrollY, behavior: 'auto' });
      });
    });

    _updateHeaderLabel();
  }

  function _topVisibleSection() {
    // Return the visible chart-section closest to the top of the viewport
    // (but not above it), plus its zero-based index among visible sections of
    // the same geography. Used as the scroll anchor for county switching.
    var sections = document.querySelectorAll('.chart-section');
    var best     = null;
    var bestTop  = Infinity;
    var counters = {};
    var indexInGeo = 0;
    for (var i = 0; i < sections.length; i++) {
      var el = sections[i];
      if (el.style.display === 'none') continue;
      var geo = el.dataset.geo;
      counters[geo] = (counters[geo] || 0);
      var top = el.getBoundingClientRect().top;
      // Pick the first section whose top is at or below 0 (in-viewport),
      // or — if none qualify — the section with the smallest |top| value.
      if (top >= -1 && top < bestTop) {
        best       = el;
        bestTop    = top;
        indexInGeo = counters[geo];
      }
      counters[geo]++;
    }
    return best ? { el: best, indexInGeo: indexInGeo } : null;
  }

  function _nthVisibleSectionOfGeo(geo, n) {
    // Return the n-th visible chart-section whose dataset.geo === geo.
    // Falls back to the last visible one of that geo if n is out of range,
    // or the first visible section of any geo if there are none.
    var sections = document.querySelectorAll('.chart-section');
    var matches = [];
    for (var i = 0; i < sections.length; i++) {
      var el = sections[i];
      if (el.style.display === 'none') continue;
      if (el.dataset.geo === geo) matches.push(el);
    }
    if (matches.length) return matches[Math.min(n, matches.length - 1)];
    for (var j = 0; j < sections.length; j++) {
      if (sections[j].style.display !== 'none') return sections[j];
    }
    return null;
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
