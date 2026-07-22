"""
US Census Geography Fetcher

This interactive command-line tool downloads high-resolution TIGER/Line shapefiles 
from the US Census Bureau (2024) for a specified state and consolidates them 
into a single GeoPackage (.gpkg) file with multiple layers.

Usage:
    uv run python tools/fetch_census_geography.py

Features:
    - Interactive FIPS code and state selection
    - Supports multiple geographic resolutions:
      * Counties
      * County Subdivisions (Townships)
      * Places (Cities/Towns)
      * Census Tracts
      * Block Groups
      * Census Blocks
      * ZIP Code Tabulation Areas (ZCTA)
      * Congressional Districts
    - Automatically handles downloading state-specific zip files as well as filtering
      national zip files down to the selected state's boundaries.
    - Consolidates all chosen shapefiles into a single `.gpkg` database for 
      streamlined integration into geospatial pipelines.
"""

import geopandas as gpd
import urllib.request
import tempfile
import os
import sys
from pathlib import Path

FIPS_CODES = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut", "10": "Delaware",
    "11": "District of Columbia", "12": "Florida", "13": "Georgia", "15": "Hawaii",
    "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa",
    "20": "Kansas", "21": "Kentucky", "22": "Louisiana", "23": "Maine",
    "24": "Maryland", "25": "Massachusetts", "26": "Michigan", "27": "Minnesota",
    "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska",
    "32": "Nevada", "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico",
    "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
    "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
    "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas",
    "49": "Utah", "50": "Vermont", "51": "Virginia", "53": "Washington",
    "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming", "60": "American Samoa",
    "66": "Guam", "69": "Northern Mariana Islands", "72": "Puerto Rico", "78": "Virgin Islands"
}

GEOGRAPHIES = {
    "1": {"name": "Counties", "type": "national", "url": "https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip"},
    "2": {"name": "County Subdivisions (Townships)", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_{fips}_cousub.zip"},
    "3": {"name": "Places (Cities/Towns)", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_{fips}_place.zip"},
    "4": {"name": "Census Tracts", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_{fips}_tract.zip"},
    "5": {"name": "Block Groups", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_{fips}_bg.zip"},
    "6": {"name": "Census Blocks", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/TABBLOCK20/tl_2024_{fips}_tabblock20.zip"},
    "7": {"name": "ZIP Code Tabulation Areas", "type": "national", "url": "https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip"},
    "8": {"name": "Congressional Districts", "type": "state", "url": "https://www2.census.gov/geo/tiger/TIGER2024/CD/tl_2024_{fips}_cd119.zip"},
}

def display_fips():
    """
    Displays a formatted, alphabetically-sorted list of all US states and 
    territories along with their corresponding 2-digit FIPS codes.
    """
    print("\n--- Available US Territories & FIPS Codes ---")
    for fips, state in sorted(FIPS_CODES.items()):
        print(f"  {fips}: {state}")
    print("---------------------------------------------\n")

def get_state_fips():
    """
    Prompts the user to enter a state FIPS code or state name.
    Provides options to list all valid codes or quit the application.
    
    Returns:
        str: A valid 2-digit state FIPS code (e.g., '39' for Ohio).
    """
    while True:
        user_input = input("Enter 2-digit State FIPS code, 'list' to see all states, or 'q' to quit: ").strip().lower()
        if user_input == 'q':
            sys.exit(0)
        elif user_input == 'list':
            display_fips()
        elif user_input in FIPS_CODES:
            print(f"-> Selected: {FIPS_CODES[user_input]} ({user_input})")
            return user_input
        else:
            # Check if user typed the state name
            matches = [f for f, s in FIPS_CODES.items() if s.lower() == user_input]
            if matches:
                fips = matches[0]
                print(f"-> Selected: {FIPS_CODES[fips]} ({fips})")
                return fips
            print("Invalid input. Please enter a valid 2-digit FIPS code.")

def get_geography_choices():
    """
    Prompts the user to select one or more geographic resolutions to download.
    Displays an enumerated menu of available Census geography levels.
    
    Returns:
        list[str]: A list of selected dictionary keys corresponding to the 
                   geographies the user wishes to download (e.g., ['1', '2']).
    """
    print("\nAvailable Geographic Resolutions:")
    for key, geo in GEOGRAPHIES.items():
        print(f"  [{key}] {geo['name']}")
    
    choices = input("Enter the numbers of the geographies to download (comma-separated, e.g. '1,2,3'), or 'all': ").strip().lower()
    
    if choices == 'all':
        return list(GEOGRAPHIES.keys())
    
    selected = [c.strip() for c in choices.split(',') if c.strip() in GEOGRAPHIES]
    if not selected:
        print("No valid options selected. Exiting.")
        sys.exit(0)
        
    return selected

def download_and_process(fips, selected_keys, output_dir):
    """
    Downloads the selected Census shapefiles for a given state, extracts them via 
    temporary storage, filters national data down to the state level if necessary, 
    and writes each geometry dataset as a separate layer within a single GeoPackage.
    
    Args:
        fips (str): The 2-digit state FIPS code (e.g., '39').
        selected_keys (list[str]): The keys for the geographies to process.
        output_dir (Path): The directory where the consolidated .gpkg will be saved.
    """
    state_name = FIPS_CODES[fips].replace(' ', '_')
    output_gpkg = output_dir / f"{state_name.lower()}_census_2024.gpkg"
    
    print(f"\n[Consolidating data into: {output_gpkg}]")
    
    for key in selected_keys:
        geo = GEOGRAPHIES[key]
        layer_name = geo["name"].lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
        url = geo["url"].format(fips=fips)
        
        print(f"\n=> Processing {geo['name']}...")
        print(f"   Downloading: {url}")
        
        tmp_path = None
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                zip_data = response.read()
                
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(zip_data)
                tmp_path = tmp.name
                
            print(f"   Reading downloaded shapefile...")
            gdf = gpd.read_file(tmp_path)
            
            # Filter national datasets by FIPS to only include the target state
            if geo["type"] == "national":
                if 'STATEFP' in gdf.columns:
                    gdf = gdf[gdf['STATEFP'] == fips]
                elif 'STATEFP20' in gdf.columns:
                    gdf = gdf[gdf['STATEFP20'] == fips]
                elif 'STATEFP' in url:
                     pass
                else:
                    print(f"   No STATEFP found. Performing spatial filter using state boundary...")
                    
                    # Fetch state boundary for spatial join
                    state_url = "https://www2.census.gov/geo/tiger/TIGER2024/STATE/tl_2024_us_state.zip"
                    req_state = urllib.request.Request(state_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_state) as response_state:
                        state_zip_data = response_state.read()
                        
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as state_tmp:
                        state_tmp.write(state_zip_data)
                        state_tmp_path = state_tmp.name
                        
                    try:
                        state_gdf = gpd.read_file(state_tmp_path)
                        state_gdf = state_gdf[state_gdf['STATEFP'] == fips]
                        
                        if gdf.crs != state_gdf.crs:
                            state_gdf = state_gdf.to_crs(gdf.crs)
                            
                        # Perform spatial join to keep only features intersecting the target state
                        gdf = gpd.sjoin(gdf, state_gdf[['geometry']], how='inner', predicate='intersects')
                        
                        if 'index_right' in gdf.columns:
                            gdf = gdf.drop(columns=['index_right'])
                            
                        print(f"   Spatial filter complete. Reduced dataset down to target state.")
                    finally:
                        if os.path.exists(state_tmp_path):
                            os.remove(state_tmp_path)
            
            print(f"   Writing {len(gdf)} features to layer '{layer_name}'...")
            gdf.to_file(output_gpkg, layer=layer_name, driver="GPKG")
            
        except Exception as e:
            print(f"   Failed to process {geo['name']}: {e}")
            
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            
    print(f"\nSuccess! All requested spatial layers have been saved to {output_gpkg}")

def main():
    """
    Main entry point for the CLI tool. Orchestrates user input, resolves the 
    destination directory within the project workspace, and triggers the download.
    """
    print("\n==============================================")
    print(" US Census Data Consolidator & GPKG Generator")
    print("==============================================")
    
    fips = get_state_fips()
    choices = get_geography_choices()
    
    # Save to local/source/Geo relative to project root
    # Since this runs from the repo root, find the root via the script's path
    root_dir = Path(__file__).resolve().parent.parent
    output_dir = root_dir / "local" / "source" / "Geo"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    download_and_process(fips, choices, output_dir)

if __name__ == "__main__":
    main()
