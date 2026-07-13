import sqlite3
import pandas as pd
import os
import time

db_path = r"D:\vibe\election-data\local\exports\county_master.db"
parquet_dir = r"D:\vibe\election-data\local\source\parquet"

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

if os.path.exists(db_path):
    os.remove(db_path)

os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)

major_districts = [
    'CONGRESSIONAL_DISTRICT', 'STATE_SENATE_DISTRICT', 'STATE_REPRESENTATIVE_DISTRICT', 
    'COURT_OF_APPEALS', 'STATE_BOARD_OF_EDUCATION'
]
local_districts = [
    'CITY_SCHOOL_DISTRICT', 'COUNTY_COURT_DISTRICT', 'EDU_SERVICE_CENTER_DISTRICT', 
    'EXEMPTED_VILL_SCHOOL_DISTRICT', 'LIBRARY', 'LOCAL_SCHOOL_DISTRICT', 'MUNICIPAL_COURT_DISTRICT', 'WARD'
]

cols_to_read = ['PRECINCT_CODE', 'PRECINCT_NAME', 'RESIDENTIAL_ZIP'] + major_districts + local_districts

start_time = time.time()
counties_data = []
precincts_df_list = []
zip_mapping = []

for i in range(1, 89):
    county_num = f"{i:02d}"
    county_name = OHIO_COUNTIES[i-1]
    file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
    
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_parquet(file_path, columns=cols_to_read)
    total_voters = len(df)
    
    counties_data.append((county_num, county_name, total_voters))
    
    p_df = df.drop_duplicates(subset=['PRECINCT_CODE']).copy()
    p_df.insert(0, 'COUNTY_ID', county_num)
    precincts_df_list.append(p_df)
    
    zips = [z for z in df['RESIDENTIAL_ZIP'].dropna().unique() if str(z).strip() != '']
    for z in zips:
        zip_mapping.append((str(z).strip(), county_num))

print("Writing Counties to DB...")
counties_df = pd.DataFrame(counties_data, columns=['COUNTY_ID', 'COUNTY_NAME', 'TOTAL_VOTERS'])
counties_df.to_sql('counties', conn, index=False, if_exists='replace')

print("Writing Precincts to DB...")
all_precincts = pd.concat(precincts_df_list, ignore_index=True)
all_precincts = all_precincts.fillna('')
all_precincts.to_sql('precincts', conn, index=False, if_exists='replace')

print("Writing Shared ZIPs to DB...")
zips_df = pd.DataFrame(zip_mapping, columns=['ZIP', 'COUNTY_ID']).drop_duplicates()
zips_df.to_sql('county_zips', conn, index=False, if_exists='replace')

# Create some useful indices for fast querying
conn.execute('CREATE INDEX idx_county_id ON precincts (COUNTY_ID)')
conn.execute('CREATE INDEX idx_zip ON county_zips (ZIP)')

conn.close()
print(f"Master SQLite database created successfully in {time.time() - start_time:.2f} seconds.")
