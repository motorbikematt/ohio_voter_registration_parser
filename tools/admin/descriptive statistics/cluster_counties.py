import os
import re

input_file = r"D:\vibe\election-data\local\exports\precinct_shapes_report.md"
output_file = r"D:\vibe\election-data\local\exports\county_clusters.md"

if not os.path.exists(input_file):
    print("Input file not found.")
    exit()

code_clusters = {}
name_clusters = {
    "Explicit 'PRECINCT' Prefix": [],
    "Contains 'WARD' or 'WD'": [],
    "No Spaces (Extreme Compression)": [],
    "Pure Base Name (Starts with [WORD])": []
}

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    if line.startswith("|") and not line.startswith("| County |") and not line.startswith("|---|"):
        parts = line.split("|")
        if len(parts) >= 4:
            county = parts[1].strip()
            code_shape = parts[2].strip()
            name_shapes = parts[3].strip()
            
            # Clean up code shape
            m = re.search(r'`([^`]+)`', code_shape)
            if m:
                code_pattern = m.group(1)
                if code_pattern not in code_clusters:
                    code_clusters[code_pattern] = []
                code_clusters[code_pattern].append(county)
            
            # Name clustering
            if "PRECINCT" in name_shapes:
                name_clusters["Explicit 'PRECINCT' Prefix"].append(county)
            if "WARD" in name_shapes or "WD" in name_shapes:
                name_clusters["Contains 'WARD' or 'WD'"].append(county)
            if "`[NUM][WORD]`" in name_shapes:
                name_clusters["No Spaces (Extreme Compression)"].append(county)
            
            # If at least one of their top shapes starts with [WORD] and doesn't start with PRECINCT
            top_shape = name_shapes.split("<br>")[0]
            if top_shape.startswith("`[WORD]"):
                name_clusters["Pure Base Name (Starts with [WORD])"].append(county)

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# County Precinct Clusters\n\n")
    f.write("This report groups Ohio's 88 counties by the shared deterministic patterns used in their precinct data.\n\n")
    
    f.write("## 1. Clustering by PRECINCT_CODE Formats\n\n")
    for code, counties in sorted(code_clusters.items(), key=lambda x: -len(x[1])):
        f.write(f"### Pattern: `{code}` ({len(counties)} Counties)\n")
        f.write(", ".join([c.split('_')[1] for c in counties]) + "\n\n")
        
    f.write("## 2. Clustering by PRECINCT_NAME Structural Features\n\n")
    f.write("Counties often share philosophical approaches to naming precincts (e.g., formal prefixes vs. abbreviations).\n\n")
    
    for feature, counties in name_clusters.items():
        f.write(f"### Feature: {feature} ({len(counties)} Counties)\n")
        if len(counties) > 0:
            f.write(", ".join([c.split('_')[1] for c in counties]) + "\n\n")
        else:
            f.write("None\n\n")

print(f"Clustered report generated at {output_file}")
