import pandas as pd
import os
import time
from collections import defaultdict

OHIO_COUNTIES = [
    "Adams", "Allen", "Ashland", "Ashtabula", "Athens", "Auglaize", "Belmont", "Brown", 
    "Butler", "Carroll", "Champaign", "Clark", "Clermont", "Clinton", "Columbiana", "Coshocton", 
    "Crawford", "Cuyahoga", "Darke", "Defiance", "Delaware", "Erie", "Fairfield", "Fayette", 
    "Franklin", "Fulton", "Gallia", "Geauga", "Greene", "Guernsey", "Hamilton", "Hancock", 
    "Hardin", "Harrison", "Henry", "Highland", "Hocking", "Holmes", "Huron", "Jackson", 
    "Jefferson", "Knox", "Lake", "Lawrence", "Licking", "Logan", "Lorain", "Lucas", 
    "Madison", "Mahoning", "Marion", "Medina", "Meigs", "Mercer", "Miami", "Monroe", 
    "Montgomery", "Morgan", "Morrow", "Muskingum", "Noble", "Ottawa", "Paulding", "Perry", 
    "Pickaway", "Pike", "Portage", "Preble", "Putnam", "Richland", "Ross", "Sandusky", 
    "Scioto", "Seneca", "Shelby", "Stark", "Summit", "Trumbull", "Tuscarawas", "Union", 
    "Van Wert", "Vinton", "Warren", "Washington", "Wayne", "Williams", "Wood", "Wyandot"
]

parquet_dir = r"D:\vibe\election-data\local\source\parquet"
output_file = r"D:\vibe\election-data\local\exports\residential_zips_by_county.md"

start_time = time.time()
os.makedirs(os.path.dirname(output_file), exist_ok=True)

print("Analyzing ZIP codes...")

zip_to_counties = defaultdict(list)

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# Residential ZIP Codes by County\n\n")
    
    for i in range(1, 89):
        county_num = f"{i:02d}"
        county_name = OHIO_COUNTIES[i-1]
        file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
        
        if not os.path.exists(file_path):
            continue
            
        df = pd.read_parquet(file_path, columns=['RESIDENTIAL_ZIP'])
        unique_zips = sorted([z for z in df['RESIDENTIAL_ZIP'].dropna().astype(str).str.strip().unique() if z != ''])
        
        for z in unique_zips:
            zip_to_counties[z].append(county_name)
        
        f.write(f"## {county_num}_{county_name} ({len(unique_zips)} unique ZIPs)\n")
        f.write(", ".join(unique_zips) + "\n\n")
        
        print(f"Processed County {county_num} - {len(unique_zips)} ZIPs")

    # Now append shared ZIPs
    f.write("---\n\n")
    f.write("# Shared ZIP Codes Across Counties\n\n")
    
    shared_zips = {z: counties for z, counties in zip_to_counties.items() if len(counties) > 1}
    
    f.write(f"Found {len(shared_zips)} ZIP codes that span across multiple county borders.\n\n")
    
    for z in sorted(shared_zips.keys()):
        counties_str = ", ".join(sorted(shared_zips[z]))
        f.write(f"- **{z}**: {counties_str} ({len(shared_zips[z])} counties)\n")

print(f"Report generated at {output_file} in {time.time() - start_time:.2f} seconds.")
