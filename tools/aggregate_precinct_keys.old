import csv
import logging
from pathlib import Path
import xlsxwriter

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "source" / "precinct_keys"
OUTPUT_FILE = BASE_DIR / "precinct_keys_master.xlsx"

def aggregate_to_excel():
    """
    Reads all CSVs in the data directory and writes them to a single 
    Excel workbook, one tab per file.
    """
    csv_files = sorted(list(DATA_DIR.glob("*_precincts.csv")))
    
    if not csv_files:
        log.error(f"No CSV files found in {DATA_DIR}")
        return

    log.info(f"Aggregating {len(csv_files)} files into {OUTPUT_FILE.name}...")

    # Create workbook
    workbook = xlsxwriter.Workbook(str(OUTPUT_FILE))
    
    # Styles
    header_fmt = workbook.add_format({
        'bold': True,
        'bg_color': '#D7E4BC',
        'border': 1
    })
    
    for csv_file in csv_files:
        # Sheet name is the county name (filename minus '_precincts.csv')
        # Excel sheet names have a 31 character limit
        sheet_name = csv_file.name.replace("_precincts.csv", "")[:31]
        worksheet = workbook.add_worksheet(sheet_name)
        
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                
                for r_idx, row in enumerate(reader):
                    for c_idx, val in enumerate(row):
                        if r_idx == 0:
                            worksheet.write(r_idx, c_idx, val, header_fmt)
                        else:
                            worksheet.write(r_idx, c_idx, val)
                            
            # Auto-filter and freeze top row for usability
            worksheet.autofilter(0, 0, 0, 2)
            worksheet.freeze_panes(1, 0)
            # Set column widths
            worksheet.set_column(0, 0, 15) # county
            worksheet.set_column(1, 1, 15) # precinct_code
            worksheet.set_column(2, 2, 40) # precinct_label
            
        except Exception as e:
            log.error(f"Error processing {csv_file.name}: {e}")

    workbook.close()
    log.info(f"\nSuccessfully created {OUTPUT_FILE.name} with {len(csv_files)} tabs.")

if __name__ == "__main__":
    aggregate_to_excel()
