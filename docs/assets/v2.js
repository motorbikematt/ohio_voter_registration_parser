/* ============================================================
   Precincts.info V2 — Main app
   - URL state with GA-style event emission
   - Data fetching (manifest + per-jurisdiction chartConfigs)
   - Hierarchy tree (Geography ↔ Districts toggle)
   - Hero: big number + 7-cohort spark ribbon + doughnut
   - Chart cards via Chart.js (reused chartConfig from data files)
   - Hex map of 88 counties, color by party lean
   - Compare mode (two jurisdictions side-by-side)
   - Tweaks panel (style, theme, layout, density, view)
   - Chart export: JSON + PNG
   ============================================================ */
(function () {
  'use strict';

  // ── Canonical cohort colors (must match data files) ────────
  const COHORT_COLORS = ['#ef4444', '#fca5a5', '#f59e0b', '#a78bfa', '#9ca3af', '#93c5fd', '#3b82f6'];
  const COHORT_LABELS = ['Pure R', 'UNC – Lapsed R', 'Mixed – Active', 'Mixed – Lapsed', 'UNC – No Primary', 'UNC – Lapsed D', 'Pure D'];
  const PARTY_LEAN_BUCKETS = [
    { max: -0.15, color: '#ef4444', label: 'Strong R' },
    { max: -0.05, color: '#f87171', label: 'Lean R' },
    { max:  0.05, color: '#9ca3af', label: 'Mixed / UNC' },
    { max:  0.15, color: '#60a5fa', label: 'Lean D' },
    { max:  1.0,  color: '#2563eb', label: 'Strong D' }
  ];

  // ── In-memory caches ───────────────────────────────────────
  const cache = { manifest: null, byUrl: {} };
  async function fetchJSON(url) {
    if (cache.byUrl[url]) return cache.byUrl[url];
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed: ' + url);
    const data = await res.json();
    cache.byUrl[url] = data;
    return data;
  }

  // Cross-county city map: { "CITY NAME": ["county_slug", ...] }.
  // Built by the pipeline from every precinct index. Cached after first load;
  // null if absent (older deploys) so callers can fall back to single-county.
  let _cityCountyMap;
  async function loadCityCountyMap() {
    if (_cityCountyMap !== undefined) return _cityCountyMap;
    try { _cityCountyMap = await fetchJSON('data/city_county_map.json'); }
    catch (e) { _cityCountyMap = null; }
    return _cityCountyMap;
  }

  // ── URL state ──────────────────────────────────────────────
  // Old precincts.info URL params (?county=&geo=&precinct=&jurType=&jurName=)
  // get translated to the new scheme before any other code reads state, so
  // existing deep links keep working.
  function legacyShim() {
    const p = new URLSearchParams(location.search);
    // If already on new scheme, leave it alone.
    if (p.has('level') || p.has('compare')) return false;
    if (!p.has('county') && !p.has('geo') && !p.has('jurType')) return false;

    const oldCounty   = p.get('county');
    const oldGeo      = p.get('geo');
    const oldPrecinct = p.get('precinct');
    const jurType     = p.get('jurType');
    const jurName     = p.get('jurName');

    const slugify = s => String(s || '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

    const next = new URLSearchParams();
    // Preserve unrelated query params (utm_*, etc.) for GA
    p.forEach((v, k) => {
      if (!['county','geo','precinct','jurType','jurCounty','jurName'].includes(k)) next.set(k, v);
    });

    if (jurType === 'state_senate_district' || jurType === 'state_representative_district' || jurType === 'congressional_district') {
      next.set('level', 'district');
      next.set('type', jurType);
      next.set('id', String(jurName || '01').padStart(2, '0'));
    } else if (oldGeo === 'precinct-detail' || (oldGeo === 'precinct' && oldPrecinct)) {
      next.set('level', 'precinct');
      next.set('county', slugify(oldCounty || 'hamilton'));
      next.set('id', slugify(oldPrecinct || ''));
    } else if (oldCounty) {
      next.set('level', 'county');
      next.set('id', slugify(oldCounty));
    }
    history.replaceState(null, '', location.pathname + '?' + next.toString());
    return true;
  }

  function readState() {
    legacyShim();
    const p = new URLSearchParams(location.search);
    const compare = p.get('compare');
    return {
      style:   p.get('style')   || 'editorial',
      theme:   p.get('theme')   || 'dark',
      layout:  p.get('layout')  || '3col',
      density: p.get('density') || 'comfortable',
      view:    p.get('view')    || 'geo',
      level:   p.get('level')   || 'county',
      id:      p.get('id')      || 'hamilton',
      county:  p.get('county')  || null,
      district_type: p.get('type') || null,
      city:    p.get('city')    || null,
      compare: compare ? compare.split(',').slice(0, 2) : null
    };
  }
  function writeState(patch, replace) {
    const p = new URLSearchParams(location.search);
    Object.keys(patch).forEach(k => {
      const v = patch[k];
      if (v === null || v === undefined || v === '') p.delete(k);
      else p.set(k, Array.isArray(v) ? v.join(',') : String(v));
    });
    const url = location.pathname + (p.toString() ? '?' + p.toString() : '');
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
  }
  function emit(name, params) {
    // GA stub — real site replaces with gtag('event', name, params)
    if (typeof window.gtag === 'function') window.gtag('event', name, params || {});
    console.debug('[gtag]', name, params || {});
  }

  // ── State container ────────────────────────────────────────
  const S = readState();

  // ── Compare slot encoding ──────────────────────────────────
  // A slot can be a county slug (bare) or "district:<dtype>:<id>".
  // Returns { kind, id, county?, dtype? }
  function parseSlot(raw) {
    if (!raw) return null;
    const parts = String(raw).split(':');
    if (parts.length >= 3 && parts[0] === 'district') {
      return { kind: 'district', dtype: parts[1], id: parts[2] };
    }
    if (parts.length === 2 && parts[0] === 'precinct') {
      // precinct:<countySlug>:<precinctSlug>  (separator is ':' between parts[1] and parts[2])
      // For simplicity we'll require 3 parts for precinct too:
      return { kind: 'precinct', id: parts[1] };
    }
    if (parts.length >= 3 && parts[0] === 'precinct') {
      return { kind: 'precinct', county: parts[1], id: parts[2] };
    }
    return { kind: 'county', id: raw };
  }
  function slotLabel(slot) {
    if (!slot) return '—';
    if (slot.kind === 'district') {
      const t = slot.dtype.replace('_district', '').replace(/_/g, ' ');
      return t.replace(/\b\w/g, c => c.toUpperCase()) + ' D' + slot.id;
    }
    if (slot.kind === 'precinct') return (slot.id || '').toUpperCase().replace(/_/g, ' ');
    return slugToCountyName(slot.id);
  }
  function slotIsLeanable(slot) {
    return slot && slot.kind === 'county';
  }

  // ── DOM ────────────────────────────────────────────────────
  const html = document.documentElement;
  const $ = (id) => document.getElementById(id);

  function applyChrome() {
    html.dataset.style   = S.style;
    html.dataset.theme   = S.theme;
    html.dataset.layout  = S.layout;
    html.dataset.density = S.density;
    html.dataset.view    = S.view;
    html.dataset.compare = S.compare ? 'on' : 'off';
  }

  // ── Manifest helpers ───────────────────────────────────────
  function manifestCounties() {
    return cache.manifest ? (cache.manifest.processedCounties || cache.manifest.counties || []) : [];
  }
  function countyToSlug(name) {
    return String(name).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  }
  function slugToCountyName(slug) {
    const list = manifestCounties();
    const norm = slug.replace(/_/g, ' ');
    return list.find(c => c.toLowerCase() === norm.toLowerCase()) || (slug[0].toUpperCase() + slug.slice(1));
  }

  // ── Data: load all chartConfigs for a jurisdiction ─────────
  // ── City-level chart aggregation ──────────────────────────
  // Fetches all precinct-level chart JSONs for a city in parallel and sums
  // the data arrays element-wise, producing county-compatible chartConfig objects.
  async function aggregateCityCharts(countySlug, cityName, precinctIndex) {
    const upper = cityName.toUpperCase();

    // Determine which counties contain this city. The cross-county map lets a
    // city like Kettering pull its Greene-side precincts (SUGARCREEK 151 /
    // BEAVERCREEK 090) even when the tree was opened under Montgomery. Without
    // the map we fall back to the single county whose tree was clicked.
    const map = await loadCityCountyMap();
    const counties = (map && map[upper] && map[upper].length) ? map[upper] : [countySlug];

    // Load each county's precinct index (the clicked one is already in hand),
    // then collect precincts whose .city matches — tagged with their own county
    // slug so chart files are fetched from the right county's namespace.
    const indexByCounty = {};
    indexByCounty[countySlug] = precinctIndex;
    await Promise.all(counties.map(async cs => {
      if (indexByCounty[cs]) return;
      indexByCounty[cs] = await fetchJSON(`data/${cs}_precinct_index.json`).catch(() => null);
    }));

    const cityPrecincts = [];
    counties.forEach(cs => {
      const idx = indexByCounty[cs];
      const list = (idx && idx.precincts) ? idx.precincts : [];
      list.forEach(prec => {
        // Prefer the city field (SWVF CITY/RESIDENTIAL_CITY). Fall back to
        // name-prefix matching only for indexes lacking a city field.
        const match = prec.city
          ? prec.city.toUpperCase() === upper
          : (prec.name.toUpperCase() === upper || prec.name.toUpperCase().startsWith(upper + ' '));
        if (match) cityPrecincts.push({ county: cs, safe_name: prec.safe_name });
      });
    });
    if (cityPrecincts.length === 0) return {};

    // Fetch all 6 chart types for every precinct in parallel, each from its
    // own county's namespace.
    const results = await Promise.all(cityPrecincts.map(async prec => {
      const cs = prec.county;
      const ps = prec.safe_name;
      const [party, decade, gen, partyDecade, partyGen, unc] = await Promise.all([
        fetchJSON(`data/${cs}_precinct_${ps}_party.json`).catch(() => null),
        fetchJSON(`data/${cs}_precinct_${ps}_decade.json`).catch(() => null),
        fetchJSON(`data/${cs}_precinct_${ps}_generation.json`).catch(() => null),
        fetchJSON(`data/${cs}_precinct_${ps}_party_by_decade.json`).catch(() => null),
        fetchJSON(`data/${cs}_precinct_${ps}_party_by_generation.json`).catch(() => null),
        fetchJSON(`data/${cs}_precinct_${ps}_unc.json`).catch(() => null),
      ]);
      return { party, decade, gen, partyDecade, partyGen, unc };
    }));

    function sumArrays(arrays) {
      if (!arrays.length) return [];
      const len = Math.max(...arrays.map(a => a.length));
      const out = new Array(len).fill(0);
      for (const arr of arrays) for (let i = 0; i < arr.length; i++) out[i] += Number(arr[i] || 0);
      return out;
    }
    function aggSingle(key) {
      const valid = results.map(r => r[key]).filter(d => d && d.chartConfig);
      if (!valid.length) return null;
      const base = JSON.parse(JSON.stringify(valid[0].chartConfig));
      const canonLabels = base.labels;
      const arrays = valid.map(d => {
        const dLabels = d.chartConfig.labels;
        return canonLabels.map(l => {
          const idx = dLabels.indexOf(l);
          return idx >= 0 ? Number(d.chartConfig.datasets[0].data[idx] || 0) : 0;
        });
      });
      base.datasets[0].data = sumArrays(arrays);
      return { chartConfig: base };
    }
    function aggStacked(key) {
      const valid = results.map(r => r[key]).filter(d => d && d.chartConfig);
      if (!valid.length) return null;
      const base = JSON.parse(JSON.stringify(valid[0].chartConfig));
      const canonLabels = base.labels;
      base.datasets = base.datasets.map((ds, dsIdx) => {
        const arrays = valid.map(d => {
          const dLabels = d.chartConfig.labels;
          return canonLabels.map(l => {
            const idx = dLabels.indexOf(l);
            return idx >= 0 ? Number(((d.chartConfig.datasets[dsIdx] || {}).data || [])[idx] || 0) : 0;
          });
        });
        ds.data = sumArrays(arrays);
        return ds;
      });
      return { chartConfig: base };
    }
    function aggUnc() {
      const valid = results.map(r => r.unc).filter(d => d && d.chartConfig);
      if (!valid.length) return null;
      const base = JSON.parse(JSON.stringify(valid[0].chartConfig));
      base.datasets = base.datasets.map((ds, i) => {
        ds.data = [valid.reduce((acc, d) => acc + Number(((d.chartConfig.datasets[i] || {}).data || [0])[0] || 0), 0)];
        return ds;
      });
      return { chartConfig: base };
    }

    return {
      party:       aggSingle('party'),
      decade:      aggSingle('decade'),
      gen:         aggSingle('gen'),
      partyDecade: aggStacked('partyDecade'),
      partyGen:    aggStacked('partyGen'),
      uncShadow:   aggUnc(),
    };
  }

  // Returns: { total, party, decade, partyDecade, gen, partyGen, uncShadow, citySummary, precinctIndex, missing[] }
  async function loadJurisdiction(level, id, county) {
    const bag = { level, id, county, missing: [] };
    const tries = [];
    function add(key, url) { tries.push({ key, url }); }

    if (level === 'county') {
      const s = id;
      add('party',       `data/${s}_party_affiliation.json`);
      add('decade',      `data/${s}_decade_distribution.json`);
      add('gen',         `data/${s}_generation_distribution.json`);
      add('partyDecade', `data/${s}_party_by_decade.json`);
      add('partyGen',    `data/${s}_party_by_generation.json`);
      add('uncShadow',   `data/${s}_unc_shadow.json`);
      add('citySummary', `data/${s}_city_summary.json`);
      add('precinctIndex',`data/${s}_precinct_index.json`);
      add('narrative',   `data/${s}_narrative.json`);
    } else if (level === 'precinct') {
      const cs = countyToSlug(county || S.county || '');
      const ps = id;
      add('party',       `data/${cs}_precinct_${ps}_party.json`);
      add('decade',      `data/${cs}_precinct_${ps}_decade.json`);
      add('gen',         `data/${cs}_precinct_${ps}_generation.json`);
      add('partyDecade', `data/${cs}_precinct_${ps}_party_by_decade.json`);
      add('partyGen',    `data/${cs}_precinct_${ps}_party_by_generation.json`);
      add('uncShadow',   `data/${cs}_precinct_${ps}_unc.json`);
      // Narrative card: silently 404s for precincts not yet generated;
      // renderNarrative() hides the card when bag.narrative is absent.
      add('narrative',   `data/${cs}_precinct_${ps}_narrative.json`);
    } else if (level === 'city') {
      const cs = countyToSlug(county || S.id || '');
      add('citySummary',   `data/${cs}_city_summary.json`);
      add('precinctIndex', `data/${cs}_precinct_index.json`);
    } else if (level === 'district') {
      const t = S.district_type || 'state_senate_district';
      add('party',       `data/${t}/${id}_party_affiliation.json`);
      add('decade',      `data/${t}/${id}_decade_distribution.json`);
      add('partyDecade', `data/${t}/${id}_party_by_decade.json`);
      add('uncShadow',   `data/${t}/${id}_unc_shadow.json`);
      // Narrative card: partial rollout safe — card hides when file absent.
      add('narrative',   `data/${t}/${id}_narrative.json`);
    }

    await Promise.all(tries.map(async t => {
      try { bag[t.key] = await fetchJSON(t.url); }
      catch (e) { bag.missing.push(t.key); }
    }));

    // For city level, aggregate chart data from individual precinct files
    if (level === 'city' && bag.precinctIndex) {
      const cs = countyToSlug(county || S.id || '');
      const cityCharts = await aggregateCityCharts(cs, id, bag.precinctIndex);
      Object.assign(bag, cityCharts);
    }
    if (bag.party && bag.party.chartConfig) {
      bag.total = bag.party.chartConfig.datasets[0].data.reduce((a, b) => a + Number(b || 0), 0);
    }
    return bag;
  }

  // ── Hex/District map ───────────────────────────────────────
  // Districts use stylized polygons (slight per-tile jitter so they read as
  // distinct shapes, not uniform cells). Real GeoJSON/KML can swap in later.
  const DISTRICT_LAYOUTS = {
    congressional_district:        { count: 16, cols: 4,  rows: 4,  label: 'congressional districts' },
    state_senate_district:         { count: 33, cols: 6,  rows: 6,  label: 'state senate districts' },
    state_representative_district: { count: 99, cols: 10, rows: 10, label: 'state house districts' }
  };

  function partyLean(partyData) {
    if (!partyData || !partyData.chartConfig) return null;
    const d = partyData.chartConfig.datasets[0].data;
    // 7-cohort: [Pure R, Lapsed R, Mixed-A, Mixed-L, No-Primary, Lapsed D, Pure D]
    const r = (d[0] || 0) + (d[1] || 0);
    const dd = (d[5] || 0) + (d[6] || 0);
    const total = d.reduce((a, b) => a + Number(b || 0), 0) || 1;
    return (dd - r) / total;
  }
  function leanColor(lean) {
    if (lean === null || lean === undefined) return null;
    for (const b of PARTY_LEAN_BUCKETS) if (lean <= b.max) return b.color;
    return PARTY_LEAN_BUCKETS[PARTY_LEAN_BUCKETS.length - 1].color;
  }

  async function preloadCountyLean() {
    // Only loads counties whose data files exist (others stay neutral)
    const leans = {};
    const counties = manifestCounties();
    await Promise.all(counties.map(async name => {
      const slug = countyToSlug(name);
      try {
        const p = await fetchJSON(`data/${slug}_party_affiliation.json`);
        leans[name] = partyLean(p);
      } catch (e) { leans[name] = null; }
    }));
    return leans;
  }

  function renderDistrictMap(dtype, selectedId, compareIds, leans) {
    const root = $('map');
    if (!root) return;
    const layout = DISTRICT_LAYOUTS[dtype] || DISTRICT_LAYOUTS.state_senate_district;
    const { count, cols, rows } = layout;
    const cellW = 36, cellH = 30, gap = 4;
    const W = cols * (cellW + gap) + 6;
    const H = rows * (cellH + gap) + 6;
    // Deterministic jitter so each district is a visibly distinct shape.
    // Real GeoJSON/KML drops in later (per user note).
    function jit(i, k) {
      const v = Math.sin(i * 33.7 + k * 91.3) * 10000;
      return ((v - Math.floor(v)) - 0.5) * 6;
    }
    const svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" aria-label="' + layout.label + ' map">'];
    for (let i = 1; i <= count; i++) {
      const id = String(i).padStart(2, '0');
      const r = Math.floor((i - 1) / cols);
      const c = (i - 1) % cols;
      const x = c * (cellW + gap) + 3;
      const y = r * (cellH + gap) + 3;
      const pts = [
        [x + jit(i, 1),                 y + jit(i, 2)],
        [x + cellW + jit(i, 3),         y + jit(i, 4)],
        [x + cellW + jit(i, 5),         y + cellH + jit(i, 6)],
        [x + jit(i, 7),                 y + cellH + jit(i, 8)]
      ];
      const isSel = id === selectedId;
      const cmpIdx = compareIds ? compareIds.indexOf(id) : -1;
      const cls = ['hex'];
      if (isSel && cmpIdx < 0) cls.push('is-selected');
      if (cmpIdx === 0) cls.push('is-compare-a');
      if (cmpIdx === 1) cls.push('is-compare-b');
      const lean = leans ? leans[id] : null;
      const fill = leanColor(lean) || 'var(--surface-3)';
      const d = 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('L') + 'Z';
      svg.push('<path class="' + cls.join(' ') + '" d="' + d + '" fill="' + fill + '" stroke="var(--rule)" stroke-width="0.7" data-district="' + id + '" data-dtype="' + dtype + '"><title>District ' + id + (lean !== null ? ' · ' + (lean > 0 ? '+' : '') + (lean * 100).toFixed(1) + '% D−R' : '') + '</title></path>');
      if (count <= 33 || isSel || cmpIdx >= 0) {
        svg.push('<text class="hex-label" x="' + (x + cellW / 2).toFixed(1) + '" y="' + (y + cellH / 2).toFixed(1) + '" style="font-size:8px">' + id + '</text>');
      }
    }
    svg.push('</svg>');
    root.innerHTML = svg.join('');
    root.querySelectorAll('[data-district]').forEach(el => {
      el.addEventListener('click', () => {
        selectDistrict(el.getAttribute('data-dtype'), el.getAttribute('data-district'));
      });
    });
  }

  async function preloadDistrictLean(dtype) {
    const layout = DISTRICT_LAYOUTS[dtype];
    if (!layout) return {};
    const leans = {};
    await Promise.all(Array.from({ length: layout.count }, (_, k) => k + 1).map(async n => {
      const id = String(n).padStart(2, '0');
      try {
        const p = await fetchJSON('data/' + dtype + '/' + id + '_party_affiliation.json');
        leans[id] = partyLean(p);
      } catch (e) { leans[id] = null; }
    }));
    return leans;
  }

  async function selectDistrict(dtype, id) {
    if (S.compare) {
      const arr = S.compare.slice();
      const slot = window._focusedSlot === 'b' ? 1 : 0;
      arr[slot] = 'district:' + dtype + ':' + id;
      S.compare = arr;
      writeState({ compare: arr });
      emit('compare_update', { slot: slot === 0 ? 'a' : 'b', value: arr[slot] });
    } else {
      S.level = 'district'; S.id = id; S.district_type = dtype;
      writeState({ level: 'district', id, type: dtype });
      emit('select_jurisdiction', { level: 'district', type: dtype, id });
    }
    await refreshView();
  }

  function renderHexMap(leans, selectedName, compareNames) {
    const root = $('map');
    if (!root) return;
    const hexW = 32, hexH = 28;          // flat-top hex spacing
    const cols = 12, rows = 12;
    const W = cols * hexW + hexW;
    const H = rows * hexH + hexH;
    const hexPath = (cx, cy, r) => {
      const pts = [];
      for (let i = 0; i < 6; i++) {
        const a = Math.PI / 3 * i - Math.PI / 6;
        pts.push((cx + r * Math.cos(a)).toFixed(1) + ',' + (cy + r * Math.sin(a)).toFixed(1));
      }
      return 'M' + pts.join('L') + 'Z';
    };
    const svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" aria-label="Ohio counties hex map">'];
    window.OHIO_HEX.forEach(([name, col, row]) => {
      const cx = col * hexW + (row % 2 === 0 ? hexW / 2 : 0) + hexW / 2;
      const cy = row * hexH + hexH / 2 + 4;
      const lean = leans ? leans[name] : null;
      const color = leanColor(lean);
      const fill = color || 'var(--surface-3)';
      const isSel = name === selectedName;
      const compareIdx = compareNames ? compareNames.indexOf(name) : -1;
      const cls = ['hex'];
      if (isSel && compareIdx < 0) cls.push('is-selected');
      if (compareIdx === 0) cls.push('is-compare-a');
      if (compareIdx === 1) cls.push('is-compare-b');
      svg.push(
        '<path class="' + cls.join(' ') + '" d="' + hexPath(cx, cy, hexW * 0.52) + '" fill="' + fill + '" ' +
        'stroke="var(--rule)" stroke-width="0.6" data-county="' + name + '"><title>' + name + (lean !== null ? ' · ' + (lean > 0 ? '+' : '') + (lean * 100).toFixed(1) + '% D−R' : ' · data pending') + '</title></path>'
      );
      // Label only for big counties or selected
      const isMajor = name === 'Hamilton' || name === 'Franklin' || name === 'Cuyahoga' || isSel;
      if (isMajor) {
        svg.push('<text class="hex-label" x="' + cx + '" y="' + cy + '">' + name.slice(0, 3).toUpperCase() + '</text>');
      }
    });
    svg.push('</svg>');
    root.innerHTML = svg.join('');
    root.querySelectorAll('.hex').forEach(el => {
      el.addEventListener('click', () => {
        const cname = el.getAttribute('data-county');
        selectCounty(cname);
      });
    });
  }

  function renderMapSelection(bag) {
    const root = $('map-selection');
    if (!root) return;
    if (!bag) { root.innerHTML = '<span class="eyebrow">Selection</span><div class="mname muted">—</div>'; return; }
    const name = bag.displayName || bag.id;
    const totalFmt = bag.total != null ? bag.total.toLocaleString() : '—';
    let leanText = '', leanBars = '';
    if (bag.party && bag.party.chartConfig) {
      const data = bag.party.chartConfig.datasets[0].data;
      const total = bag.total || 1;
      const r = data[0] + data[1], dd = data[5] + data[6], unc = data[2] + data[3] + data[4];
      const leanPct = ((dd - r) / total * 100);
      leanText = (leanPct > 0 ? '+' : '') + leanPct.toFixed(1) + '% D−R · UNC ' + (unc / total * 100).toFixed(0) + '%';
      const segR = (r / total * 100).toFixed(1);
      const segU = (unc / total * 100).toFixed(1);
      const segD = (dd / total * 100).toFixed(1);
      leanBars = '<div class="mlean">' +
        '<div class="mlean-seg" style="width:' + segR + '%;background:var(--c-rep)"></div>' +
        '<div class="mlean-seg" style="width:' + segU + '%;background:var(--c-unc)"></div>' +
        '<div class="mlean-seg" style="width:' + segD + '%;background:var(--c-dem)"></div>' +
      '</div>';
    }
    root.innerHTML =
      '<span class="eyebrow">Selection</span>' +
      '<div class="mname">' + name + '</div>' +
      '<div class="mstat">' + totalFmt + ' registered · ' + leanText + '</div>' +
      leanBars;
  }

  // ── Hierarchy tree ─────────────────────────────────────────
  async function renderHierarchy() {
    const root = $('hierarchy');
    if (!root) return;
    root.innerHTML = '';

    if (S.view === 'geo') {
      const counties = manifestCounties();
      const html = ['<div class="hier-section">',
        '<span class="eyebrow">Statewide</span>',
        '<div class="hier-row depth-0" data-action="select-state"><span class="twirl"></span><span class="label">Ohio</span><span class="count">' + counties.length + '</span></div>',
        '</div>',
        '<div class="hier-section"><span class="eyebrow">Counties (88)</span>'];
      counties.forEach(c => {
        const slug = countyToSlug(c);
        const isSel = S.level === 'county' && S.id === slug;
        const isExpanded = isSel ||
          (S.level === 'city' && S.id === slug) ||
          (S.level === 'precinct' && countyToSlug(S.county || '') === slug);
        html.push('<div class="hier-row depth-0 ' + (isSel ? 'is-selected' : '') + '" data-action="select-county" data-county="' + slug + '" data-county-name="' + c + '"><span class="twirl">▸</span><span class="label">' + c + '</span><span class="count">—</span></div>');
        if (isExpanded) {
          html.push('<div class="hier-children is-open" data-county-children="' + slug + '"></div>');
        }
      });
      html.push('</div>');
      root.innerHTML = html.join('');

      // If a county is open, lazy-load its city/precinct list
      if (S.level === 'county' || S.level === 'precinct' || S.level === 'city') {
        const cs = S.level === 'precinct' ? countyToSlug(S.county || '') : S.id;
        await populateCountyChildren(cs);
      }
    } else {
      // Districts view
      const html = [
        '<div class="hier-section"><span class="eyebrow">Federal</span>',
        '<div class="hier-row depth-0 ' + (S.district_type === 'congressional_district' ? 'is-open' : '') + '" data-action="toggle-dtype" data-dtype="congressional_district"><span class="twirl">▸</span><span class="label">Congressional</span><span class="count">16</span></div>',
        '<div class="hier-children ' + (S.district_type === 'congressional_district' ? 'is-open' : '') + '" data-dtype-children="congressional_district"></div>',
        '</div>',
        '<div class="hier-section"><span class="eyebrow">State</span>',
        '<div class="hier-row depth-0 ' + (S.district_type === 'state_senate_district' ? 'is-open' : '') + '" data-action="toggle-dtype" data-dtype="state_senate_district"><span class="twirl">▸</span><span class="label">State Senate</span><span class="count">33</span></div>',
        '<div class="hier-children ' + (S.district_type === 'state_senate_district' ? 'is-open' : '') + '" data-dtype-children="state_senate_district"></div>',
        '<div class="hier-row depth-0 ' + (S.district_type === 'state_representative_district' ? 'is-open' : '') + '" data-action="toggle-dtype" data-dtype="state_representative_district"><span class="twirl">▸</span><span class="label">State House</span><span class="count">99</span></div>',
        '<div class="hier-children ' + (S.district_type === 'state_representative_district' ? 'is-open' : '') + '" data-dtype-children="state_representative_district"></div>',
        '</div>'
      ];
      root.innerHTML = html.join('');
      if (S.district_type) await populateDistrictChildren(S.district_type);
    }
    wireHierarchyEvents();
  }

  async function populateCountyChildren(countySlug) {
    const wrap = document.querySelector('[data-county-children="' + countySlug + '"]');
    if (!wrap) return;
    wrap.innerHTML = '<div class="hier-row depth-1 muted"><span class="label">Loading…</span></div>';

    const [citySum, precIdx] = await Promise.all([
      fetchJSON('data/' + countySlug + '_city_summary.json').catch(() => null),
      fetchJSON('data/' + countySlug + '_precinct_index.json').catch(() => null)
    ]);

    const cities = (citySum && citySum.rows)
      ? citySum.rows.map(r => ({ name: r[1], total: r[4], precinctCount: Number(r[5]) || 0 }))
      : [];
    const precincts = (precIdx && precIdx.precincts) ? precIdx.precincts : [];

    if (cities.length === 0 && precincts.length === 0) {
      wrap.innerHTML = '<div class="hier-row depth-1 muted"><span class="label">Not yet processed</span></div>';
      return;
    }

    // Group precincts under cities by the per-precinct `city` field (from the
    // SWVF CITY/RESIDENTIAL_CITY column). This is authoritative and correctly
    // handles precincts whose NAME does not contain the city (e.g. Greene's
    // SUGARCREEK 151 belongs to Kettering). Fall back to longest-prefix-match
    // on name only for precincts lacking a city field.
    const cityByUpper = {};
    cities.forEach(c => { cityByUpper[c.name.toUpperCase()] = c.name; });
    const citiesByLen = cities.slice().sort((a, b) => b.name.length - a.name.length);
    const buckets = {};
    const orphans = [];
    precincts.forEach(p => {
      let matched = null;
      const pcity = (p.city || '').toUpperCase();
      if (pcity && cityByUpper[pcity]) {
        matched = cityByUpper[pcity];
      } else if (!p.city) {
        const upper = p.name.toUpperCase();
        for (const c of citiesByLen) {
          const cn = c.name.toUpperCase();
          if (upper === cn || upper.startsWith(cn + ' ') || upper.startsWith(cn)) { matched = c.name; break; }
        }
      }
      if (matched) (buckets[matched] = buckets[matched] || []).push(p);
      else orphans.push(p);
    });

    // Sort cities by total registered (descending) for display.
    const parseTotal = (s) => Number(String(s).replace(/,/g, '')) || 0;
    const ordered = cities.slice().sort((a, b) => parseTotal(b.total) - parseTotal(a.total));

    const html = [];
    ordered.forEach(c => {
      const cityPrecincts = buckets[c.name] || [];
      if (cityPrecincts.length === 0) return;
      const ck = countySlug + '_' + c.name.toLowerCase().replace(/[^a-z0-9]+/g, '_');
      const isCitySel = S.level === 'city' && S.city === c.name;
      html.push(
        '<div class="hier-row depth-1 ' + (isCitySel ? 'is-selected' : '') + '" data-action="toggle-city" data-city-key="' + ck + '" data-city-name="' + c.name + '" data-county="' + countySlug + '">' +
          '<span class="twirl">▸</span>' +
          '<span class="label">' + c.name + '</span>' +
          '<span class="count">' + cityPrecincts.length + '</span>' +
        '</div>',
        '<div class="hier-children" data-city-children="' + ck + '">'
      );
      cityPrecincts.forEach(p => {
        const isSel = S.level === 'precinct' && S.id === p.safe_name;
        html.push(
          '<div class="hier-row depth-2 ' + (isSel ? 'is-selected' : '') + '" data-action="select-precinct" data-county="' + countySlug + '" data-precinct="' + p.safe_name + '" data-precinct-name="' + p.name + '">' +
            '<span class="twirl"></span>' +
            '<span class="label">' + p.name + '</span>' +
            '<span class="count">' + (p.total ? p.total.toLocaleString() : '—') + '</span>' +
          '</div>'
        );
      });
      html.push('</div>');
    });

    if (orphans.length > 0) {
      const ck = countySlug + '_other';
      html.push(
        '<div class="hier-row depth-1" data-action="toggle-city" data-city-key="' + ck + '">' +
          '<span class="twirl">▸</span><span class="label muted">Other precincts</span>' +
          '<span class="count">' + orphans.length + '</span>' +
        '</div>',
        '<div class="hier-children" data-city-children="' + ck + '">'
      );
      orphans.slice(0, 40).forEach(p => {
        const isSel = S.level === 'precinct' && S.id === p.safe_name;
        html.push(
          '<div class="hier-row depth-2 ' + (isSel ? 'is-selected' : '') + '" data-action="select-precinct" data-county="' + countySlug + '" data-precinct="' + p.safe_name + '" data-precinct-name="' + p.name + '">' +
            '<span class="twirl"></span><span class="label">' + p.name + '</span>' +
            '<span class="count">' + (p.total ? p.total.toLocaleString() : '—') + '</span>' +
          '</div>'
        );
      });
      if (orphans.length > 40) html.push('<div class="hier-row depth-2 muted"><span class="label">+ ' + (orphans.length - 40) + ' more</span></div>');
      html.push('</div>');
    }

    wrap.innerHTML = html.join('');

    // Toggle handlers on city rows: expand tree AND navigate to city view
    wrap.querySelectorAll('[data-action="toggle-city"]').forEach(el => {
      el.onclick = async (e) => {
        e.stopPropagation();
        const key = el.getAttribute('data-city-key');
        const cityName = el.getAttribute('data-city-name');
        const cs = el.getAttribute('data-county');
        const isOpen = el.classList.toggle('is-open');
        const children = wrap.querySelector('[data-city-children="' + key + '"]');
        if (children) children.classList.toggle('is-open', isOpen);
        // Navigate to city view for named cities (not 'Other precincts')
        if (cityName && cs) {
          wrap.querySelectorAll('[data-action="toggle-city"].is-selected').forEach(r => r.classList.remove('is-selected'));
          el.classList.add('is-selected');
          S.level = 'city'; S.city = cityName; S.id = cs; S.county = cs;
          writeState({ level: 'city', city: cityName, id: cs, county: cs, type: null });
          emit('select_jurisdiction', { level: 'city', city: cityName, county: cs });
          await refreshView();
        }
      };
    });

    // Wire precinct click handlers (depth-2 rows are excluded from wireHierarchyEvents)
    wrap.querySelectorAll('[data-action="select-precinct"]').forEach(el => {
      el.onclick = async (e) => {
        e.stopPropagation();
        const county = el.getAttribute('data-county');
        const precinct = el.getAttribute('data-precinct');
        const name = el.getAttribute('data-precinct-name');
        S.level = 'precinct'; S.id = precinct; S.county = county; S.city = null;
        writeState({ level: 'precinct', id: precinct, county: county, city: null, type: null });
        emit('select_jurisdiction', { level: 'precinct', id: precinct, county, name });
        await refreshView();
      };
    });

    // Auto-expand the city that contains the currently-selected precinct
    if (S.level === 'precinct') {
      const selRow = wrap.querySelector('.hier-row.depth-2.is-selected');
      if (selRow) {
        const ch = selRow.parentNode;
        const key = ch.getAttribute('data-city-children');
        const toggle = wrap.querySelector('[data-city-key="' + key + '"]');
        if (toggle) {
          toggle.classList.add('is-open');
          ch.classList.add('is-open');
        }
      }
    }
    // Auto-expand the active city when at city view
    if (S.level === 'city' && S.city) {
      const cityKey = countySlug + '_' + S.city.toLowerCase().replace(/[^a-z0-9]+/g, '_');
      const cityRow = wrap.querySelector('[data-city-key="' + cityKey + '"]');
      const cityChildren = wrap.querySelector('[data-city-children="' + cityKey + '"]');
      if (cityRow && !cityRow.classList.contains('is-open')) { cityRow.classList.add('is-open'); }
      if (cityChildren) cityChildren.classList.add('is-open');
    }
  }

  async function populateDistrictChildren(dtype) {
    const wrap = document.querySelector('[data-dtype-children="' + dtype + '"]');
    if (!wrap) return;
    wrap.innerHTML = '<div class="hier-row depth-1 muted"><span class="label">Loading…</span></div>';
    try {
      const idx = await fetchJSON(`data/${dtype}/index.json`);
      const list = Array.isArray(idx) ? idx : (idx.districts || []);
      const html = list.map(d => {
        const isSel = S.level === 'district' && S.district_type === dtype && S.id === d.slug;
        const label = d.display_name || d.name || d.slug;
        return '<div class="hier-row depth-1 ' + (isSel ? 'is-selected' : '') + '" data-action="select-district" data-dtype="' + dtype + '" data-id="' + d.slug + '" data-district-name="' + label + '"><span class="twirl"></span><span class="label">District ' + label + '</span><span class="count">' + (d.voter_count ? d.voter_count.toLocaleString() : '—') + '</span></div>';
      });
      wrap.innerHTML = html.join('');
    } catch (e) {
      wrap.innerHTML = '<div class="hier-row depth-1 muted"><span class="label">Not yet processed</span></div>';
    }
  }

  function wireHierarchyEvents() {
    document.querySelectorAll('[data-action]').forEach(el => {
      // Skip rows whose handlers are owned by populateCountyChildren
      // (city toggles + precincts under cities). Otherwise this would
      // overwrite their onclick and the tree expansion would die silently.
      const action = el.getAttribute('data-action');
      if (action === 'toggle-city') return;
      if (action === 'select-precinct' && el.classList.contains('depth-2')) return;
      el.onclick = async () => {
        if (action === 'select-state') {
          // No state-level data file exists for all 88; just zoom out the breadcrumb
          S.level = 'county'; S.id = 'hamilton'; S.county = null;
          writeState({ level: 'county', id: 'hamilton', compare: null, county: null });
          emit('select_jurisdiction', { level: 'state', id: 'ohio' });
        } else if (action === 'select-county') {
          const slug = el.getAttribute('data-county');
          const name = el.getAttribute('data-county-name');
          S.level = 'county'; S.id = slug; S.county = null; S.district_type = null;
          writeState({ level: 'county', id: slug, county: null, type: null });
          emit('select_jurisdiction', { level: 'county', id: slug, name });
        } else if (action === 'select-precinct') {
          const county = el.getAttribute('data-county');
          const precinct = el.getAttribute('data-precinct');
          const name = el.getAttribute('data-precinct-name');
          S.level = 'precinct'; S.id = precinct; S.county = county;
          writeState({ level: 'precinct', id: precinct, county: county });
          emit('select_jurisdiction', { level: 'precinct', id: precinct, county, name });
        } else if (action === 'toggle-dtype') {
          const dtype = el.getAttribute('data-dtype');
          S.district_type = S.district_type === dtype ? null : dtype;
          await renderHierarchy();
          return;
        } else if (action === 'select-district') {
          const dtype = el.getAttribute('data-dtype');
          const id = el.getAttribute('data-id');
          const name = el.getAttribute('data-district-name');
          S.level = 'district'; S.id = id; S.district_type = dtype;
          writeState({ level: 'district', id, type: dtype });
          emit('select_jurisdiction', { level: 'district', type: dtype, id, name });
        }
        await refreshView();
      };
    });
  }

  // ── Selection drivers ──────────────────────────────────────
  async function selectCounty(name) {
    const slug = countyToSlug(name);
    if (S.compare) {
      const slot = window._focusedSlot === 'b' ? 1 : 0;
      const arr = S.compare.slice();
      arr[slot] = slug;
      S.compare = arr;
      writeState({ compare: arr });
      emit('compare_update', { slot: slot === 0 ? 'a' : 'b', id: slug, name });
    } else {
      S.level = 'county'; S.id = slug; S.county = null; S.district_type = null;
      writeState({ level: 'county', id: slug, county: null, type: null });
      emit('select_jurisdiction', { level: 'county', id: slug, name });
    }
    await refreshView();
  }

  // ── Charts ─────────────────────────────────────────────────
  const chartInstances = {};
  function destroyAll() {
    Object.keys(chartInstances).forEach(k => {
      try { chartInstances[k].destroy(); } catch (e) {}
      delete chartInstances[k];
    });
  }
  function destroyChart(key) {
    if (chartInstances[key]) {
      try { chartInstances[key].destroy(); } catch (e) {}
      delete chartInstances[key];
    }
  }

  function commonOptions() {
    const cs = getComputedStyle(html);
    const ink = cs.getPropertyValue('--ink').trim();
    const muted = cs.getPropertyValue('--muted').trim();
    const rule = cs.getPropertyValue('--rule').trim();
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: cs.getPropertyValue('--surface').trim(),
          titleColor: ink,
          bodyColor: ink,
          borderColor: rule,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 6,
          titleFont: { weight: '500' },
          bodyFont: { size: 12 }
        }
      },
      scales: {
        x: { ticks: { color: muted, font: { size: 10 } }, grid: { color: rule, drawTicks: false }, border: { color: rule } },
        y: { ticks: { color: muted, font: { size: 10 } }, grid: { color: rule, drawTicks: false }, border: { color: rule }, beginAtZero: true }
      }
    };
  }

  function renderChart(canvasId, type, dataObj, opts) {
    destroyChart(canvasId);
    const c = $(canvasId);
    if (!c) return;
    const base = commonOptions();
    const merged = JSON.parse(JSON.stringify(base));
    if (type === 'doughnut') {
      merged.scales = undefined;
      merged.cutout = '60%';
    }
    if (opts && opts.stacked) {
      merged.scales.x.stacked = true;
      merged.scales.y.stacked = true;
    }
    if (opts && opts.percentY) {
      merged.scales.y.max = 100;
      merged.scales.y.ticks.callback = (v) => v + '%';
    }
    chartInstances[canvasId] = new Chart(c.getContext('2d'), {
      type,
      data: dataObj,
      options: merged
    });
  }

  function renderHero(container, bag) {
    if (bag && bag.level === 'city') {
      const cityRow = bag.citySummary && bag.citySummary.rows
        ? bag.citySummary.rows.find(r => r[1] === bag.displayName) : null;
      const precinctCount = cityRow ? cityRow[5] : '?';
      if (bag.party && bag.party.chartConfig) {
        // Full hero with ribbon (same layout as county)
        const labels = bag.party.chartConfig.labels.map(l => String(l).split(' \u2014 ')[0]);
        const data   = bag.party.chartConfig.datasets[0].data;
        const colors = bag.party.chartConfig.datasets[0].backgroundColor || COHORT_COLORS;
        const total  = data.reduce((a, b) => a + Number(b || 0), 0);
        const r   = data[0] + data[1];
        const unc = data[2] + data[3] + data[4];
        const dd  = data[5] + data[6];
        container.innerHTML =
          '<div class="hero-headline">' +
            '<div class="eyebrow">Total registered voters</div>' +
            '<div class="hero-number">' + total.toLocaleString() + '</div>' +
            '<div class="hero-subtitle">' +
              bag.displayName + ' \u00b7 ' + precinctCount + ' precincts \u00b7 ' +
              '<b>' + (r / total * 100).toFixed(1) + '%</b> Republican-leaning, ' +
              '<b>' + (unc / total * 100).toFixed(1) + '%</b> unaffiliated, ' +
              '<b>' + (dd / total * 100).toFixed(1) + '%</b> Democratic-leaning' +
            '</div>' +
          '</div>' +
          '<div class="hero-ribbon-wrap">' +
            '<div class="hero-ribbon-label"><span>7-cohort partisan spectrum</span></div>' +
            '<div class="hero-ribbon">' + labels.map((l, i) => {
              const pct = (data[i] / total * 100).toFixed(2);
              return '<div class="hero-ribbon-seg" style="width:' + pct + '%;background:' + colors[i] + '" title="' + l + ': ' + data[i].toLocaleString() + ' (' + pct + '%)"></div>';
            }).join('') + '</div>' +
            '<div class="hero-legend">' + labels.map((l, i) => {
              return '<div class="legend-item"><span class="sw" style="background:' + colors[i] + '"></span><span class="lbl">' + l + '</span><span class="val">' + (data[i] / total * 100).toFixed(1) + '%</span></div>';
            }).join('') + '</div>' +
          '</div>';
      } else if (cityRow) {
        container.innerHTML =
          '<div class="hero-headline">' +
            '<div class="eyebrow">Total registered voters</div>' +
            '<div class="hero-number">' + cityRow[4] + '</div>' +
            '<div class="hero-subtitle">' + bag.displayName + ' \u00b7 ' +
              precinctCount + ' precincts \u00b7 ' +
              cityRow[2] + ' active, ' + cityRow[3] + ' confirmation' +
            '</div>' +
          '</div>' +
          '<div class="hero-ribbon-wrap">' +
            '<div class="hero-ribbon-label"><span>Aggregating precinct data\u2026</span></div>' +
          '</div>';
      } else {
        container.innerHTML = '<div class="hero-headline"><div class="eyebrow">' + bag.displayName + '</div><div class="hero-number">\u2014</div><div class="hero-subtitle muted">No summary data found.</div></div><div></div>';
      }
      return;
    }
    if (!bag || !bag.party || !bag.party.chartConfig) {
      container.innerHTML = '<div class="hero-headline"><div class="eyebrow">Total registered voters</div><div class="hero-number">—</div><div class="hero-subtitle muted">Data has not yet been processed for this jurisdiction.</div></div><div></div>';
      return;
    }
    const labels = bag.party.chartConfig.labels.map(l => String(l).split(' — ')[0]);
    const data = bag.party.chartConfig.datasets[0].data;
    const colors = bag.party.chartConfig.datasets[0].backgroundColor || COHORT_COLORS;
    const total = bag.total || data.reduce((a, b) => a + Number(b || 0), 0);
    const r = data[0] + data[1];
    const unc = data[2] + data[3] + data[4];
    const dd = data[5] + data[6];

    container.innerHTML = '' +
      '<div class="hero-headline">' +
        '<div class="eyebrow">Total registered voters</div>' +
        '<div class="hero-number">' + total.toLocaleString() + '</div>' +
        '<div class="hero-subtitle">' +
          bag.displayName + ' · ' +
          '<b>' + (r / total * 100).toFixed(1) + '%</b> Republican-leaning, ' +
          '<b>' + (unc / total * 100).toFixed(1) + '%</b> unaffiliated, ' +
          '<b>' + (dd / total * 100).toFixed(1) + '%</b> Democratic-leaning' +
        '</div>' +
      '</div>' +
      '<div class="hero-ribbon-wrap">' +
        '<div class="hero-ribbon-label"><span>7-cohort partisan spectrum</span><span class="mono">' + (bag.party.updated || '') + '</span></div>' +
        '<div class="hero-ribbon">' + labels.map((l, i) => {
          const pct = (data[i] / total * 100).toFixed(2);
          return '<div class="hero-ribbon-seg" style="width:' + pct + '%;background:' + colors[i] + '" title="' + l + ': ' + data[i].toLocaleString() + ' (' + pct + '%)"></div>';
        }).join('') + '</div>' +
        '<div class="hero-legend">' + labels.map((l, i) => {
          return '<div class="legend-item"><span class="sw" style="background:' + colors[i] + '"></span><span class="lbl">' + l + '</span><span class="val">' + (data[i] / total * 100).toFixed(1) + '%</span></div>';
        }).join('') + '</div>' +
      '</div>';
  }

  function renderDoughnutCard(bag) {
    if (!bag.party || !bag.party.chartConfig) { setPlaceholder('chart-party-wrap', 'No party data'); return; }
    renderChart('chart-party', 'doughnut', bag.party.chartConfig);
    // inline legend
    const lg = $('chart-party-legend');
    if (lg) {
      const labels = bag.party.chartConfig.labels.map(l => String(l).split(' — ')[0]);
      const data = bag.party.chartConfig.datasets[0].data;
      const colors = bag.party.chartConfig.datasets[0].backgroundColor || COHORT_COLORS;
      const total = data.reduce((a, b) => a + Number(b || 0), 0);
      lg.innerHTML = labels.map((l, i) =>
        '<div class="legend-item"><span class="sw" style="background:' + colors[i] + '"></span><span class="lbl">' + l + '</span><span class="val">' + data[i].toLocaleString() + '</span></div>'
      ).join('');
    }
  }
  function setPlaceholder(wrapId, msg) {
    const w = $(wrapId);
    if (w) w.innerHTML = '<div class="placeholder">' + msg + '</div>';
  }
  function ensureCanvas(wrapId, canvasId) {
    const w = $(wrapId);
    if (!w) return;
    w.innerHTML = '<canvas id="' + canvasId + '"></canvas>';
  }

  function renderCharts(bag) {
    // Doughnut + legend
    if (bag.party && bag.party.chartConfig) {
      ensureCanvas('chart-party-wrap', 'chart-party');
      renderDoughnutCard(bag);
    } else { setPlaceholder('chart-party-wrap', 'Party data not yet processed'); }

    if (bag.decade && bag.decade.chartConfig) {
      ensureCanvas('chart-decade-wrap', 'chart-decade');
      renderChart('chart-decade', 'bar', bag.decade.chartConfig);
    } else { setPlaceholder('chart-decade-wrap', 'Decade data not yet processed'); }

    if (bag.partyDecade && bag.partyDecade.chartConfig) {
      ensureCanvas('chart-party-decade-wrap', 'chart-party-decade');
      renderChart('chart-party-decade', 'bar', bag.partyDecade.chartConfig, { stacked: true });
    } else { setPlaceholder('chart-party-decade-wrap', 'Party × decade not yet processed'); }

    if (bag.gen && bag.gen.chartConfig) {
      ensureCanvas('chart-gen-wrap', 'chart-gen');
      renderChart('chart-gen', 'bar', bag.gen.chartConfig);
    } else { setPlaceholder('chart-gen-wrap', 'Generation data not yet processed for this scope'); }

    if (bag.partyGen && bag.partyGen.chartConfig) {
      ensureCanvas('chart-party-gen-wrap', 'chart-party-gen');
      renderChart('chart-party-gen', 'bar', bag.partyGen.chartConfig, { stacked: true });
    } else { setPlaceholder('chart-party-gen-wrap', 'Party × generation not yet processed for this scope'); }

    if (bag.uncShadow && bag.uncShadow.chartConfig) {
      ensureCanvas('chart-unc-wrap', 'chart-unc');
      renderChart('chart-unc', 'bar', bag.uncShadow.chartConfig, { stacked: true });
    } else { setPlaceholder('chart-unc-wrap', 'UNC shadow not yet processed'); }

    if (bag.level === 'city') {
      setPlaceholder('city-table-wrap', 'Precinct-level charts above \u2014 select a precinct for detailed data');
    } else if (bag.citySummary && bag.citySummary.rows) {
      renderTable($('city-table-wrap'), bag.citySummary);
    } else if ($('city-table-wrap')) {
      setPlaceholder('city-table-wrap', S.level === 'county' ? 'City/township summary not yet processed' : 'Not applicable at this scope');
    }
  }

  // Sortable table for citySummary
  const tableState = { sortKey: null, sortDir: 'desc' };
  function renderTable(wrap, ds) {
    if (!wrap || !ds.rows) return;
    const headers = ds.headers || [];
    function parseNum(s) { return Number(String(s).replace(/,/g, '')); }
    let rows = ds.rows.slice();
    if (tableState.sortKey !== null) {
      const idx = tableState.sortKey;
      rows.sort((a, b) => {
        const av = a[idx], bv = b[idx];
        const an = parseNum(av), bn = parseNum(bv);
        const numeric = !isNaN(an) && !isNaN(bn);
        if (numeric) return tableState.sortDir === 'asc' ? an - bn : bn - an;
        return tableState.sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      });
    }
    const ths = headers.map((h, i) => {
      const isAct = tableState.sortKey === i;
      const ind = isAct ? (tableState.sortDir === 'asc' ? '▲' : '▼') : '↕';
      return '<th data-col="' + i + '" class="' + (isAct ? 'sort-active' : '') + '">' + h + '<span class="sort-ind">' + ind + '</span></th>';
    }).join('');
    const tbody = rows.map(r =>
      '<tr>' + r.map((c, i) => '<td>' + c + '</td>').join('') + '</tr>'
    ).join('');
    wrap.innerHTML = '<table class="data-table"><thead><tr>' + ths + '</tr></thead><tbody>' + tbody + '</tbody></table>';
    wrap.querySelectorAll('th[data-col]').forEach(th => {
      th.onclick = () => {
        const col = Number(th.getAttribute('data-col'));
        if (tableState.sortKey === col) {
          tableState.sortDir = tableState.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          tableState.sortKey = col;
          tableState.sortDir = 'desc';
        }
        renderTable(wrap, ds);
      };
    });
  }

  // ── Narrative card ─────────────────────────────────────────
  function renderNarrative(bag) {
    const el = $('narrative-card');
    if (!el) return;
    if (!bag || !bag.narrative || !bag.narrative.narrative) {
      el.style.display = 'none';
      return;
    }
    el.style.display = '';
    el.innerHTML =
      '<div class="eyebrow" style="margin-bottom:6px">Jurisdiction overview</div>' +
      '<p class="narrative-text">' + bag.narrative.narrative + '</p>' +
      '<div class="narrative-meta">Data as of ' + (bag.narrative.updated || '') +
      ' &middot; generated by ' + (bag.narrative.generated_by || 'AI') + '</div>';
  }

  // ── Breadcrumb ─────────────────────────────────────────────
  function renderBreadcrumb(bag) {
    const root = $('breadcrumb');
    if (!root) return;
    const parts = [{ label: 'Ohio', action: 'state' }];
    if (bag.level === 'county') {
      parts.push({ label: bag.displayName, here: true });
    } else if (bag.level === 'city') {
      parts.push({ label: slugToCountyName(bag.county || S.id || ''), action: 'county', county: bag.county || S.id });
      parts.push({ label: bag.displayName, here: true });
    } else if (bag.level === 'precinct') {
      parts.push({ label: slugToCountyName(bag.county), action: 'county', county: bag.county });
      parts.push({ label: bag.displayName, here: true });
    } else if (bag.level === 'district') {
      parts.push({ label: (S.district_type || '').replace(/_/g, ' ').replace('district', '').trim().replace(/\b\w/g, c => c.toUpperCase()) || 'Districts', action: 'dtype', dtype: S.district_type });
      parts.push({ label: 'District ' + bag.displayName, here: true });
    }
    root.innerHTML = parts.map((p, i) => {
      const sep = i > 0 ? '<span class="sep">›</span> ' : '';
      if (p.here) return sep + '<span class="here">' + p.label + '</span>';
      return sep + '<a data-bc="' + (p.action || '') + '" data-county="' + (p.county || '') + '" data-dtype="' + (p.dtype || '') + '">' + p.label + '</a>';
    }).join(' ');
    root.querySelectorAll('a[data-bc]').forEach(a => {
      a.onclick = async () => {
        const action = a.getAttribute('data-bc');
        if (action === 'state') {
          S.level = 'county'; S.id = 'hamilton';
          writeState({ level: 'county', id: 'hamilton' });
        } else if (action === 'county') {
          const slug = a.getAttribute('data-county');
          S.level = 'county'; S.id = countyToSlug(slug);
          writeState({ level: 'county', id: S.id });
        } else if (action === 'dtype') {
          S.level = 'county'; S.id = 'hamilton'; S.district_type = null;
          writeState({ level: 'county', id: 'hamilton', type: null });
        }
        await refreshView();
      };
    });
  }

  // ── Center pane skeleton ───────────────────────────────────
  function chartCardHTML(id, title, sub) {
    return '' +
    '<div class="chart-card" data-chart-id="' + id + '">' +
      '<header>' +
        '<div>' +
          '<h3>' + title + '</h3>' +
          (sub ? '<div class="card-sub">' + sub + '</div>' : '') +
        '</div>' +
        '<div class="card-actions">' +
          '<button class="icon-btn" data-menu-trigger="' + id + '" title="Chart actions">⋯</button>' +
          '<div class="menu-pop" data-menu-pop="' + id + '">' +
            '<button data-export="png" data-cid="' + id + '">Export PNG</button>' +
            '<button data-export="json" data-cid="' + id + '">Export JSON</button>' +
          '</div>' +
        '</div>' +
      '</header>' +
      '<div class="chart-canvas-wrap" id="' + id + '-wrap"><canvas id="' + id + '"></canvas></div>' +
      (id === 'chart-party' ? '<div class="chart-legend-inline" id="chart-party-legend"></div>' : '') +
    '</div>';
  }

  function buildCenterPaneSingle() {
    const cp = $('center-pane');
    cp.innerHTML = '' +
      '<div class="breadcrumb" id="breadcrumb"></div>' +
      '<div class="hero" id="hero"></div>' +
      '<div class="narrative-card" id="narrative-card" style="display:none"></div>' +
      '<div class="charts-grid">' +
        chartCardHTML('chart-party',         'Party Affiliation', '7-cohort partisan spectrum') +
        chartCardHTML('chart-decade',        'Voter Age by Birth Decade') +
        chartCardHTML('chart-party-decade',  'Party × Birth Decade') +
        chartCardHTML('chart-gen',           'Generation Distribution') +
        chartCardHTML('chart-party-gen',     'Party × Generation') +
        chartCardHTML('chart-unc',           'UNC Voter Behavior', 'Inferred from primary ballot history') +
        '<div class="chart-card chart-card--wide" data-chart-id="city-table">' +
          '<header><div><h3>Registration by City / Township</h3><div class="card-sub">Sortable; rows are precincts grouped by name prefix</div></div>' +
            '<div class="card-actions"><button class="icon-btn" data-menu-trigger="city-table">⋯</button>' +
              '<div class="menu-pop" data-menu-pop="city-table">' +
                '<button data-export="json" data-cid="city-table">Export JSON</button>' +
              '</div>' +
            '</div>' +
          '</header>' +
          '<div id="city-table-wrap" class="chart-canvas-wrap"></div>' +
        '</div>' +
      '</div>';
  }

  function buildCenterPaneCompare(slotA, slotB) {
    const cp = $('center-pane');
    const aRaw = S.compare && S.compare[0];
    const bRaw = S.compare && S.compare[1];
    slotA = slotA || parseSlot(aRaw);
    slotB = slotB || parseSlot(bRaw);
    const a = slotA ? slotLabel(slotA) : '—';
    const b = slotB ? slotLabel(slotB) : '—';
    cp.innerHTML = '' +
      '<div class="breadcrumb full" id="breadcrumb"></div>' +
      '<section class="compare-pane" data-slot="a">' +
        '<div class="compare-pane-header"><span>Slot A</span><span class="name">' + a + '</span><button data-action="swap-slot" data-slot="a">change</button></div>' +
        '<div class="hero" id="hero-a"></div>' +
      '</section>' +
      '<section class="compare-pane" data-slot="b">' +
        '<div class="compare-pane-header"><span>Slot B</span><span class="name">' + b + '</span><button data-action="swap-slot" data-slot="b">change</button></div>' +
        '<div class="hero" id="hero-b"></div>' +
      '</section>' +
      '<section class="compare-pane" data-slot="a">' +
        chartCardHTML('chart-party-a',        'Party · ' + a, '7-cohort spectrum') +
      '</section>' +
      '<section class="compare-pane" data-slot="b">' +
        chartCardHTML('chart-party-b',        'Party · ' + b, '7-cohort spectrum') +
      '</section>' +
      '<section class="compare-pane" data-slot="a">' +
        chartCardHTML('chart-decade-a',       'Age · ' + a) +
      '</section>' +
      '<section class="compare-pane" data-slot="b">' +
        chartCardHTML('chart-decade-b',       'Age · ' + b) +
      '</section>' +
      '<section class="compare-pane" data-slot="a">' +
        chartCardHTML('chart-party-decade-a', 'Party × Age · ' + a) +
      '</section>' +
      '<section class="compare-pane" data-slot="b">' +
        chartCardHTML('chart-party-decade-b', 'Party × Age · ' + b) +
      '</section>' +
      '<section class="compare-pane" data-slot="a">' +
        chartCardHTML('chart-unc-a',          'UNC · ' + a) +
      '</section>' +
      '<section class="compare-pane" data-slot="b">' +
        chartCardHTML('chart-unc-b',          'UNC · ' + b) +
      '</section>';
  }

  // ── Compare rendering ──────────────────────────────────────
  async function refreshCompareView() {
    if (!S.compare || S.compare.length === 0) return;
    const slotA = parseSlot(S.compare[0]) || { kind: 'county', id: 'hamilton' };
    const slotB = parseSlot(S.compare[1]) || { kind: 'county', id: 'franklin' };
    buildCenterPaneCompare(slotA, slotB);

    async function loadSlot(slot) {
      if (slot.kind === 'district') {
        S.district_type = slot.dtype;
        return await loadJurisdiction('district', slot.id, null);
      }
      if (slot.kind === 'precinct') {
        return await loadJurisdiction('precinct', slot.id, slot.county);
      }
      return await loadJurisdiction('county', slot.id, null);
    }

    const [aBag, bBag] = await Promise.all([loadSlot(slotA), loadSlot(slotB)]);
    aBag.displayName = slotLabel(slotA);
    bBag.displayName = slotLabel(slotB);

    renderHero($('hero-a'), aBag);
    renderHero($('hero-b'), bBag);

    if (aBag.party && aBag.party.chartConfig) renderChart('chart-party-a', 'doughnut', aBag.party.chartConfig);
    if (bBag.party && bBag.party.chartConfig) renderChart('chart-party-b', 'doughnut', bBag.party.chartConfig);
    if (aBag.decade && aBag.decade.chartConfig) renderChart('chart-decade-a', 'bar', aBag.decade.chartConfig);
    if (bBag.decade && bBag.decade.chartConfig) renderChart('chart-decade-b', 'bar', bBag.decade.chartConfig);
    if (aBag.partyDecade && aBag.partyDecade.chartConfig) renderChart('chart-party-decade-a', 'bar', aBag.partyDecade.chartConfig, { stacked: true });
    if (bBag.partyDecade && bBag.partyDecade.chartConfig) renderChart('chart-party-decade-b', 'bar', bBag.partyDecade.chartConfig, { stacked: true });
    if (aBag.uncShadow && aBag.uncShadow.chartConfig) renderChart('chart-unc-a', 'bar', aBag.uncShadow.chartConfig, { stacked: true });
    if (bBag.uncShadow && bBag.uncShadow.chartConfig) renderChart('chart-unc-b', 'bar', bBag.uncShadow.chartConfig, { stacked: true });

    // Breadcrumb shows comparison context
    const root = $('breadcrumb');
    const ctx = (slotA.kind === 'district' || slotB.kind === 'district') ? 'Districts' : 'Geography';
    root.innerHTML =
      '<span class="here">Compare</span> <span class="sep">·</span> ' +
      '<a data-bc="state">' + ctx + '</a> <span class="sep">›</span> ' +
      aBag.displayName + ' <b style="color:var(--accent);margin:0 4px">⇄</b> ' + bBag.displayName;
    root.querySelectorAll('a[data-bc]').forEach(a => a.onclick = () => { S.compare = null; writeState({ compare: null }); refreshView(); });

    // Wire slot swap buttons — open a scrollable picker popover instead of a prompt.
    // Clicking the button also "focuses" that slot, so subsequent map clicks
    // update the correct slot.
    document.querySelectorAll('[data-action="swap-slot"]').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const slot = btn.getAttribute('data-slot');
        window._focusedSlot = slot;
        document.querySelectorAll('.compare-pane-header').forEach(h => h.classList.toggle('is-focused', h.closest('[data-slot="' + slot + '"]') !== null && h.parentNode.getAttribute('data-slot') === slot));
        const current = slot === 'a' ? slotA : slotB;
        const dtype = current.kind === 'district' ? current.dtype : null;
        await openSlotPicker(btn, slot, dtype, current);
      };
    });

    wireMenus();
    return [aBag, bBag];
  }

  async function listCompareChoices(dtype) {
    if (dtype) {
      try {
        const idx = await fetchJSON('data/' + dtype + '/index.json');
        const list = Array.isArray(idx) ? idx : (idx.districts || []);
        return list.map(d => ({ id: d.slug, label: 'District ' + d.slug, sub: (d.voter_count || 0).toLocaleString() + ' voters' }));
      } catch (e) { return []; }
    }
    return manifestCounties().map(name => ({ id: countyToSlug(name), label: name, sub: '' }));
  }

  async function openSlotPicker(anchorBtn, slot, dtype, current) {
    // Remove any open picker
    document.querySelectorAll('.slot-picker-pop').forEach(el => el.remove());
    const choices = await listCompareChoices(dtype);
    const pop = document.createElement('div');
    pop.className = 'slot-picker-pop';
    pop.innerHTML =
      '<div class="spp-search"><input type="search" placeholder="Filter…" autofocus></div>' +
      '<div class="spp-hint">' + (dtype ? 'or click a district on the map' : 'or click a county on the map') + '</div>' +
      '<div class="spp-list">' +
        choices.map(c => '<button class="spp-item" data-id="' + c.id + '"><span class="spp-name">' + c.label + '</span><span class="spp-sub">' + c.sub + '</span></button>').join('') +
      '</div>';
    document.body.appendChild(pop);

    // Position below the anchor button
    const rect = anchorBtn.getBoundingClientRect();
    pop.style.left = Math.max(8, rect.left) + 'px';
    pop.style.top = (rect.bottom + 6) + 'px';
    pop.style.minWidth = Math.max(220, rect.width + 80) + 'px';

    const inp = pop.querySelector('input');
    inp.focus();
    inp.oninput = () => {
      const q = inp.value.trim().toLowerCase();
      pop.querySelectorAll('.spp-item').forEach(b => {
        const t = b.textContent.toLowerCase();
        b.style.display = (!q || t.includes(q)) ? '' : 'none';
      });
    };
    pop.querySelectorAll('.spp-item').forEach(b => {
      b.onclick = () => {
        const id = b.getAttribute('data-id');
        const arr = S.compare.slice();
        arr[slot === 'a' ? 0 : 1] = dtype
          ? 'district:' + dtype + ':' + String(id).padStart(2, '0')
          : id;
        S.compare = arr;
        writeState({ compare: arr });
        emit('compare_update', { slot, value: arr[slot === 'a' ? 0 : 1] });
        pop.remove();
        refreshView();
      };
    });

    // Dismiss on outside click
    setTimeout(() => {
      document.addEventListener('click', function once(e) {
        if (!pop.contains(e.target) && e.target !== anchorBtn) {
          pop.remove();
          document.removeEventListener('click', once);
        }
      });
    }, 0);
  }


  // ── Main refresh ───────────────────────────────────────────
  async function refreshView() {
    applyChrome();

    if (!cache.manifest) {
      try { cache.manifest = await fetchJSON('manifest.json'); }
      catch (e) { console.error('manifest load fail', e); }
    }

    // Hierarchy
    await renderHierarchy();

    // Compare branch
    if (S.compare && S.compare.length) {
      await refreshCompareView();
    } else {
      buildCenterPaneSingle();
      destroyAll();

      let bag;
      if (S.level === 'county') {
        bag = await loadJurisdiction('county', S.id, null);
        bag.displayName = slugToCountyName(S.id);
      } else if (S.level === 'city') {
        bag = await loadJurisdiction('city', S.city, S.id);
        bag.displayName = S.city || '';
        bag.county = S.id;
      } else if (S.level === 'precinct') {
        bag = await loadJurisdiction('precinct', S.id, S.county || 'hamilton');
        bag.displayName = (bag.party && bag.party.precinct) || S.id.replace(/_/g, ' ').toUpperCase();
      } else if (S.level === 'district') {
        bag = await loadJurisdiction('district', S.id, null);
        bag.displayName = S.id;
      }
      renderBreadcrumb(bag);
      renderHero($('hero'), bag);
      renderNarrative(bag);
      renderCharts(bag);
      renderMapSelection(bag);
      wireMenus();
    }

    // Hex / District map: route by current view
    const mapEyebrow = document.querySelector('.right-pane .map-section > .eyebrow');
    const inDistrictMode = S.view === 'district' || S.level === 'district';
    if (inDistrictMode) {
      const dtype = S.district_type || 'state_senate_district';
      const layout = DISTRICT_LAYOUTS[dtype] || DISTRICT_LAYOUTS.state_senate_district;
      if (mapEyebrow) mapEyebrow.textContent = 'Ohio · ' + layout.count + ' ' + layout.label + ' · party lean';
      let selectedId = (S.level === 'district') ? S.id : null;
      let compareIds = null;
      if (S.compare) {
        const a = parseSlot(S.compare[0]);
        const b = parseSlot(S.compare[1]);
        compareIds = [
          (a && a.kind === 'district' && a.dtype === dtype) ? a.id : null,
          (b && b.kind === 'district' && b.dtype === dtype) ? b.id : null
        ];
      }
      renderDistrictMap(dtype, selectedId, compareIds, window._districtLeans && window._districtLeans[dtype]);
      // Background preload of leans for this district type
      if (!(window._districtLeans && window._districtLeans[dtype])) {
        preloadDistrictLean(dtype).then(leans => {
          window._districtLeans = window._districtLeans || {};
          window._districtLeans[dtype] = leans;
          renderDistrictMap(dtype, selectedId, compareIds, leans);
        });
      }
    } else if (S.compare) {
      if (mapEyebrow) mapEyebrow.textContent = 'Ohio · 88 counties · party lean';
      const a = parseSlot(S.compare[0]);
      const b = parseSlot(S.compare[1]);
      const aName = (a && a.kind === 'county') ? slugToCountyName(a.id) : null;
      const bName = (b && b.kind === 'county') ? slugToCountyName(b.id) : null;
      renderHexMap(window._leans, null, [aName, bName].filter(Boolean));
    } else {
      if (mapEyebrow) mapEyebrow.textContent = 'Ohio · 88 counties · party lean';
      const name = S.level === 'county' ? slugToCountyName(S.id) :
                   S.level === 'city' ? slugToCountyName(S.id) :
                   S.level === 'precinct' ? slugToCountyName(S.county || '') : null;
      renderHexMap(window._leans, name, null);
    }

    // GA pageview
    emit('page_view', { page_path: location.search, level: S.level, id: S.id, compare: S.compare ? S.compare.join(',') : null });

    // Compact tag in topbar
    const tag = $('compare-tag');
    if (tag) tag.style.display = S.compare ? '' : 'none';
    const cBtn = $('compare-toggle');
    if (cBtn) cBtn.classList.toggle('is-on', !!S.compare);
  }

  // ── Menus + exports ────────────────────────────────────────
  function wireMenus() {
    document.querySelectorAll('[data-menu-trigger]').forEach(t => {
      const id = t.getAttribute('data-menu-trigger');
      t.onclick = (e) => {
        e.stopPropagation();
        const popAll = document.querySelectorAll('.menu-pop');
        popAll.forEach(p => { if (p.getAttribute('data-menu-pop') !== id) p.classList.remove('is-open'); });
        const pop = document.querySelector('[data-menu-pop="' + id + '"]');
        if (pop) pop.classList.toggle('is-open');
      };
    });
    document.addEventListener('click', () => {
      document.querySelectorAll('.menu-pop.is-open').forEach(p => p.classList.remove('is-open'));
    });
    document.querySelectorAll('[data-export]').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const fmt = btn.getAttribute('data-export');
        const cid = btn.getAttribute('data-cid');
        await exportChart(cid, fmt);
        document.querySelectorAll('.menu-pop.is-open').forEach(p => p.classList.remove('is-open'));
      };
    });
  }

  async function exportChart(chartId, fmt) {
    if (fmt === 'png') {
      const chart = chartInstances[chartId];
      if (!chart) { toast('Chart not ready'); return; }
      const link = document.createElement('a');
      link.download = chartId + '.png';
      link.href = chart.toBase64Image('image/png', 1);
      link.click();
      emit('export_chart', { chart_id: chartId, format: 'png' });
      toast('PNG exported');
    } else if (fmt === 'json') {
      // Re-derive source URL based on current state + chart id
      const slug = S.level === 'county' ? S.id : (S.county || 'hamilton');
      const map = {
        'chart-party':        `data/${slug}_party_affiliation.json`,
        'chart-decade':       `data/${slug}_decade_distribution.json`,
        'chart-party-decade': `data/${slug}_party_by_decade.json`,
        'chart-gen':          `data/${slug}_generation_distribution.json`,
        'chart-party-gen':    `data/${slug}_party_by_generation.json`,
        'chart-unc':          `data/${slug}_unc_shadow.json`,
        'city-table':         `data/${slug}_city_summary.json`
      };
      const url = map[chartId];
      if (!url) { toast('JSON source unknown'); return; }
      try {
        const data = await fetchJSON(url);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.download = chartId + '.json';
        link.href = URL.createObjectURL(blob);
        link.click();
        URL.revokeObjectURL(link.href);
        emit('export_chart', { chart_id: chartId, format: 'json' });
        toast('JSON exported');
      } catch (e) { toast('Export failed'); }
    }
  }

  function toast(msg) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1800);
  }

  // ── Tweaks panel ───────────────────────────────────────────
  function buildTweaksPanel() {
    const p = $('tweaks-panel');
    if (!p) return;
    p.innerHTML = '' +
      '<header><h4>Tweaks</h4><button data-close-tweaks>×</button></header>' +
      tweakSeg('style',   'Visual style',  ['current','editorial']) +
      tweakSeg('theme',   'Theme',         ['light','dark']) +
      tweakSeg('layout',  'Layout',        ['3col','2col','single']) +
      tweakSeg('density', 'Density',       ['comfortable','compact']) +
      tweakSeg('view',    'Hierarchy view',['geo','district']);
    p.querySelector('[data-close-tweaks]').onclick = () => p.classList.add('hidden');
    p.querySelectorAll('[data-tweak]').forEach(btn => {
      btn.onclick = () => {
        const key = btn.getAttribute('data-tweak');
        const val = btn.getAttribute('data-val');
        S[key] = val;
        writeState({ [key]: val });
        emit('tweak_change', { key, value: val });
        if (key === 'view') { renderHierarchy(); }
        applyChrome();
        // Some changes need rerender (compact spacings, layout swap)
        if (['layout','density','style'].includes(key)) refreshView();
        buildTweaksPanel(); // refresh active state
      };
    });
  }
  function tweakSeg(key, label, opts) {
    return '<div class="tweak-group"><label class="lbl">' + label + '</label><div class="tweak-seg">' +
      opts.map(o => '<button data-tweak="' + key + '" data-val="' + o + '" class="' + (S[key] === o ? 'active' : '') + '">' + o + '</button>').join('') +
      '</div></div>';
  }

  // ── Search ─────────────────────────────────────────────────
  function wireSearch() {
    const inp = $('global-search');
    if (!inp) return;
    inp.oninput = () => {
      const q = inp.value.trim().toLowerCase();
      if (!q) return;
      // Filter visible rows in hierarchy
      document.querySelectorAll('.hier-row[data-action]').forEach(r => {
        const lbl = (r.textContent || '').toLowerCase();
        r.style.display = lbl.includes(q) ? '' : 'none';
      });
    };
    inp.onblur = () => {
      if (!inp.value) {
        document.querySelectorAll('.hier-row[data-action]').forEach(r => r.style.display = '');
      }
    };
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        emit('search', { query: inp.value });
        // Jump to first visible row
        const first = Array.from(document.querySelectorAll('.hier-row[data-action]')).find(r => r.style.display !== 'none');
        if (first) first.click();
      }
    });
  }

  // ── Topbar wiring ──────────────────────────────────────────
  function wireTopbar() {
    $('theme-toggle').onclick = () => {
      S.theme = S.theme === 'dark' ? 'light' : 'dark';
      writeState({ theme: S.theme });
      applyChrome();
      emit('theme_change', { theme: S.theme });
      refreshView();
    };
    $('tweaks-toggle').onclick = () => {
      const p = $('tweaks-panel');
      buildTweaksPanel();
      p.classList.toggle('hidden');
    };
    $('compare-toggle').onclick = () => {
      if (S.compare) {
        S.compare = null;
        writeState({ compare: null });
      } else if (S.view === 'district' || S.level === 'district') {
        // District-vs-district default pair within the same type
        const dtype = S.district_type || 'state_senate_district';
        const layout = DISTRICT_LAYOUTS[dtype];
        const baseId = (S.level === 'district' ? S.id : null) || '09';
        const pad = n => String(n).padStart(2, '0');
        const otherId = pad((parseInt(baseId, 10) % layout.count) + 1);
        const arr = ['district:' + dtype + ':' + baseId, 'district:' + dtype + ':' + otherId];
        S.compare = arr;
        writeState({ compare: arr });
      } else {
        // County-vs-county default pair
        const a = S.level === 'county' ? S.id : 'hamilton';
        const b = a === 'franklin' ? 'cuyahoga' : 'franklin';
        S.compare = [a, b];
        writeState({ compare: [a, b] });
      }
      emit('compare_toggle', { on: !!S.compare });
      refreshView();
    };
    // Drawer toggles
    document.querySelectorAll('[data-drawer]').forEach(b => {
      b.onclick = () => {
        const side = b.getAttribute('data-drawer');
        const target = side === 'left' ? document.querySelector('.left-pane') : document.querySelector('.right-pane');
        const bd = document.querySelector('.drawer-backdrop');
        const isOpen = target.classList.toggle('is-open');
        document.querySelectorAll('.left-pane.is-open, .right-pane.is-open').forEach(p => { if (p !== target) p.classList.remove('is-open'); });
        bd.classList.toggle('is-visible', !!document.querySelector('.left-pane.is-open, .right-pane.is-open'));
      };
    });
    document.querySelector('.drawer-backdrop').onclick = () => {
      document.querySelectorAll('.left-pane.is-open, .right-pane.is-open').forEach(p => p.classList.remove('is-open'));
      document.querySelector('.drawer-backdrop').classList.remove('is-visible');
    };
  }

  // ── Boot ───────────────────────────────────────────────────
  async function boot() {
    applyChrome();
    wireTopbar();
    wireSearch();
    // Initial skeleton
    buildCenterPaneSingle();

    // Map first paint (no leans yet)
    renderHexMap({}, S.level === 'county' ? slugToCountyName(S.id) : null);

    await refreshView();

    // Preload leans for the map in the background
    // Skip when in district view — the district map fetches its own leans.
    if (S.view !== 'district' && S.level !== 'district') {
      preloadCountyLean().then(leans => {
        window._leans = leans;
        // Re-check state at fire time — user may have switched to district view
        if (S.view === 'district' || S.level === 'district') return;
        if (S.compare) {
          const a = parseSlot(S.compare[0]);
          const b = parseSlot(S.compare[1]);
          const aN = (a && a.kind === 'county') ? slugToCountyName(a.id) : null;
          const bN = (b && b.kind === 'county') ? slugToCountyName(b.id) : null;
          renderHexMap(leans, null, [aN, bN].filter(Boolean));
        } else {
          const name = S.level === 'county' ? slugToCountyName(S.id) :
                       S.level === 'city' ? slugToCountyName(S.id) :
                       S.level === 'precinct' ? slugToCountyName(S.county || '') : null;
          renderHexMap(leans, name, null);
        }
      }).catch(e => console.warn('lean preload error', e));
    }

    window.addEventListener('popstate', () => {
      Object.assign(S, readState());
      refreshView();
    });
  }
  document.addEventListener('DOMContentLoaded', boot);
})();
