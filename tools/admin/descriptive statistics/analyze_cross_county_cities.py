import pandas as pd
import os
from collections import defaultdict

parquet_dir = r"D:\vibe\election-data\local\source\parquet"

# Get cross-county cities efficiently
city_to_counties = defaultdict(set)
all_precincts = []

for i in range(1, 89):
    county_num = f"{i:02d}"
    file_path = os.path.join(parquet_dir, f"COUNTY_NUMBER={county_num}", "part-0.parquet")
    if not os.path.exists(file_path): continue
    try:
        df = pd.read_parquet(file_path, columns=['CITY', 'PRECINCT_NAME', 'PRECINCT_CODE'])
        # VITAL: Drop duplicate voters so we only analyze the ~9,000 unique precincts, not 8 million voters!
        df = df.drop_duplicates(subset=['PRECINCT_CODE'])
        
        cities = df['CITY'].dropna().astype(str).str.strip().str.upper().unique()
        for c in cities:
            if c != '': city_to_counties[c].add(county_num)
            
        df['COUNTY_ID'] = county_num
        all_precincts.append(df)
    except Exception: pass

cross_county_cities = {c: countys for c, countys in city_to_counties.items() if len(countys) > 1}

master_df = pd.concat(all_precincts, ignore_index=True)
master_df = master_df.dropna(subset=['CITY', 'PRECINCT_NAME'])
master_df['CITY'] = master_df['CITY'].astype(str).str.strip().str.upper()
master_df['PRECINCT_NAME'] = master_df['PRECINCT_NAME'].astype(str).str.upper()

county_names = {f"{i:02d}": name.upper() for i, name in enumerate([
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
], 1)}

def explicitly_mentions_county(row):
    return county_names.get(row['COUNTY_ID'], '') in row['PRECINCT_NAME']

master_df['is_cross'] = master_df['CITY'].isin(cross_county_cities)
master_df['mentions_county'] = master_df.apply(explicitly_mentions_county, axis=1)

cross_precincts = master_df[master_df['is_cross']]
env_precincts = master_df[~master_df['is_cross']]

cross_mentions = cross_precincts['mentions_county'].sum()
env_mentions = env_precincts['mentions_county'].sum()

md_output = r"D:\vibe\election-data\local\exports\cross_county_cities_analysis.md"
os.makedirs(os.path.dirname(md_output), exist_ok=True)

with open(md_output, "w", encoding="utf-8") as f:
    f.write("# Cross-County Cities Disambiguation Analysis\n\n")
    
    f.write("## 26 Cross-County Cities Detected\n\n")
    for c in sorted(cross_county_cities.keys()):
        counties = sorted(list(cross_county_cities[c]))
        f.write(f"- **{c}** ({len(counties)} Counties): {', '.join(counties)}\n")
        
    f.write("\n## Precinct Naming Disambiguation Pattern\n\n")
    f.write("Do Boards of Elections explicitly inject the County Name into the `PRECINCT_NAME` if the city crosses borders, to avoid confusion with the other half of the city?\n\n")
    
    f.write(f"- **Number of cross-county precincts analyzed:** {len(cross_precincts)}\n")
    f.write(f"- **Number of completely enveloped precincts analyzed:** {len(env_precincts)}\n\n")
    
    cross_pct = (cross_mentions / max(1, len(cross_precincts))) * 100
    env_pct = (env_mentions / max(1, len(env_precincts))) * 100
    
    f.write(f"- Cross-county precincts explicitly mentioning their county in the name: **{cross_mentions} / {len(cross_precincts)} ({cross_pct:.2f}%)**\n")
    f.write(f"- Enveloped precincts explicitly mentioning their county in the name: **{env_mentions} / {len(env_precincts)} ({env_pct:.2f}%)**\n\n")
    
    if cross_pct > env_pct * 1.5:
        f.write("> **Conclusion:** Yes, there is a statistical signal! Precincts that belong to cross-county cities are more likely to explicitly mention their parent county in their string name to disambiguate themselves from their neighbors across the border.\n")
    else:
        f.write("> **Conclusion:** No strong signal detected. Boards of Elections do not appear to explicitly label cross-county city precincts with the county name significantly more often than standard enveloped cities.\n")

print(f"Report successfully saved to {md_output}")
