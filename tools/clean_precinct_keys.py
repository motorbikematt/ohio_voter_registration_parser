import csv
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "source" / "precinct_keys"

# Configuration
EXPECTED_COLS = ["county", "precinct_code", "precinct_label", "name", "sub"]
KEEP_COLS = ["county", "precinct_code", "precinct_label"]

def clean_csv(file_path: Path):
    """
    Reads a CSV, validates its header, and overwrites it with only the 
    desired columns.
    """
    try:
        # Read the data
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            # 1. Validate Header
            if reader.fieldnames != EXPECTED_COLS:
                log.error(f"FAIL: {file_path.name} has unexpected columns: {reader.fieldnames}")
                return False
                
            rows = list(reader)

        # 2. Write back only the desired columns
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=KEEP_COLS)
            writer.writeheader()
            
            for row in rows:
                # Create a new dict with only the keys we want
                clean_row = {k: row[k] for k in KEEP_COLS}
                writer.writerow(clean_row)
        
        log.info(f"CLEANED: {file_path.name} ({len(rows)} rows)")
        return True
    except Exception as e:
        log.error(f"ERROR processing {file_path.name}: {e}")
        return False

def main():
    if not DATA_DIR.exists():
        log.error(f"Directory not found: {DATA_DIR}")
        return

    csv_files = sorted(list(DATA_DIR.glob("*_precincts.csv")))
    log.info(f"Found {len(csv_files)} files to process.\n")
    
    success_count = 0
    for csv_file in csv_files:
        if clean_csv(csv_file):
            success_count += 1
            
    log.info(f"\nSummary: {success_count}/{len(csv_files)} files cleaned successfully.")

if __name__ == "__main__":
    main()
