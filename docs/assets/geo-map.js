/* ============================================================
   geo-map.js — shared inline-SVG geography for precincts.info

   ONE projection, ONE path builder, ONE party-lean table, used by
   BOTH the landing choropleth (index.htm / landing-map.js) and the
   dashboard map panel (app.htm / v2.js). Zero dependencies: no
   Leaflet, no tile CDN.

   Why this file exists: PARTY_LEAN_BUCKETS previously lived in two
   places (landing-map.js and v2.js) with a hand-sync comment, and
   the dashboard drew stylized hexes/jittered cells instead of real
   shapes. Duplicated derivation logic is how the postal-city bug
   survived weeks (CLAUDE.md section 5). Do not re-copy anything
   below into a consumer -- import it from window.GeoMap.

   Data: docs/data/state_map/*.geojson, plain EPSG:4326 lon/lat,
   each carrying `bounds: [W,S,E,N]` and per-feature
   `properties.lean` precomputed by the map-data build. We only
   COLOR by lean here; we never recompute it.

   Loaded as a plain global-scope script BEFORE its consumers:
     app.htm    -> before assets/v2.js
     index.htm  -> before assets/landing-map.js
   Not an ES module by design -- nothing else here uses them.

   All markup is built with createElementNS + textContent, never
   innerHTML, so feature text has no HTML-injection surface. There
   is deliberately no esc() here; v2.js's esc() is private to that
   file's IIFE and is not visible from this one.
   ============================================================ */
(function () {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  // ── Party lean ───────────────────────────────────────────
  // Single canonical copy. Previously duplicated in landing-map.js
  // and v2.js; both now read it from here.
  var PARTY_LEAN_BUCKETS = [
    { max: -0.15, color: '#ef4444', label: 'Strong R' },
    { max: -0.05, color: '#f87171', label: 'Lean R' },
    { max:  0.05, color: '#9ca3af', label: 'Mixed / UNC' },
    { max:  0.15, color: '#60a5fa', label: 'Lean D' },
    { max:  1.0,  color: '#2563eb', label: 'Strong D' }
  ];

  function leanColor(lean) {
    if (lean === null || lean === undefined) return null;
    for (var i = 0; i < PARTY_LEAN_BUCKETS.length; i++) {
      if (lean <= PARTY_LEAN_BUCKETS[i].max) return PARTY_LEAN_BUCKETS[i].color;
    }
    return PARTY_LEAN_BUCKETS[PARTY_LEAN_BUCKETS.length - 1].color;
  }
  function leanLabel(lean) {
    if (lean === null || lean === undefined) return 'No data';
    for (var i = 0; i < PARTY_LEAN_BUCKETS.length; i++) {
      if (lean <= PARTY_LEAN_BUCKETS[i].max) return PARTY_LEAN_BUCKETS[i].label;
    }
    return PARTY_LEAN_BUCKETS[PARTY_LEAN_BUCKETS.length - 1].label;
  }
  function formatLean(lean) {
    if (lean === null || lean === undefined) return 'n/a';
    var pct = lean * 100;
    return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '% D-R';
  }

  // ── Projection (equirectangular, corrected for latitude) ──
  // Longitude degrees are pre-multiplied by cos(midLat) so Ohio is
  // not horizontally squashed at ~40N. Width is normalized to 1000
  // user units; height follows from the real aspect (Ohio: ~1197,
  // i.e. PORTRAIT, aspect ~0.835 -- consumers must size their
  // container to match rather than distort the geometry).
  function computeProjection(bounds) {
    var W = bounds[0], S = bounds[1], E = bounds[2], N = bounds[3];
    var midLat = (S + N) / 2;
    var kx = Math.cos(midLat * Math.PI / 180);
    var s = 1000 / ((E - W) * kx);
    return {
      W: W, S: S, E: E, N: N,
      width: 1000,
      height: (N - S) * s,
      x: function (lon) { return (lon - W) * kx * s; },
      y: function (lat) { return (N - lat) * s; }
    };
  }

  function ringToPath(ring, proj) {
    var d = '';
    for (var i = 0; i < ring.length; i++) {
      var x = proj.x(ring[i][0]).toFixed(2);
      var y = proj.y(ring[i][1]).toFixed(2);
      d += (i === 0 ? 'M' : 'L') + x + ' ' + y;
    }
    return d + 'Z';
  }
  function geometryToPath(geom, proj) {
    var d = '', i, j;
    if (!geom) return d;
    if (geom.type === 'Polygon') {
      for (i = 0; i < geom.coordinates.length; i++) d += ringToPath(geom.coordinates[i], proj);
    } else if (geom.type === 'MultiPolygon') {
      for (i = 0; i < geom.coordinates.length; i++) {
        for (j = 0; j < geom.coordinates[i].length; j++) d += ringToPath(geom.coordinates[i][j], proj);
      }
    }
    return d;
  }

  // ── Feature bounds ───────────────────────────────────────
  // Lon/lat bbox of one geometry, in the same [W,S,E,N] shape the
  // geojson files carry -- so it can be handed straight to
  // computeProjection() to "zoom": projecting a smaller box into the
  // same 1000-unit width IS the zoom. No transform math involved.
  //
  // `padFrac` insets the box by a fraction of its larger side (0.15 =
  // ~15% breathing room). Padding the larger side on both axes keeps
  // the shape's true aspect: padding each axis by its own extent would
  // distort a long thin district differently than a compact one.
  //
  // A degenerate box (single point, or a geometry we could not walk)
  // returns null rather than a zero-size projection that would divide
  // by zero downstream.
  function featureBounds(geom, padFrac) {
    if (!geom) return null;
    var minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
    function walkRing(ring) {
      for (var i = 0; i < ring.length; i++) {
        var lon = ring[i][0], lat = ring[i][1];
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
    if (geom.type === 'Polygon') {
      for (var i = 0; i < geom.coordinates.length; i++) walkRing(geom.coordinates[i]);
    } else if (geom.type === 'MultiPolygon') {
      for (var j = 0; j < geom.coordinates.length; j++) {
        for (var k = 0; k < geom.coordinates[j].length; k++) walkRing(geom.coordinates[j][k]);
      }
    } else {
      return null;
    }
    if (!isFinite(minLon) || !isFinite(minLat)) return null;
    var dLon = maxLon - minLon, dLat = maxLat - minLat;
    if (dLon <= 0 && dLat <= 0) return null;
    var pad = (padFrac === undefined ? 0.15 : padFrac) * Math.max(dLon, dLat);
    return [minLon - pad, minLat - pad, maxLon + pad, maxLat + pad];
  }

  // ── Fetch + cache ────────────────────────────────────────
  // Keyed by url, shared process-wide. The dashboard renderers run
  // on every view refresh; re-fetching 163 KB each time would be a
  // regression. Promises (not results) are cached so concurrent
  // callers coalesce into one request.
  var _geoCache = {};
  function loadGeoJSON(url) {
    if (_geoCache[url]) return _geoCache[url];
    _geoCache[url] = fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + url);
      return r.json();
    }).catch(function (e) {
      delete _geoCache[url];        // allow a later retry
      throw e;
    });
    return _geoCache[url];
  }

  // ── Render ───────────────────────────────────────────────
  // Serves two contexts from one code path:
  //
  //                  landing (index.htm)      dashboard (app.htm)
  //   container      <g id="viewport">        <div id="map">
  //   mode           'all'                    'selected'
  //   click          native <a href>          onClick callback
  //   tooltip        caller's hover handler   <title> only
  //
  // opts:
  //   container   Element. An SVG <g>/<svg> node is appended to
  //               directly; anything else (a <div>) gets a fresh
  //               <svg> built inside it, replacing its contents.
  //   geojson     parsed FeatureCollection carrying `bounds`.
  //   proj        optional precomputed projection; otherwise
  //               derived from geojson.bounds.
  //   mode        'all'      -> every shape filled by lean
  //               'selected' -> selected/compare filled by lean,
  //                             all others dimmed but OUTLINED
  //   keyProp     properties key to join on ('slug' | 'id').
  //   selectedKey string | null
  //   compareKeys [aKey, bKey] | null
  //   activeKeys  Set|Array of keys that keep lean color in 'selected'
  //               mode without the selected/compare stroke treatment.
  //               compareKeys is POSITIONAL (indexOf -> is-compare-a/b)
  //               and so holds exactly two; this carries a whole set --
  //               e.g. every precinct of one city, coloured while the
  //               rest of the county greys out.
  //   hrefFor     fn(props) -> url; wraps each shape in <a>.
  //   onClick     fn(key, props, event); used when hrefFor is absent.
  //   nameFor     fn(props) -> display name (title / aria-label).
  //   titleFor    fn(props) -> <title> text; defaults to
  //               "Name - +1.2% D-R".
  //   className   base class per shape (default 'geo-shape').
  //   setViewBox  bool, default true when container is a plain
  //               element; sets viewBox on the owning <svg>.
  //
  // Returns { proj, svg, count } so a caller can drive pan/zoom.
  function render(opts) {
    var container = opts.container;
    var gj = opts.geojson;
    if (!container || !gj || !gj.features) return null;

    var proj = opts.proj || computeProjection(gj.bounds || [-84.8203, 38.40342, -80.5187, 42.32713]);
    var isSvgNode = (container.namespaceURI === SVG_NS);
    var svg, target;

    if (isSvgNode) {
      // Landing: caller owns <svg> and the pan/zoom <g>; we only fill it.
      target = container;
      svg = container.ownerSVGElement || container;
      while (target.firstChild) target.removeChild(target.firstChild);
    } else {
      // Dashboard: build a fresh <svg> inside the given element.
      while (container.firstChild) container.removeChild(container.firstChild);
      svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      if (opts.ariaLabel) svg.setAttribute('aria-label', opts.ariaLabel);
      container.appendChild(svg);
      target = svg;
    }
    if (opts.setViewBox !== false) {
      svg.setAttribute('viewBox', '0 0 ' + proj.width + ' ' + proj.height.toFixed(1));
    }

    var keyProp   = opts.keyProp || 'slug';
    var mode      = opts.mode || 'all';
    var baseClass = opts.className || 'geo-shape';
    var selected  = opts.selectedKey || null;
    var compare   = opts.compareKeys || null;
    // Normalized to a Set so membership is O(1) across 381 precincts.
    var active    = null;
    if (opts.activeKeys) {
      active = (typeof Set === 'function' && opts.activeKeys instanceof Set)
        ? opts.activeKeys
        : new Set(opts.activeKeys);
    }
    var frag = document.createDocumentFragment();
    var feats = gj.features;
    var n = 0;

    // When zoomed (the inset), skip features whose own bbox does not
    // intersect the frame at all. Without this a house-district inset
    // builds 99 full-detail paths to show two or three.
    var clip = opts.clipBounds || null;

    for (var i = 0; i < feats.length; i++) {
      var f = feats[i], p = f.properties || {};
      var key = p[keyProp];
      if (clip) {
        var fb = featureBounds(f.geometry, 0);
        if (!fb || fb[2] < clip[0] || fb[0] > clip[2] || fb[3] < clip[1] || fb[1] > clip[3]) continue;
      }
      var name = opts.nameFor ? opts.nameFor(p) : (p.name || String(key));
      var lean = (p.lean === undefined ? null : p.lean);

      var isSel = (selected !== null && key === selected);
      var cmpIdx = compare ? compare.indexOf(key) : -1;
      var isActive = (active !== null && key !== undefined && key !== null && active.has(key));
      var highlighted = isSel || cmpIdx >= 0 || isActive;

      var cls = [baseClass];
      if (isSel && cmpIdx < 0) cls.push('is-selected');
      if (cmpIdx === 0) cls.push('is-compare-a');
      if (cmpIdx === 1) cls.push('is-compare-b');
      // 'selected' mode: highlighted shapes carry the full lean color;
      // everything else is dimmed -- but keeps its stroke, so every
      // outline stays visible (the operator's actual request).
      var dimmed = (mode === 'selected' && !highlighted);
      if (dimmed) cls.push('is-dimmed');

      // A dimmed shape keeps its lean HUE, mixed down toward the surface,
      // rather than being flattened to one grey. Previously every unselected
      // shape painted var(--surface-3), which discarded information the
      // tooltip was still reporting ("Hancock County - -29.2% D-R") and, in
      // dark mode, left the rest of the state a barely-visible flat mass.
      // Mixing (not a blanket opacity) keeps red-vs-blue legible at a glance
      // while the selection still clearly dominates; :hover in v2.css raises
      // the same colour toward full strength.
      var full = leanColor(lean);
      var fill;
      if (!dimmed) {
        fill = full || 'var(--surface-3)';
      } else if (full) {
        fill = 'color-mix(in srgb, ' + full + ' 42%, var(--surface-3))';
      } else {
        fill = 'var(--surface-3)';   // genuinely no data: stays neutral
      }

      var path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('d', geometryToPath(f.geometry, proj));
      path.setAttribute('fill-rule', 'evenodd');
      path.setAttribute('fill', fill);
      path.setAttribute('stroke', 'var(--rule)');
      path.setAttribute('stroke-width', '0.6');
      path.setAttribute('vector-effect', 'non-scaling-stroke');
      path.setAttribute('class', cls.join(' '));
      if (key !== undefined && key !== null) path.setAttribute('data-key', String(key));

      // Default tooltip carries name, the lean bucket in words, the signed
      // margin, and registered voters where we have them -- the same facts the
      // landing map already put in its aria-label. Hovering an unselected
      // shape should answer "what is this and how does it lean?" without
      // requiring a click. Native <title> keeps the browser's own hover
      // timing, which the operator asked to preserve.
      var title = document.createElementNS(SVG_NS, 'title');
      title.textContent = opts.titleFor
        ? opts.titleFor(p)
        : (name +
           (lean === null
             ? ' - data pending'
             : ' - ' + leanLabel(lean) + ' (' + formatLean(lean) + ')') +
           (p.total_voters
             ? ' - ' + Number(p.total_voters).toLocaleString() + ' registered'
             : ''));
      path.appendChild(title);

      if (opts.hrefFor) {
        var a = document.createElementNS(SVG_NS, 'a');
        a.setAttributeNS(null, 'href', opts.hrefFor(p));
        a.setAttribute('aria-label',
          name + ' - ' + leanLabel(lean) + ' (' + formatLean(lean) + ')' +
          (p.total_voters ? ' - ' + Number(p.total_voters).toLocaleString() + ' registered voters' : ''));
        a.dataset.name  = name;
        a.dataset.lean  = formatLean(lean);
        a.dataset.label = leanLabel(lean);
        a.dataset.total = Number(p.total_voters || 0).toLocaleString();
        a.appendChild(path);
        frag.appendChild(a);
      } else {
        if (opts.onClick) {
          path.style.cursor = 'pointer';
          (function (k, props) {
            path.addEventListener('click', function (ev) { opts.onClick(k, props, ev); });
          })(key, p);
        }
        frag.appendChild(path);
      }
      n++;
    }

    target.appendChild(frag);
    return { proj: proj, svg: svg, count: n };
  }

  window.GeoMap = {
    SVG_NS: SVG_NS,
    PARTY_LEAN_BUCKETS: PARTY_LEAN_BUCKETS,
    leanColor: leanColor,
    leanLabel: leanLabel,
    formatLean: formatLean,
    computeProjection: computeProjection,
    featureBounds: featureBounds,
    ringToPath: ringToPath,
    geometryToPath: geometryToPath,
    loadGeoJSON: loadGeoJSON,
    render: render
  };
})();
