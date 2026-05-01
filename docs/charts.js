/**
 * charts.js - Modular chart rendering engine for the Ohio Voter Registration dashboard.
 *
 * PUBLIC API
 * ----------
 * ChartDashboard.init(config)       Bootstraps the full dashboard from manifest.json.
 * ChartDashboard.renderSingle(opts) Renders one chart into any container on any page.
 *
 * renderSingle usage (embed in a comparison page):
 *   <div id="my-chart"></div>
 *   <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
 *   <script src="path/to/charts.js"></script>
 *   <script>
 *     ChartDashboard.renderSingle({
 *       containerId: 'my-chart',
 *       dataUrl:     'data/montgomery_party_affiliation.json'
 *     });
 *   </script>
 */
const ChartDashboard = (() => {

  // ── State ────────────────────────────────────────────────────────────────
  let cfg          = {};
  let manifest     = null;
  let activeCounty = null;   // null = all counties
  let activeGeo    = 'all';
  const instances  = {};     // Chart.js instances keyed by section id

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

    sel.innerHTML = '';
    sel.appendChild(_el('option', { value: 'all', textContent: 'All Counties' }));
    manifest.counties.forEach(function(c) {
      sel.appendChild(_el('option', { value: c, textContent: c + ' County' }));
    });

    // Default to first county if there is only one
    if (manifest.counties.length === 1) {
      sel.value    = manifest.counties[0];
      activeCounty = manifest.counties[0];
    }

    sel.addEventListener('change', function() {
      activeCounty = sel.value === 'all' ? null : sel.value;
      _updateHeaderLabel();
      _updatePageDescription();
      _filterSections();
      _rebuildNav();
    });

    _updateHeaderLabel();
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
  function _renderAllSections() {
    const container = document.getElementById(cfg.containerId);
    container.innerHTML = '';

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
      _loadAndRender(section);
    });

    _filterSections();
    _rebuildNav();
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
    const countyMatch = !activeCounty || s.county === activeCounty || s.county === 'all';
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
      _renderTable(wrapper, data);
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

  function _renderTable(wrapper, data) {
    const scroll = _el('div', { className: 'table-scroll' });
    const table  = _el('table', { className: 'data-table' });

    const thead = document.createElement('thead');
    const hrow  = document.createElement('tr');
    data.headers.forEach(function(h) { hrow.appendChild(_el('th', { textContent: h })); });
    thead.appendChild(hrow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    data.rows.forEach(function(row, i) {
      const tr = _el('tr', { className: i % 2 === 0 ? 'row-even' : 'row-odd' });
      row.forEach(function(cell) { tr.appendChild(_el('td', { textContent: cell })); });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    scroll.appendChild(table);
    wrapper.appendChild(scroll);
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
    const county = activeCounty ? activeCounty + ' County' : 'all available counties';
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
    var map = { county: 'County', precinct: 'Precinct', city: 'City',
                congressional: 'Congressional Dist.', all: 'Statewide' };
    return map[geo] || geo;
  }

  function _showError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = '<p class="error">' + msg + '</p>';
  }

  // ── Public: embed a single chart on any page ─────────────────────────────
  /**
   * ChartDashboard.renderSingle({ containerId, dataUrl })
   *
   * Renders one chart JSON into any div on any page.
   * Host page must load Chart.js before calling this.
   *
   * Example:
   *   ChartDashboard.renderSingle({
   *     containerId: 'comparison-left',
   *     dataUrl:     'data/montgomery_party_affiliation.json'
   *   });
   */
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
