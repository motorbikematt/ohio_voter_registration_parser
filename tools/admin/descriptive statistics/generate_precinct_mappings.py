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

major_districts = [
    'CONGRESSIONAL_DISTRICT', 'STATE_SENATE_DISTRICT', 'STATE_REPRESENTATIVE_DISTRICT', 
    'COURT_OF_APPEALS', 'STATE_BOARD_OF_EDUCATION'
]
local_districts = [
    'CITY_SCHOOL_DISTRICT', 'COUNTY_COURT_DISTRICT', 'EDU_SERVICE_CENTER_DISTRICT', 
    'EXEMPTED_VILL_SCHOOL_DISTRICT', 'LIBRARY', 'LOCAL_SCHOOL_DISTRICT', 'MUNICIPAL_COURT_DISTRICT', 'WARD'
]

# Do not request COUNTY_NUMBER from parquet in case it's strictly a partition folder name
cols_to_read = ['PRECINCT_CODE', 'PRECINCT_NAME'] + major_districts + local_districts

start_time = time.time()
all_precincts = []

print("Loading county data...")
for i in range(1, 89):
    county_num = f"{i:02d}"
    file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
    
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_parquet(file_path, columns=cols_to_read)
    
    # Drop duplicates so we just have a catalog of precincts
    df_unique = df.drop_duplicates(subset=['PRECINCT_CODE']).copy()
    
    df_unique['COUNTY_NUMBER'] = county_num
    df_unique['COUNTY_NAME'] = OHIO_COUNTIES[i-1]
    
    all_precincts.append(df_unique)

print("Concatenating and processing...")
full_df = pd.concat(all_precincts, ignore_index=True)
full_df[major_districts + local_districts] = full_df[major_districts + local_districts].fillna('')

os.makedirs(r"D:\vibe\election-data\local\exports", exist_ok=True)

# 1. Precincts per county
out1 = r"D:\vibe\election-data\local\exports\precincts_per_county.md"
print(f"Generating {out1}...")
with open(out1, "w", encoding="utf-8") as f:
    f.write("# Precincts per County\n\n")
    for county_num, group in full_df.groupby('COUNTY_NUMBER'):
        county_name = group['COUNTY_NAME'].iloc[0]
        f.write(f"## {county_num}_{county_name} ({len(group)} Precincts)\n")
        group = group.sort_values('PRECINCT_CODE')
        for _, row in group.iterrows():
            f.write(f"- `{row['PRECINCT_CODE']}` : {row['PRECINCT_NAME']}\n")
        f.write("\n")

# Helper for district reports
def write_district_report(outfile, title, district_cols, df):
    print(f"Generating {outfile}...")
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        for col in district_cols:
            display_name = col.replace('_', ' ').title()
            f.write(f"## {display_name}\n\n")
            
            # Sort district names carefully to put numbers in order
            def sort_key(x):
                try:
                    return (0, int(x))
                except ValueError:
                    return (1, x)
            
            districts = sorted([d for d in df[col].unique() if str(d).strip() != ''], key=sort_key)
            
            for dist in districts:
                sub_df = df[df[col] == dist].sort_values(['COUNTY_NUMBER', 'PRECINCT_CODE'])
                f.write(f"### District: {dist} ({len(sub_df)} Precincts)\n")
                for _, row in sub_df.iterrows():
                    f.write(f"- `{row['COUNTY_NUMBER']}-{row['PRECINCT_CODE']}` : {row['PRECINCT_NAME']} ({row['COUNTY_NAME']})\n")
                f.write("\n")

# 2. Precincts per major district
out2 = r"D:\vibe\election-data\local\exports\precincts_per_major_district.md"
write_district_report(out2, "Precincts per Major District", major_districts, full_df)

# 3. Precincts per local district
out3 = r"D:\vibe\election-data\local\exports\precincts_per_local_district.md"
write_district_report(out3, "Precincts per Local District", local_districts, full_df)

print(f"All reports generated successfully in {time.time() - start_time:.2f} seconds.")
