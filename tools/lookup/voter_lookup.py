import polars as pl
from pathlib import Path
from datetime import datetime
import argparse
import sys

def run_global_parquet_search(term: str = None, parquet_dir: str = None):
    # 1. Handle Prompting
    if not term:
        term = input("Enter search term: ").strip()
    if not term:
        print("No search term provided. Exiting.")
        return

    # Resolve paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent
    if parquet_dir is None:
        base_path = project_root / "local" / "source" / "parquet"  # PATCH: Rerouted to local/ workspace
    else:
        base_path = Path(parquet_dir).resolve()

    if not base_path.exists():
        print(f"Error: Parquet directory '{base_path}' not found.")
        return

    term_upper = term.upper()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = project_root / f"search_{term.replace(' ', '_')}_{timestamp}.csv"

    print(f"\nGLOBAL PARQUET SEARCH")
    print(f"Term:   '{term}'")
    print(f"Source: {base_path}")
    print("-" * 60)

    partitions = list(base_path.glob("COUNTY_NUMBER=*"))
    if not partitions:
        print(f"No county partitions found in {base_path}")
        return

    all_matches = []
    
    for p in sorted(partitions):
        c_num = p.name.split("=")[1]
        try:
            lf = pl.scan_parquet(p)
            
            # Global search across all columns
            filter_expr = pl.any_horizontal(
                pl.all().cast(pl.String).str.to_uppercase().str.contains(term_upper)
            )
            
            match = lf.filter(filter_expr).collect()
            
            if not match.is_empty():
                match = match.with_columns(pl.lit(c_num).alias("COUNTY_NUMBER"))
                all_matches.append(match)
                print(f"  County {c_num}: Found {len(match):,} matches")
                
        except Exception as e:
            continue

    if not all_matches:
        print(f"\nNo records found containing '{term}'.")
        return

    # Combine results
    final_df = pl.concat(all_matches)
    
    # --- RESTORED SUMMARY VIEW ---
    print("-" * 60)
    print(f"TOTAL MATCHES FOUND: {len(final_df):,}")
    
    # Show Top combinations (Jurisdictional focus for quick sanity check)
    print("\nTOP JURISDICTIONAL COMBINATIONS:")
    juris_cols = [c for c in ["CITY", "TOWNSHIP", "VILLAGE", "PRECINCT_NAME"] if c in final_df.columns]
    summary = final_df.group_by(["COUNTY_NUMBER"] + juris_cols).agg(pl.len().alias("Voters")).sort("Voters", descending=True)
    with pl.Config(tbl_rows=20, tbl_width_chars=120):
        print(summary.head(20))

    # Show County Breakdown
    print("\nBREAKDOWN BY COUNTY:")
    county_sum = final_df.group_by("COUNTY_NUMBER").agg(pl.len().alias("Voters")).sort("Voters", descending=True)
    print(county_sum)
    
    # --- FILE EXPORT ---
    print("-" * 60)
    print(f"Writing all 135 columns for {len(final_df):,} records to: {output_file.name}")
    try:
        final_df.write_csv(output_file)
        print("Export Complete.")
    except Exception as e:
        print(f"Error writing CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Global search across all columns in Parquet files.")
    parser.add_argument("term", nargs="?", help="Search term (optional, will prompt if omitted)")
    parser.add_argument("--dir", default=None, help="Path to parquet directory")
    
    args = parser.parse_args()
    run_global_parquet_search(args.term, args.dir)
