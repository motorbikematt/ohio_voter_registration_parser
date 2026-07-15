import os
import re

def patch_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 1. Add controls
    controls_search = r'<label>\s*<input type="checkbox" id="toggle-wards"[^>]*> Show Wards \(Yellow Overlay\)\s*</label>'
    controls_replace = """<label>
                <input type="checkbox" id="toggle-wards" checked> Show Wards
            </label>
            <label>
                <input type="checkbox" id="toggle-house"> Show House
            </label>
            <label>
                <input type="checkbox" id="toggle-senate"> Show Senate
            </label>
            <label>
                <input type="checkbox" id="toggle-congress"> Show Congress
            </label>"""
    html = re.sub(controls_search, controls_replace, html)
    
    # 2. Add legend items
    legend_search = r'<div class="legend-item">\s*<div class="legend-color" style="border-top: 3px dashed #eab308; [^>]*></div>\s*<span>Strict Ward Boundaries</span>\s*</div>'
    legend_replace = """<div class="legend-item">
                <div class="legend-color" style="border-top: 3px dashed #eab308; width: 16px; height: 0; background: transparent;"></div>
                <span>Wards</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="border-top: 3px dashed #10b981; width: 16px; height: 0; background: transparent;"></div>
                <span>House</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="border-top: 3px dashed #f43f5e; width: 16px; height: 0; background: transparent;"></div>
                <span>Senate</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="border-top: 3px dashed #8b5cf6; width: 16px; height: 0; background: transparent;"></div>
                <span>Congress</span>
            </div>"""
    html = re.sub(legend_search, legend_replace, html)
    
    # 3. Add variables
    var_search = r'let wardsLayer;'
    var_replace = """let wardsLayer;
        let houseLayer;
        let senateLayer;
        let congressLayer;"""
    html = html.replace(var_search, var_replace)
    
    # 4. Replace ward loading logic with dynamic loading logic
    ward_load_search = r'// Load Wards.*?catch\(err => console\.error\("Error loading wards:", err\)\);'
    
    ward_load_replace = """// Helper to load overlays
        function loadOverlayLayer(url, color, dashArray, varName, titleCol) {
            fetch(url)
                .then(res => res.json())
                .then(data => {
                    const layer = L.geoJSON(data, {
                        style: {
                            color: color,
                            weight: 3,
                            opacity: 1,
                            fillOpacity: 0.0,
                            dashArray: dashArray
                        },
                        onEachFeature: (feature, l) => {
                            const props = feature.properties;
                            l.bindPopup(createPopupContent(props[titleCol] || 'Unknown', props));
                        }
                    });
                    
                    if (varName === 'wards') wardsLayer = layer;
                    if (varName === 'house') houseLayer = layer;
                    if (varName === 'senate') senateLayer = layer;
                    if (varName === 'congress') congressLayer = layer;
                    
                    // Wards checked by default
                    if (varName === 'wards') {
                        layer.addTo(map);
                        layer.bringToFront();
                    }
                })
                .catch(err => console.error("Error loading " + varName + ":", err));
        }

        loadOverlayLayer('data/montgomery_wards.geojson', '#eab308', '5, 5', 'wards', 'DESCRIPTIO');
        loadOverlayLayer('data/montgomery_house.geojson', '#10b981', '8, 4', 'house', 'DESCRIPTIO');
        loadOverlayLayer('data/montgomery_senate.geojson', '#f43f5e', '10, 5', 'senate', 'DESCRIPTIO');
        loadOverlayLayer('data/montgomery_congress.geojson', '#8b5cf6', '12, 6', 'congress', 'DESRIPTION');"""
    html = re.sub(ward_load_search, ward_load_replace, html, flags=re.DOTALL)
    
    # 5. Replace toggle logic
    toggle_search = r'document\.getElementById\(\'toggle-precincts\'\).*?}\);'
    
    toggle_replace = """document.getElementById('toggle-precincts').addEventListener('change', function() {
            if (this.checked && precinctsLayer) {
                map.addLayer(precinctsLayer);
                if (wardsLayer && map.hasLayer(wardsLayer)) wardsLayer.bringToFront();
                if (houseLayer && map.hasLayer(houseLayer)) houseLayer.bringToFront();
                if (senateLayer && map.hasLayer(senateLayer)) senateLayer.bringToFront();
                if (congressLayer && map.hasLayer(congressLayer)) congressLayer.bringToFront();
            } else if (precinctsLayer) {
                map.removeLayer(precinctsLayer);
            }
        });

        function toggleLayer(checkboxId, getLayer) {
            document.getElementById(checkboxId).addEventListener('change', function() {
                const layer = getLayer();
                if (!layer) return;
                if (this.checked) {
                    map.addLayer(layer);
                    layer.bringToFront();
                } else {
                    map.removeLayer(layer);
                }
            });
        }

        toggleLayer('toggle-wards', () => wardsLayer);
        toggleLayer('toggle-house', () => houseLayer);
        toggleLayer('toggle-senate', () => senateLayer);
        toggleLayer('toggle-congress', () => congressLayer);"""
    
    # The toggle search has multiple matches potentially, so we do it via slicing
    # Find start of toggle-precincts
    t_start = html.find("document.getElementById('toggle-precincts')")
    t_end = html.rfind("});") + 3
    if t_start != -1 and t_end != -1:
        html = html[:t_start] + toggle_replace + html[t_end:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Patched {filepath}")

patch_html("D:/vibe/election-data/docs/montgomery_demo.html")
patch_html("D:/vibe/election-data/docs/montgomery_choropleth.html")
