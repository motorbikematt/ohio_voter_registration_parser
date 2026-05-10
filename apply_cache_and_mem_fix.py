import polars as pl
from pathlib import Path
import sys

# ── Paths ─────────────────────────────────────────────────────────────────────
p_v2 = Path('voter_data_cleaner_v2.py')
p_jg = Path('jurisdictional_groupings.py')

# ── Patch voter_data_cleaner_v2.py ───────────────────────────────────────────
if p_v2.exists():
    src = p_v2.read_text(encoding='utf-8')
    
    # 1. Add Constant
    if 'PARQUET_ENRICHED_DIR' not in src:
        src = src.replace(
            'PARQUET_DIR  = BASE_DIR / "source" / "parquet"',
            'PARQUET_DIR  = BASE_DIR / "source" / "parquet"\nPARQUET_ENRICHED_DIR = BASE_DIR / "source" / "parquet_enriched"'
        )

    # 2. Add Caching Logic to run_ohio_analysis
    # We need to find the enrichment step and wrap it.
    # Looking for: df = clean_voter_data(df, src_date, logger)
    old_enrich = '    df = clean_voter_data(df, src_date, logger)'
    new_enrich = """    # ── Persistent Enrichment Cache ──────────────────────────────────────────
    PARQUET_ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = PARQUET_ENRICHED_DIR / "enriched_voters.parquet"
    
    use_cache = False
    if cache_path.exists():
        # Check if cache is newer than any partition in the raw parquet dir
        cache_mt = cache_path.stat().st_mtime
        raw_partitions = list(PARQUET_DIR.glob("COUNTY_NUMBER=*"))
        if raw_partitions:
            latest_raw = max(p.stat().st_mtime for p in raw_partitions)
            if cache_mt > latest_raw:
                use_cache = True
    
    if use_cache:
        logger.info("Loading enriched voter data from persistent cache...")
        df = pl.read_parquet(cache_path)
    else:
        logger.info("Enriching voter data (this will take ~80s)...")
        df = clean_voter_data(df, src_date, logger)
        logger.info("Saving enriched voter data to persistent cache...")
        df.write_parquet(cache_path, compression="zstd")
    # ──────────────────────────────────────────────────────────────────────────"""
    
    if old_enrich in src:
        src = src.replace(old_enrich, new_enrich)
        print("Patched v2 with persistent cache.")
    
    p_v2.write_text(src, encoding='utf-8')


# ── Patch jurisdictional_groupings.py ────────────────────────────────────────
if p_jg.exists():
    src = p_jg.read_text(encoding='utf-8')
    
    # 1. Add Constant
    if 'PARQUET_ENRICHED_DIR' not in src:
        src = src.replace(
            'PARQUET_DIR = BASE_DIR / "source" / "parquet"',
            'PARQUET_DIR = BASE_DIR / "source" / "parquet"\nPARQUET_ENRICHED_DIR = BASE_DIR / "source" / "parquet_enriched"'
        )

    # 2. Add Caching Logic to main
    old_load = """    logger.info('Loading voter parquet cache...')
    df = pl.read_parquet(PARQUET_DIR)
    logger.info(f'Loaded {df.height:,} rows x {df.width} columns')

    logger.info('Enriching voter data (cohort classification + demographics)...')
    # get_source_date handles the manifest loading internally
    from voter_data_cleaner_v2 import clean_voter_data, get_source_date
    src_date = get_source_date(logger)
    df = clean_voter_data(df, src_date, logger)"""
    
    new_load = """    # ── Persistent Enrichment Cache ──────────────────────────────────────────
    PARQUET_ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = PARQUET_ENRICHED_DIR / "enriched_voters.parquet"
    
    use_cache = False
    if cache_path.exists():
        cache_mt = cache_path.stat().st_mtime
        raw_partitions = list(PARQUET_DIR.glob("COUNTY_NUMBER=*"))
        if raw_partitions:
            latest_raw = max(p.stat().st_mtime for p in raw_partitions)
            if cache_mt > latest_raw:
                use_cache = True
    
    if use_cache:
        logger.info("Loading enriched voter data from persistent cache...")
        df = pl.read_parquet(cache_path)
    else:
        logger.info('Loading voter parquet cache...')
        df = pl.read_parquet(PARQUET_DIR)
        logger.info(f'Loaded {df.height:,} rows x {df.width} columns')
        logger.info('Enriching voter data (this will take ~80s)...')
        from voter_data_cleaner_v2 import clean_voter_data, get_source_date
        src_date = get_source_date(logger)
        df = clean_voter_data(df, src_date, logger)
        logger.info("Saving enriched voter data to persistent cache...")
        df.write_parquet(cache_path, compression="zstd")
    # ──────────────────────────────────────────────────────────────────────────"""

    # 3. Sequential Aggregation Fix (Memory Stability)
    old_agg = """            # Submit one task per jurisdiction; each worker receives its pre-sliced
            # frame so its internal filter is a trivial no-op on a small subset.
            futures_for_type = {}
            for jurisdiction_name in jurisdictions:
                future = executor.submit(
                    aggregate_jurisdiction,
                    partition_map[jurisdiction_name],
                    column, jurisdiction_name, display, election_cols, today, logger,
                )
                futures_for_type[jurisdiction_name] = future

            # Collect results and print a rolling progress counter so the terminal
            # does not appear frozen during long aggregation passes.
            results = []
            total = len(jurisdictions)
            for idx, jurisdiction_name in enumerate(jurisdictions, 1):
                print(f'\\r  Processing {jurisdiction_type_key}: {idx}/{total} ({jurisdiction_name[:30]})', end='', flush=True)
                try:
                    result = futures_for_type[jurisdiction_name].result(timeout=120)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f'Timeout aggregating {jurisdiction_type_key} / {jurisdiction_name}: {e}')
            print()"""

    new_agg = """            # ── Sequential Aggregation (Memory Stability) ─────────────────────────
            # Replaced ThreadPoolExecutor with sequential processing to eliminate
            # the 2x memory peak caused by partition_by buffer copies.
            results = []
            total = len(jurisdictions)
            for idx, jurisdiction_name in enumerate(jurisdictions, 1):
                print(f'\\r  Processing {jurisdiction_type_key}: {idx}/{total} ({jurisdiction_name[:30]})', end='', flush=True)
                
                # Slices are created and freed one at a time
                subset = df.filter(pl.col(column) == jurisdiction_name)
                if not subset.is_empty():
                    result = aggregate_jurisdiction(
                        subset, column, jurisdiction_name, display, 
                        election_cols, today, logger
                    )
                    if result:
                        results.append(result)
                del subset
            print()"""

    if old_load in src:
        src = src.replace(old_load, new_load)
        print("Patched groupings with persistent cache.")
    
    if old_agg in src:
        src = src.replace(old_agg, new_agg)
        print("Patched groupings with sequential aggregation.")

    p_jg.write_text(src, encoding='utf-8')

print("All patches applied.")
