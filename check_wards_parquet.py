import polars as pl
import os

parquet_path = r"D:\vibe\election-data\local\source\parquet_enriched\enriched_voters.parquet"
if not os.path.exists(parquet_path):
    parquet_path = r"D:\vibe\election-data\local\source\parquet\raw_voters.parquet"

df = pl.scan_parquet(parquet_path).filter((pl.col("COUNTY_NUMBER") == "57") & pl.col("WARD").is_not_null())
ward_df = df.group_by(["CITY", "WARD"]).agg(pl.len().alias("count")).collect().sort(["CITY", "WARD"])

ward_df.write_csv(r"D:\vibe\election-data\ward_counts.csv")
