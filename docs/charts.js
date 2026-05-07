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
  let cfg            = {};
  let manifest       = null;
  let activeCounty   = null;
  let activeGeo      = 'all';
  let activePrecinct = null;   // null = no precinct selected; string = selected precinct name
  let activeScope    = 'county'; // county | precinct | city
  const instances    = {};

  // ── Entry point ──────────────────────────────────────────────────────────
  async function init(config) {
    cfg = config;
    _setupTheme();
    _setupScrollBehavior();
    _setupScopeTabs();
    _setupGeoFilter();

    try {
      manifest = await _fetchJSON(cfg.manifestUrl);
    } catch (e) {
      _showError(cfg.containerId, 'Failed to load ' + cfg.manifestUrl + ': ' + e.message);
      return;
    }

    _applyUrlState();
    _populateCountyDropdown();
    _syncGeoButtonsToActiveGeo();
    _syncScopeTabsToActiveScope();
    _renderAllSections();
    _updatePageDescription();

    var hashSuffix = _readHashSuffix();
    if (hashSuffix) _scrollToSuffixWhenReady(hashSuffix);
  }

  // ── URL state ────────────────────────────────────────────────────────────
  function _readUrlParams() {
    var params = new URLSearchParams(window.location.search);
    return {
      county:   params.get('county'),
      geo:      params.get('geo'),
      precinct: params.get('precinct'),
    };
  }

  function _readHashSuffix() {
    var h = window.location.hash || '';
    return h.replace(/^#/, '') || null;
  }

  function _applyUrlState() {
    var params    = _readUrlParams();
    var processed = manifest.processedCounties || manifest.counties || [];

    if (params.county && processed.indexOf(params.county) >= 0) {
      activeCounty = params.county;
    } else if (processed.length > 0) {
      activeCounty = processed.slice().sort()[0];
    }

    // Restore scope + geo from URL
    if (params.geo === 'precinct-detail' || params.geo === 'precinct') {
      activeScope    = 'precinct';
      activeGeo      = params.geo;
      if (params.precinct) activePrecinct = params.precinct;
    } else if (params.geo === 'city') {
      activeScope = 'city';
      activeGeo   = 'city';
    } else {
      var validGeos = ['all', 'county', 'city', 'city-precinct', 'precinct', 'congressional'];
      if (params.geo && validGeos.indexOf(params.geo) >= 0) {
        activeGeo = params.geo;
      }
      activeScope = 'county';
    }
  }

  function _writeUrlState(opts) {
    var url     = new URL(window.location.href);
    var changed = false;

    if (opts && 'county' in opts) {
      if (opts.county) url.searchParams.set('county', opts.county);
      else             url.searchParams.delete('county');
      changed = true;
    }
    if (opts && 'geo' in opts) {
      if (opts.geo && opts.geo !== 'all') url.searchParams.set('geo', opts.geo);
      else                                url.searchParams.delete('geo');
      changed = true;
    }
    if (opts && 'precinct' in opts) {
      if (opts.precinct) url.searchParams.set('precinct', opts.precinct);
      else               url.searchParams.delete('precinct');
      changed = true;
    }
    if (opts && 'hash' in opts) {
      url.hash = opts.hash ? opts.hash : '';
      changed = true;
    }
    if (changed) history.replaceState(null, '', url.toString());
  }

  function _syncGeoButtonsToActiveGeo() {
    document.querySelectorAll('.geo-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.geo === activeGeo);
    });
  }

  function _syncScopeTabsToActiveScope() {
    var tabs = document.getElementById(cfg.scopeTabsId);
    if (!tabs) return;
    tabs.querySelectorAll('.scope-tab').forEach(function(t) {
      t.classList.toggle('active', t.dataset.scope === activeScope);
    });
    // Show/hide geo sub-filter and precinct control based on active scope
    var geoGroup      = document.getElementById(cfg.geoFilterGroupId);
    var precinctCtrl  = document.getElementById(cfg.precinctControlId);

    if (activeScope === 'county') {
      if (geoGroup)     geoGroup.style.display     = '';
      if (precinctCtrl) precinctCtrl.style.display  = 'none';
    } else if (activeScope === 'precinct') {
      if (geoGroup)     geoGroup.style.display     = 'none';
      if (precinctCtrl) precinctCtrl.style.display  = '';
    } else if (activeScope === 'city') {
      if (geoGroup)     geoGroup.style.display     = 'none';
      if (precinctCtrl) precinctCtrl.style.display  = 'none';
    }
  }

  // ── Section readiness helpers ────────────────────────────────────────────
  function _isSectionReady(el) {
    if (!el || el.style.display === 'none') return false;
    var loading = el.querySelector('.chart-loading');
    if (loading) return false;
    var content = el.querySelector('canvas, .data-table, .error');
    if (!content) return false;
    if (content.tagName === 'CANVAS' && content.offsetHeight < 20) return false;
    return true;
  }

  function _headerOffset() {
    var h = document.getElementById('site-header');
    return h ? h.getBoundingClientRect().height + 8 : 138;
  }

  function _scrollToElement(el) {
    var rect = el.getBoundingClientRect();
    var top  = rect.top + window.scrollY - _headerOffset();
    window.scrollTo({ top: top, left: 0, behavior: 'auto' });
  }

  function _scrollToSuffixWhenReady(suffix) {
    var newSlug  = (activeCounty || '').toLowerCase().replace(/ /g, '_');
    var targetId = 'section-' + newSlug + '-' + suffix;
    var deadline = performance.now() + 4000;
    var scrolled = false;

    function tryScroll() {
      if (scrolled) return true;
      var el = document.getElementById(targetId);
      if (!_isSectionReady(el)) return false;
      requestAnimationFrame(function() {
        var fresh = document.getElementById(targetId);
        if (!_isSectionReady(fresh)) return;
        _scrollToElement(fresh);
        scrolled = true;
      });
      scrolled = true;
      return true;
    }

    if (tryScroll()) return;

    var observer = new MutationObserver(function() {
      if (tryScroll() || performance.now() > deadline) observer.disconnect();
    });
    observer.observe(document.body, {
      childList: true, subtree: true,
      attributes: true, attributeFilter: ['style', 'class'],
    });

    var interval = setInterval(function() {
      if (tryScroll() || performance.now() > deadline) {
        clearInterval(interval);
        observer.disconnect();
      }
    }, 60);
  }

  // ── County dropdown ──────────────────────────────────────────────────────
  function _populateCountyDropdown() {
    const sel = document.getElementById(cfg.countySelectId);
    if (!sel) return;

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

    sel.value = activeCounty;

    sel.addEventListener('change', function() {
      var savedScrollY = window.scrollY;
      var anchor       = _focalChartSection();
      var anchorSuffix = anchor ? _slugSuffix(anchor.id, activeCounty) : null;

      activeCounty   = sel.value;
      activePrecinct = null;
      _resetPrecinctDropdown();

      _writeUrlState({ county: activeCounty, geo: activeGeo, precinct: null, hash: anchorSuffix });
      _updateHeaderLabel();
      _updatePageDescription();
      _filterSections();
      _renderVisibleSections();
      _rebuildNav();

      // Load precinct index for new county if in precinct scope
      if (activeScope === 'precinct') {
        _loadPrecinctIndex();
      }

      if (anchorSuffix) {
        _scrollToSuffixWhenReady(anchorSuffix);
      } else {
        requestAnimationFrame(function() {
          window.scrollTo({ top: savedScrollY, behavior: 'auto' });
        });
      }
    });

    _updateHeaderLabel();

    // Load precinct index if we're already in precinct scope on init
    if (activeScope === 'precinct') {
      _loadPrecinctIndex();
    }
  }

  var _CHART_GEOGRAPHIES = { 'county': true, 'congressional': true, 'precinct-detail': true };

  function _focalChartSection() {
    var viewMid  = window.innerHeight / 2;
    var sections = document.querySelectorAll('.chart-section');
    var best     = null;
    var bestDist = Infinity;
    for (var i = 0; i < sections.length; i++) {
      var el = sections[i];
      if (el.style.display === 'none') continue;
      if (!_CHART_GEOGRAPHIES[el.dataset.geo]) continue;
      var rect  = el.getBoundingClientRect();
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
    var prefix = 'section-' + (county || '').toLowerCase().replace(/ /g, '_') + '-';
    if (sectionElementId.indexOf(prefix) === 0) {
      return sectionElementId.slice(prefix.length);
    }
    var trimmed = sectionElementId.replace(/^section-/, '');
    var dash    = trimmed.indexOf('-');
    return dash >= 0 ? trimmed.slice(dash + 1) : trimmed;
  }

  function _updateHeaderLabel() {
    const el = document.getElementById(cfg.headerCountyLabelId);
    if (!el) return;
    if (activePrecinct && activeCounty) {
      el.textContent = activeCounty + ' County — ' + activePrecinct;
    } else {
      el.textContent = activeCounty ? activeCounty + ' County' : '';
    }
  }

  // ── Scope tabs ───────────────────────────────────────────────────────────
  function _setupScopeTabs() {
    document.addEventListener('click', function(e) {
      var tab = e.target.closest('.scope-tab');
      if (!tab) return;
      if (tab.disabled || tab.classList.contains('disabled')) return;

      var scope = tab.dataset.scope;
      activeScope = scope;

      if (scope === 'county') {
        activeGeo      = 'all';
        activePrecinct = null;
        _resetPrecinctDropdown();
      } else if (scope === 'precinct') {
        activeGeo      = activePrecinct ? 'precinct-detail' : 'precinct';
        _loadPrecinctIndex();
      } else if (scope === 'city') {
        activeGeo      = 'city';
        activePrecinct = null;
        _resetPrecinctDropdown();
      }

      _writeUrlState({ geo: activeGeo, precinct: activePrecinct });
      _syncScopeTabsToActiveScope();
      _syncGeoButtonsToActiveGeo();
      _filterSections();
      _renderVisibleSections();
      _rebuildNav();
      _updateHeaderLabel();
    });
  }

  // ── Geography filter (county sub-filter buttons) ─────────────────────────
  function _setupGeoFilter() {
    document.addEventListener('click', function(e) {
      if (!e.target.classList.contains('geo-btn')) return;
      document.querySelectorAll('.geo-btn').forEach(function(b) { b.classList.remove('active'); });
      e.target.classList.add('active');
      activeGeo = e.target.dataset.geo;

      var anchor       = _focalChartSection();
      var anchorSuffix = anchor ? _slugSuffix(anchor.id, activeCounty) : null;

      _writeUrlState({ geo: activeGeo, hash: anchorSuffix });
      _filterSections();
      _renderVisibleSections();
      _rebuildNav();

      if (anchorSuffix) {
        var newSlug = (activeCounty || '').toLowerCase().replace(/ /g, '_');
        var target  = document.getElementById('section-' + newSlug + '-' + anchorSuffix);
        if (target && target.style.display !== 'none') {
          _scrollToSuffixWhenReady(anchorSuffix);
        }
      }
    });
  }

  // ── Precinct dropdown ────────────────────────────────────────────────────
  function _resetPrecinctDropdown() {
    activePrecinct = null;
    _removePrecnctDetailSections();
    var sel = document.getElementById(cfg.precinctSelectId);
    if (sel) {
      sel.innerHTML = '<option value="">-- select precinct --</option>';
    }
  }

  async function _loadPrecinctIndex() {
    if (!activeCounty) return;
    var slug     = activeCounty.toLowerCase().replace(/ /g, '_');
    var indexUrl = 'data/' + slug + '_precinct_index.json';
    try {
      var idx = await _fetchJSON(indexUrl);
      _populatePrecinctDropdown(idx.precincts || []);
    } catch (e) {
      // No precinct index for this county yet — silently hide the dropdown
      _resetPrecinctDropdown();
    }
  }

  function _populatePrecinctDropdown(precincts) {
    var sel = document.getElementById(cfg.precinctSelectId);
    if (!sel) return;

    sel.innerHTML = '';
    var placeholder = _el('option', { value: '', textContent: '-- select precinct --' });
    sel.appendChild(placeholder);

    precincts.forEach(function(p) {
      var opt = _el('option', { value: p.name, textContent: p.name });
      sel.appendChild(opt);
    });

    // Restore active precinct if set
    if (activePrecinct) sel.value = activePrecinct;

    // Only attach once — remove old listener by replacing node
    var newSel = sel.cloneNode(true);
    sel.parentNode.replaceChild(newSel, sel);
    newSel.value = activePrecinct || '';

    newSel.addEventListener('change', function() {
      activePrecinct = newSel.value || null;
      activeGeo      = activePrecinct ? 'precinct-detail' : 'precinct';

      _writeUrlState({ geo: activeGeo, precinct: activePrecinct });
      _updateHeaderLabel();

      if (activePrecinct) {
        // Find the precinct entry from the index we already fetched
        var entry = (newSel._precinctIndex || []).find(function(p) {
          return p.name === activePrecinct;
        });
        if (entry) _injectPrecinctSections(entry);
      } else {
        _removePrecnctDetailSections();
      }

      _filterSections();
      _renderVisibleSections();
      _rebuildNav();
    });

    // Stash the index on the select element so the change handler can use it
    newSel._precinctIndex = precincts;

    // If a precinct is already active (deep-link), inject its sections now
    if (activePrecinct) {
      var entry = precincts.find(function(p) { return p.name === activePrecinct; });
      if (entry) _injectPrecinctSections(entry);
    }
  }

  function _injectPrecinctSections(entry) {
    // Remove any existing precinct-detail sections for this county first
    _removePrecnctDetailSections();

    var slug       = (activeCounty || '').toLowerCase().replace(/ /g, '_');
    var safeName   = entry.safe_name;
    var newSections = [
      {
        id:          slug + '-precinct-' + safeName + '-party',
        title:       'Party Affiliation — ' + entry.name,
        navLabel:    'Party',
        description: 'Party affiliation breakdown for this precinct.',
        county:      activeCounty,
        precinct:    entry.name,
        geography:   'precinct-detail',
        dataUrl:     entry.partyUrl,
      },
      {
        id:          slug + '-precinct-' + safeName + '-unc',
        title:       'UNC Primary History — ' + entry.name,
        navLabel:    'UNC Shadow',
        description: 'Unaffiliated voter shadow partisanship for this precinct.',
        county:      activeCounty,
        precinct:    entry.name,
        geography:   'precinct-detail',
        dataUrl:     entry.uncUrl,
      },
    ];

    // Append to manifest so _sectionVisible can match them
    newSections.forEach(function(s) { manifest.sections.push(s); });

    // Scaffold DOM sections for the new entries
    var container = document.getElementById(cfg.containerId);
    newSections.forEach(function(section) {
      var wrapper = document.createElement('section');
      wrapper.className         = 'chart-section';
      wrapper.id                = 'section-' + section.id;
      wrapper.dataset.county    = section.county;
      wrapper.dataset.geo       = section.geography;
      wrapper.dataset.precinct  = section.precinct;

      wrapper.innerHTML =
        '<div class="section-header">' +
          '<div class="section-meta">' +
            '<span class="geo-tag">' + _geoLabel(section.geography) + '</span>' +
            '<span class="county-tag">' + section.county + ' Co.</span>' +
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
  }

  function _removePrecnctDetailSections() {
    // Remove precinct-detail sections from manifest and DOM
    manifest.sections = manifest.sections.filter(function(s) {
      return s.geography !== 'precinct-detail';
    });
    document.querySelectorAll('.chart-section[data-geo="precinct-detail"]').forEach(function(el) {
      // Destroy any Chart.js instance on this section before removing
      var id = el.id.replace('section-', '');
      if (instances[id]) { try { instances[id].destroy(); } catch(e) {} delete instances[id]; }
      _renderedSections.delete(id);
      el.remove();
    });
  }

  // ── Section rendering ────────────────────────────────────────────────────
  const _renderedSections = new Set();

  function _renderAllSections() {
    const container = document.getElementById(cfg.containerId);
    container.innerHTML = '';

    manifest.sections.forEach(function(section) {
      // precinct-index sections are never rendered as chart sections
      if (section.geography === 'precinct-index') return;

      const wrapper = document.createElement('section');
      wrapper.className      = 'chart-section';
      wrapper.id             = 'section-' + section.id;
      wrapper.dataset.county = section.county;
      wrapper.dataset.geo    = section.geography;
      if (section.precinct) wrapper.dataset.precinct = section.precinct;

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

    _filterSections();
    _renderVisibleSections();
    _rebuildNav();
  }

  function _renderVisibleSections() {
    requestAnimationFrame(function() {
      manifest.sections.forEach(function(s) {
        if (s.geography === 'precinct-index') return;
        if (_renderedSections.has(s.id)) return;
        if (!_sectionVisible(s)) return;
        const el = document.getElementById('section-' + s.id);
        if (!el || el.style.display === 'none') return;
        _renderedSections.add(s.id);
        _loadAndRender(s);
      });
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
      if (s.geography === 'precinct-index') return;
      const el = document.getElementById('section-' + s.id);
      if (!el) return;
      el.style.display = _sectionVisible(s) ? '' : 'none';
    });
  }

  function _sectionVisible(s) {
    if (s.geography === 'precinct-index') return false;

    const countyMatch = s.county === activeCounty;
    if (!countyMatch) return false;

    if (activeScope === 'precinct') {
      if (activePrecinct) {
        // Show only precinct-detail sections that match the selected precinct
        return s.geography === 'precinct-detail' && s.precinct === activePrecinct;
      } else {
        // Show the precinct summary table
        return s.geography === 'precinct';
      }
    }

    if (activeScope === 'city') {
      return s.geography === 'city';
    }

    // County scope: use geo sub-filter
    const geoMatch = activeGeo === 'all' || s.geography === activeGeo;
    // In county scope, hide precinct-detail sections
    if (s.geography === 'precinct-detail') return false;
    return geoMatch;
  }

  // ── Nav ──────────────────────────────────────────────────────────────────
  function _rebuildNav() {
    const nav = document.getElementById(cfg.navId);
    if (!nav) return;
    nav.innerHTML = '';
    manifest.sections
      .filter(_sectionVisible)
      .forEach(function(s) {
        var suffix = _slugSuffix('section-' + s.id, s.county);
        nav.appendChild(_el('a', {
          href:        '#' + suffix,
          textContent: s.navLabel || s.title,
          className:   'nav-link'
        }));
      });
  }

  window.addEventListener('hashchange', function() {
    var suffix = _readHashSuffix();
    if (suffix) _scrollToSuffixWhenReady(suffix);
  });

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

    var tooltipPlugin = { mode: 'index', intersect: false };
    if (data.totalUnc) {
      var _total = data.totalUnc;
      tooltipPlugin.callbacks = {
        label: function(ctx) {
          var n   = ctx.parsed.y || 0;
          var pct = _total > 0 ? (n / _total * 100).toFixed(1) : '0.0';
          return ' ' + ctx.dataset.label + ': ' + n.toLocaleString() + ' (' + pct + '% of UNC)';
        }
      };
    }

    var chartOpts = data.chartOptions ? JSON.parse(JSON.stringify(data.chartOptions)) : {};
    if (chartOpts.plugins && chartOpts.plugins.tooltip) {
      delete chartOpts.plugins.tooltip.callbacks;
      if (Object.keys(chartOpts.plugins.tooltip).length === 0) delete chartOpts.plugins.tooltip;
      if (Object.keys(chartOpts.plugins).length === 0)         delete chartOpts.plugins;
    }

    var hasStack = !isRadial && (data.chartConfig.datasets || []).some(function(ds) {
      return ds.stack !== undefined && ds.stack !== null;
    });

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
          tooltip: tooltipPlugin
        },
        scales: isRadial ? {} : {
          x: {
            stacked: hasStack,
            ticks: { color: colors.text, maxRotation: 45 },
            grid:  { color: colors.grid }
          },
          y: {
            stacked: hasStack,
            beginAtZero: true,
            ticks: { color: colors.text, callback: function(v) { return v.toLocaleString(); } },
            grid:  { color: colors.grid }
          }
        }
      }, chartOpts)
    });
  }

  // ── Sortable, paginated table rendering ──────────────────────────────────
  var PAGE_SIZE = 50;

  function _renderTable(wrapper, data, id) {
    var sortState   = { col: null, dir: 1 };
    var currentPage = 1;
    var totalRows   = (data.rows || []).length;
    var paginate    = totalRows > PAGE_SIZE;

    var numericCols = {};
    if (data.rows && data.rows.length > 0) {
      data.rows[0].forEach(function(cell, ci) {
        var n = parseFloat(String(cell).replace(/,/g, ''));
        numericCols[ci] = !isNaN(n);
      });
    }

    function sortedRows() {
      if (sortState.col === null) return data.rows.slice();
      var col   = sortState.col;
      var dir   = sortState.dir;
      var isNum = numericCols[col];
      return data.rows.slice().sort(function(a, b) {
        var av = String(a[col]).replace(/,/g, '');
        var bv = String(b[col]).replace(/,/g, '');
        if (isNum) return dir * ((parseFloat(av) || 0) - (parseFloat(bv) || 0));
        return dir * av.localeCompare(bv);
      });
    }

    function pageRows(sorted) {
      if (!paginate) return sorted;
      var start = (currentPage - 1) * PAGE_SIZE;
      return sorted.slice(start, start + PAGE_SIZE);
    }

    function totalPages() {
      return Math.ceil(totalRows / PAGE_SIZE);
    }

    function render() {
      wrapper.innerHTML = '';
      var sorted  = sortedRows();
      var visible = pageRows(sorted);

      var scroll = _el('div', { className: 'table-scroll' });
      var table  = _el('table', { className: 'data-table' });

      var thead = document.createElement('thead');
      var hrow  = document.createElement('tr');
      data.headers.forEach(function(h, hi) {
        var indicator = (sortState.col === hi) ? (sortState.dir === 1 ? ' ▲' : ' ▼') : '';
        var th = _el('th', { textContent: h + indicator });
        th.style.cursor     = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', function() {
          if (sortState.col === hi) { sortState.dir *= -1; }
          else { sortState.col = hi; sortState.dir = numericCols[hi] ? -1 : 1; }
          currentPage = 1;
          render();
        });
        hrow.appendChild(th);
      });
      thead.appendChild(hrow);
      table.appendChild(thead);

      var tbody = document.createElement('tbody');
      visible.forEach(function(row, i) {
        var tr = _el('tr', { className: i % 2 === 0 ? 'row-even' : 'row-odd' });
        row.forEach(function(cell) { tr.appendChild(_el('td', { textContent: cell })); });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      scroll.appendChild(table);
      wrapper.appendChild(scroll);

      if (paginate) {
        var tp  = totalPages();
        var nav = _el('div', { className: 'table-pagination' });

        var btnPrev = _el('button', { textContent: '← Prev' });
        btnPrev.disabled = (currentPage === 1);
        btnPrev.addEventListener('click', function() {
          if (currentPage > 1) { currentPage--; render(); }
        });

        var btnNext = _el('button', { textContent: 'Next →' });
        btnNext.disabled = (currentPage === tp);
        btnNext.addEventListener('click', function() {
          if (currentPage < tp) { currentPage++; render(); }
        });

        var label = _el('span', {
          textContent: 'Page ' + currentPage + ' of ' + tp + ' (' + totalRows + ' precincts)',
          className: 'pagination-label'
        });

        nav.appendChild(btnPrev);
        nav.appendChild(label);
        nav.appendChild(btnNext);
        wrapper.appendChild(nav);
      }
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
      county:           'County',
      precinct:         'Precinct',
      'precinct-detail':'Precinct Detail',
      'precinct-index': 'Precinct Index',
      city:             'City / Township',
      'city-precinct':  'City Precincts',
      congressional:    'Congressional Dist.',
      all:              'Statewide'
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
