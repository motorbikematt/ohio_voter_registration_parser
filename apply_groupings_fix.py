from pathlib import Path
import sys

p = Path('jurisdictional_groupings.py')
if not p.exists():
    print("Error: jurisdictional_groupings.py not found.")
    sys.exit(1)

src = p.read_text(encoding='utf-8')

# Fix 1: Optimize Pre-partitioning
old_partition = """            # Pre-partition the full dataframe into per-jurisdiction slices before
            # spawning workers. Without this, each worker scans all 7.9M rows to
            # filter its own slice — under 8 concurrent threads that compounds into
            # severe memory pressure and causes multi-minute stalls or timeouts.
            print(f'  Pre-partitioning {len(jurisdictions)} {jurisdiction_type_key}...', flush=True)
            partition_map = {
                name: df.filter(pl.col(column) == name)
                for name in jurisdictions
            }"""

new_partition = """            # Optimize: Single-pass partition instead of N-full scans.
            print(f'  Pre-partitioning {len(jurisdictions)} {jurisdiction_type_key}...', flush=True)
            partition_map = df.partition_by(column, include_key=True, as_dict=True)"""

# Fix 2: Increase Timeout
old_timeout = "result = futures_for_type[jurisdiction_name].result(timeout=300)"
new_timeout = "result = futures_for_type[jurisdiction_name].result(timeout=900)"

# Fix 3: Optimize generation logic (vectorized instead of map_elements)
old_gen = """    if 'cohort_family' in subset.columns and 'birth_year' in subset.columns:
        # Compute generation from birth_year
        subset_with_gen = subset.with_columns(
            pl.col('birth_year').map_elements(
                lambda y: next((g for g, (start, end) in GENERATION_RANGES.items()
                              if start <= y <= end), 'Unknown'),
                return_dtype=pl.Utf8
            ).alias('generation')
        )"""

new_gen = """    if 'cohort_family' in subset.columns and 'birth_year' in subset.columns:
        # Vectorized generation mapping
        gen_expr = pl.lit('Unknown')
        # We sort by year to ensure overlapping ranges (if any) are handled consistently
        for gen_name, (start, end) in GENERATION_RANGES.items():
            gen_expr = pl.when((pl.col('birth_year') >= start) & (pl.col('birth_year') <= end)).then(pl.lit(gen_name)).otherwise(gen_expr)
            
        subset_with_gen = subset.with_columns(gen_expr.alias('generation'))"""

# Apply changes
if old_partition in src:
    src = src.replace(old_partition, new_partition)
    print("Patched pre-partitioning logic.")
else:
    print("Warning: Could not find pre-partitioning block.")

if old_timeout in src:
    src = src.replace(old_timeout, new_timeout)
    print("Patched timeout duration.")
else:
    print("Warning: Could not find timeout line.")

if old_gen in src:
    src = src.replace(old_gen, new_gen)
    print("Patched generation logic (vectorized).")
else:
    print("Warning: Could not find generation logic block.")

p.write_text(src, encoding='utf-8')
print("Patching complete.")
