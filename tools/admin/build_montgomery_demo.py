import os
import re
import pandas as pd
import polars as pl
import geopandas as gpd

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET_PATH = os.path.join(REPO_ROOT, "local", "source", "parquet_enriched", "enriched_voters.parquet")
if not os.path.exists(PARQUET_PATH):
    PARQUET_PATH = os.path.join(REPO_ROOT, "local", "source", "parquet", "raw_voters.parquet")

GEO_DIR = os.path.join(REPO_ROOT, "local", "source", "Geo", "57_Montgomery", "SHAPEFILE_BOARD_OF_ELECTIONS (2)")

def make_join_key(s):
    if not isinstance(s, str): return s
    s = s.upper()
    s = s.replace(' TOWNSHIP', ' TWP')
    s = s.replace('WEST CARROLLTON', 'W CARROLLTON')
    s = re.sub(r'(^|\D)0+(\d+)', r'\1\2', s)
    s = re.sub(r'[\s\-]', '', s)
    return s

def process_layer(df, shp_filename, parq_col, shp_col, shp_prefix, out_filename, desc_col="DESCRIPTIO"):
    print(f"Aggregating {parq_col} totals...")
    agg = df.filter(pl.col(parq_col).is_not_null()).group_by(parq_col).agg([
        pl.len().alias("TOTAL_VOTERS"),
        (pl.col("PARTY_LABEL") == "DEM").sum().alias("DEM_VOTERS"),
        (pl.col("PARTY_LABEL") == "REP").sum().alias("REP_VOTERS"),
        (pl.col("PARTY_LABEL") == "UNC").sum().alias("UNA_VOTERS"),
    ]).to_pandas()
    
    # Strip leading zeros for robust integer string matching
    agg["JOIN_KEY"] = agg[parq_col].apply(lambda x: str(int(x)) if pd.notnull(x) and str(x).isdigit() else x)
    
    print(f"Loading {shp_filename}...")
    shp_path = os.path.join(GEO_DIR, shp_filename)
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(epsg=4326)
    
    gdf["JOIN_KEY"] = gdf[shp_col].str.replace(shp_prefix, "").apply(lambda x: str(int(x)) if pd.notnull(x) and str(x).isdigit() else x)
    
    print(f"Merging {shp_filename}...")
    merged = gdf.merge(agg, on="JOIN_KEY", how="left")
    
    for col in ["TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS"]:
        merged[col] = merged[col].fillna(0).astype(int)
    
    # Keep description if available
    desc = desc_col if desc_col in merged.columns else ("DESRIPTION" if "DESRIPTION" in merged.columns else shp_col)
    
    cols_to_keep = [desc, "JOIN_KEY", "TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS", "geometry"]
    out_gdf = merged[cols_to_keep]
    
    out_path = os.path.join(REPO_ROOT, "docs", "data", out_filename)
    print(f"Writing {out_path}...")
    out_gdf.to_file(out_path, driver="GeoJSON")

def run():
    print("Loading parquet data...")
    df = pl.scan_parquet(PARQUET_PATH).filter(pl.col("COUNTY_NUMBER") == "57").collect()
    
    # PRECINCTS
    print("Aggregating precinct totals...")
    precinct_agg = df.group_by("PRECINCT_NAME").agg([
        pl.len().alias("TOTAL_VOTERS"),
        (pl.col("PARTY_LABEL") == "DEM").sum().alias("DEM_VOTERS"),
        (pl.col("PARTY_LABEL") == "REP").sum().alias("REP_VOTERS"),
        (pl.col("PARTY_LABEL") == "UNC").sum().alias("UNA_VOTERS"),
    ]).to_pandas()
    precinct_agg["JOIN_KEY"] = precinct_agg["PRECINCT_NAME"].apply(make_join_key)
    
    print("Loading precinct shapefile...")
    precincts_gdf = gpd.read_file(os.path.join(GEO_DIR, "Precinct_2022_Polygon.shp")).to_crs(epsg=4326)
    precincts_gdf["JOIN_KEY"] = precincts_gdf["VNAME"].apply(make_join_key)
    
    precincts_merged = precincts_gdf.merge(precinct_agg, on="JOIN_KEY", how="left")
    for col in ["TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS"]:
        precincts_merged[col] = precincts_merged[col].fillna(0).astype(int)
    
    precincts_out = precincts_merged[["VNAME", "TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS", "geometry"]]
    precincts_out.to_file(os.path.join(REPO_ROOT, "docs", "data", "montgomery_precincts.geojson"), driver="GeoJSON")
    
    # WARDS
    print("Aggregating ward totals...")
    ward_agg = df.filter(pl.col("WARD").is_not_null()).group_by(["CITY", "WARD"]).agg([
        pl.len().alias("TOTAL_VOTERS"),
        (pl.col("PARTY_LABEL") == "DEM").sum().alias("DEM_VOTERS"),
        (pl.col("PARTY_LABEL") == "REP").sum().alias("REP_VOTERS"),
        (pl.col("PARTY_LABEL") == "UNC").sum().alias("UNA_VOTERS"),
    ]).to_pandas()
    
    wards_gdf = gpd.read_file(os.path.join(GEO_DIR, "ward_polygon.shp")).to_crs(epsg=4326)
    def normalize_ward(desc):
        if not isinstance(desc, str): return desc
        desc = desc.upper()
        desc = re.sub(r' WARD 0(\d)', r' WARD \1', desc)
        return desc
    wards_gdf["JOIN_WARD"] = wards_gdf["DESCRIPTIO"].apply(normalize_ward)
    wards_merged = wards_gdf.merge(ward_agg, left_on="JOIN_WARD", right_on="WARD", how="left")
    for col in ["TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS"]:
        wards_merged[col] = wards_merged[col].fillna(0).astype(int)
    wards_out = wards_merged[["DESCRIPTIO", "JOIN_WARD", "TOTAL_VOTERS", "DEM_VOTERS", "REP_VOTERS", "UNA_VOTERS", "geometry"]]
    wards_out.to_file(os.path.join(REPO_ROOT, "docs", "data", "montgomery_wards.geojson"), driver="GeoJSON")

    # HOUSE
    process_layer(
        df, "house_polygon.shp", "STATE_REPRESENTATIVE_DISTRICT", "HOUSE", "HS", "montgomery_house.geojson"
    )
    
    # SENATE
    process_layer(
        df, "senate_polygon.shp", "STATE_SENATE_DISTRICT", "SENATE", "SN", "montgomery_senate.geojson"
    )
    
    # CONGRESS
    process_layer(
        df, "us_cong_polygon.shp", "CONGRESSIONAL_DISTRICT", "US", "CN", "montgomery_congress.geojson", desc_col="DESRIPTION"
    )

    print("Done!")

if __name__ == "__main__":
    run()
