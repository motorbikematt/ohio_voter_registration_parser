import pandas as pd
import os
import time

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
output_file = r"D:\vibe\election-data\local\exports\local_district_clusters.md"

local_districts = [
    'CITY_SCHOOL_DISTRICT', 
    'COUNTY_COURT_DISTRICT', 
    'EDU_SERVICE_CENTER_DISTRICT', 
    'EXEMPTED_VILL_SCHOOL_DISTRICT', 
    'LIBRARY', 
    'LOCAL_SCHOOL_DISTRICT', 
    'MUNICIPAL_COURT_DISTRICT'
]

clusters = {d: {} for d in local_districts}

os.makedirs(os.path.dirname(output_file), exist_ok=True)
start_time = time.time()

for i in range(1, 89):
    county_num = f"{i:02d}"
    county_name = OHIO_COUNTIES[i-1]
    file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
    
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_parquet(file_path, columns=local_districts)
    
    for col in local_districts:
        unique_vals = df[col].dropna().astype(str).str.strip().unique()
        for val in unique_vals:
            if val != "":
                if val not in clusters[col]:
                    clusters[col][val] = []
                clusters[col][val].append(f"{county_num}_{county_name}")

    print(f"Processed County {county_num} - {county_name}")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# County Clusters by Local Districts\n\n")
    f.write("This report shows how Ohio's 88 counties map to localized jurisdictions such as school districts, library districts, and municipal courts. Note that many of these districts are highly localized and may only exist within a single county, while some cross county borders.\n\n")
    
    for col in local_districts:
        display_name = col.replace('_', ' ').title()
        f.write(f"## {display_name}\n\n")
        
        # Sort alphabetically
        sorted_districts = sorted(clusters[col].items(), key=lambda x: str(x[0]))
        
        for val, counties in sorted_districts:
            f.write(f"### District: {val} ({len(counties)} Counties)\n")
            f.write(", ".join(sorted(counties)) + "\n\n")

print(f"Local district cluster report generated at {output_file} in {time.time() - start_time:.2f} seconds.")
