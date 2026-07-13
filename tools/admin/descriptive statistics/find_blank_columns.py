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
output_file = r"D:\vibe\election-data\local\exports\blank_columns_report.md"

def is_column_blank(series):
    # If all values are NaN/Null
    if series.isna().all():
        return True
    
    # If string/object type, check if all non-null values are empty strings or whitespace
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        valid_values = series.dropna().astype(str).str.strip()
        if (valid_values == '').all():
            return True
            
    return False

os.makedirs(os.path.dirname(output_file), exist_ok=True)
start_time = time.time()

with open(output_file, "w", encoding="utf-8") as f:
    f.write("# Blank or Unused Columns by County\n\n")
    f.write("This report lists all columns in the voter data files that are completely empty (containing only nulls, empty strings, or whitespace) for each specific county.\n\n")
    
    for i in range(1, 89):
        county_num = f"{i:02d}"
        county_name = OHIO_COUNTIES[i-1]
        file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
        
        if not os.path.exists(file_path):
            continue
            
        # Read the entire dataframe to check all columns
        df = pd.read_parquet(file_path)
        
        blank_columns = []
        for col in df.columns:
            if is_column_blank(df[col]):
                blank_columns.append(col)
                
        f.write(f"## County {county_num} - {county_name}\n")
        if blank_columns:
            f.write(f"Found **{len(blank_columns)}** completely blank columns:\n")
            for col in blank_columns:
                f.write(f"- `{col}`\n")
        else:
            f.write("No completely blank columns found.\n")
            
        f.write("\n")
        print(f"Processed County {county_num} - Found {len(blank_columns)} blank columns")

print(f"Finished analyzing blank columns in {time.time() - start_time:.2f} seconds.")
