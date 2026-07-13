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

district_columns = [
    'CITY_SCHOOL_DISTRICT', 'COUNTY_COURT_DISTRICT', 'CONGRESSIONAL_DISTRICT', 
    'COURT_OF_APPEALS', 'EDU_SERVICE_CENTER_DISTRICT', 'EXEMPTED_VILL_SCHOOL_DISTRICT', 
    'LIBRARY', 'LOCAL_SCHOOL_DISTRICT', 'MUNICIPAL_COURT_DISTRICT', 
    'STATE_BOARD_OF_EDUCATION', 'STATE_REPRESENTATIVE_DISTRICT', 'STATE_SENATE_DISTRICT'
]

# We also need these to determine the patterns
columns_to_read = district_columns + ['PRECINCT_NAME', 'PRECINCT_CODE']

parquet_dir = r"D:\vibe\election-data\local\source\parquet"
output_file = r"D:\vibe\election-data\local\exports\county_report.md"

os.makedirs(os.path.dirname(output_file), exist_ok=True)

start_time = time.time()
precinct_patterns = []

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# Ohio County Properties Report\n\n")
    
    for i in range(1, 89):
        county_num = f"{i:02d}"
        county_name = OHIO_COUNTIES[i-1]
        file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
        
        if not os.path.exists(file_path):
            continue
            
        df = pd.read_parquet(file_path, columns=columns_to_read)
        total_voters = len(df)
        
        # Determine Precinct Name pattern lengths
        names = df['PRECINCT_NAME'].dropna().astype(str).str.strip()
        name_min = names.str.len().min()
        name_max = names.str.len().max()
        if name_min == name_max:
            name_pattern = f"Fixed ({name_max} chars)"
        else:
            name_pattern = f"Variable ({name_min}-{name_max} chars)"
            
        # Determine Precinct Code pattern lengths and types
        codes = df['PRECINCT_CODE'].dropna().astype(str).str.strip()
        code_min = codes.str.len().min()
        code_max = codes.str.len().max()
        is_num = codes.str.isnumeric().all()
        code_type = "Numeric" if is_num else "Alphanumeric"
        if code_min == code_max:
            code_pattern = f"{code_type}, Fixed ({code_max} chars)"
        else:
            code_pattern = f"{code_type}, Variable ({code_min}-{code_max} chars)"
            
        precinct_patterns.append({
            "county_id": f"{county_num}_{county_name}",
            "name_pattern": name_pattern,
            "code_pattern": code_pattern
        })
        
        f.write(f"## County {county_num} - {county_name}\n")
        f.write(f"**Total Voters:** {total_voters:,}\n\n")
        
        for col in district_columns:
            counts = df[col].value_counts(dropna=True)
            if '' in counts.index:
                counts = counts.drop('')
                
            if len(counts) > 0:
                display_name = col.replace('_', ' ').title()
                f.write(f"### {display_name}\n")
                for name, count in counts.items():
                    f.write(f"- {name}: {count:,}\n")
                f.write("\n")
        
        print(f"Processed County {county_num}")

    # Append the Precinct Patterns table at the end
    f.write("---\n\n")
    f.write("## Precinct Patterns Summary\n\n")
    f.write("| County | PRECINCT_NAME Pattern | PRECINCT_CODE Pattern |\n")
    f.write("|---|---|---|\n")
    for pat in precinct_patterns:
        f.write(f"| {pat['county_id']} | {pat['name_pattern']} | {pat['code_pattern']} |\n")

print(f"Finished generating report in {time.time() - start_time:.2f} seconds.")
