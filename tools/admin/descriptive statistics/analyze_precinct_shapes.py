import pandas as pd
import os
import time
import re
from collections import Counter

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
output_file = r"D:\vibe\election-data\local\exports\precinct_shapes_report.md"

KEYWORDS = {"WARD", "WD", "TWP", "TOWNSHIP", "PRECINCT", "PCT", "CITY", "VILLAGE", "VILL", "CORP"}

def get_name_shape(name):
    if not isinstance(name, str): return "N/A"
    name = name.upper().strip()
    
    tokens = []
    # Split into alphabetic, numeric, and other characters (including spaces)
    parts = re.findall(r'[A-Z]+|[0-9]+|[^A-Z0-9]+', name)
    
    for p in parts:
        if p.strip() == "":
            tokens.append(p) # Keep spaces intact
        elif p in KEYWORDS:
            tokens.append(p)
        elif p.isalpha():
            if len(p) == 1:
                tokens.append("[CHAR]")
            else:
                tokens.append("[WORD]")
        elif p.isnumeric():
            tokens.append("[NUM]")
        else:
            tokens.append(p) # punctuation
            
    return "".join(tokens)

def get_code_shape(code):
    if not isinstance(code, str): return "N/A"
    code = code.strip().upper()
    # Replace digits with N, letters with A, keep punctuation
    shape = re.sub(r'[A-Z]', 'A', code)
    shape = re.sub(r'[0-9]', 'N', shape)
    return shape

os.makedirs(os.path.dirname(output_file), exist_ok=True)
start_time = time.time()

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# Detailed Precinct Patterns by County\n\n")
    f.write("This report analyzes the structural 'shape' of PRECINCT_NAME and PRECINCT_CODE to reveal deterministic rules and clustering for each county.\n")
    f.write("- `[WORD]` = Any alphabetic string > 1 char\n")
    f.write("- `[CHAR]` = Single letter\n")
    f.write("- `[NUM]` = Any number\n")
    f.write("- Keywords like WARD, TWP, CITY are preserved literally.\n\n")
    
    f.write("| County | Dominant CODE Shape | Dominant NAME Shapes |\n")
    f.write("|---|---|---|\n")
    
    for i in range(1, 89):
        county_num = f"{i:02d}"
        county_name = OHIO_COUNTIES[i-1]
        file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
        
        if not os.path.exists(file_path):
            continue
            
        df = pd.read_parquet(file_path, columns=['PRECINCT_NAME', 'PRECINCT_CODE'])
        # We only want unique precincts to avoid being skewed by voter populations
        unique_precincts = df.drop_duplicates(subset=['PRECINCT_CODE']).dropna()
        
        if len(unique_precincts) == 0:
            continue
            
        # Get Code Shapes
        codes = unique_precincts['PRECINCT_CODE'].apply(get_code_shape)
        code_counts = Counter(codes)
        top_code = code_counts.most_common(1)[0]
        code_shape_str = f"`{top_code[0]}` ({top_code[1]/len(codes):.0%})"
        
        # Get Name Shapes
        names = unique_precincts['PRECINCT_NAME'].apply(get_name_shape)
        name_counts = Counter(names)
        top_names = name_counts.most_common(3)
        name_shape_str = "<br>".join([f"`{n[0]}` ({n[1]/len(names):.0%})" for n in top_names])
        
        f.write(f"| {county_num}_{county_name} | {code_shape_str} | {name_shape_str} |\n")
        
        print(f"Processed County {county_num} - {county_name}")

print(f"Finished generating pattern shapes in {time.time() - start_time:.2f} seconds.")
