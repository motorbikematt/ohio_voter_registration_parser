import os
import re

def patch_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Replace style logic in loadOverlayLayer
    search_str = r"""style: \{
                            color: color,
                            weight: 3,
                            opacity: 1,
                            fillOpacity: 0\.0,
                            dashArray: dashArray
                        \}"""
    
    replace_str = """style: (feature) => {
                            const dem = feature.properties.DEM_VOTERS || 0;
                            const rep = feature.properties.REP_VOTERS || 0;
                            const total = feature.properties.TOTAL_VOTERS || 0;
                            
                            let fillColor = 'transparent';
                            let fillOpacity = 0.0;
                            
                            // Only apply choropleth if there are voters (solves the 0 problem)
                            if (total > 0) {
                                fillOpacity = 0.5; // Slightly transparent to let precincts show through if stacked
                                fillColor = '#9ca3af'; // Tie
                                if (dem > rep) fillColor = '#2563eb'; // Pure D
                                else if (rep > dem) fillColor = '#ef4444'; // Pure R
                            }
                            
                            return {
                                color: color, // Keep the distinct dashed border color
                                weight: 3,
                                opacity: 1,
                                dashArray: dashArray,
                                fillColor: fillColor,
                                fillOpacity: fillOpacity
                            };
                        }"""
    
    html = re.sub(search_str, replace_str, html, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Patched {filepath}")

patch_html("D:/vibe/election-data/docs/montgomery_choropleth.html")
