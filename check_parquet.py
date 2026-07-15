import polars as pl
import os

parquet_path = r"D:\vibe\election-data\local\source\parquet_enriched\enriched_voters.parquet"
if not os.path.exists(parquet_path):
    print("Parquet not found at default path. Checking local/source/parquet...")
    parquet_path = r"D:\vibe\election-data\local\source\parquet\raw_voters.parquet"

print(f"Reading {parquet_path}")

try:
    # County 57 is Montgomery
    # Read just a subset to get column names and a few Montgomery rows
    df = pl.scan_parquet(parquet_path).filter(pl.col("COUNTY_NUMBER") == "57").head(5).collect()
    print("Columns:", df.columns)
    print("Sample rows:")
    print(df.select(["PRECINCT_NAME", "PRECINCT_CODE", "CITY", "WARD"]).head())
except Exception as e:
    print(f"Error: {e}")
