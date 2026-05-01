# Voter Data Cleaner - Run Locally in VSCode

## Quick Start

### 1. Install Dependencies
Open terminal in VSCode and run:
```bash
pip install -r requirements.txt
```

### 2. Run the Script
```bash
python voter_data_cleaner.py
```

## What It Does

**Input:** `D:\vibe\election-data\source\2026-04-30\voterfile.csv`

**Output:** `D:\vibe\election-data\voter_analysis.xlsx`

### Processing
1. Loads voter CSV (300K+ rows)
2. Cleans birth years (removes invalid dates)
3. Creates decade groupings (1900s, 1910s, etc.)
4. Standardizes party affiliations
5. Constructs full addresses

### Output File Structure

**Sheet 1: "Voter Data"**
- All 300K+ cleaned voter records
- Columns: name, address, birth year, party, districts, election participation, etc.
- Ready for filtering and analysis

**Sheet 2: "Decade Summary"**
- Two columns: Decade | Voter Count
- Uses Excel **COUNTIFS formulas** (not hardcoded values)
- Dynamic: formulas auto-update if you modify the raw data
- **Perfect for creating histograms** — just select and insert chart

## Creating the Histogram in Excel

1. Open `voter_analysis.xlsx`
2. Go to "Decade Summary" sheet
3. Select columns A & B (Decade + Voter Count)
4. Insert → Chart → Column Chart
5. Format as needed (colors, fonts, labels, etc.)

## Troubleshooting

**"File not found" error:**
- Verify the input CSV exists at: `D:\vibe\election-data\source\2026-04-30\voterfile.csv`
- Ensure it has data (not 0 bytes)

**Slow on large files:**
- Normal for 300K+ rows; pandas/openpyxl handle it efficiently
- First run may take 30-60 seconds

**Formula errors in Excel:**
- If you see #REF! errors, check that the sheet names match exactly ("Voter Data" and "Decade Summary")
- Re-open the file in Excel to recalculate formulas

## Customization

Edit these in the script:
- `INPUT_CSV` — change source file path
- `OUTPUT_XLSX` — change output location
- Birth year range (line 18-19) — adjust valid year constraints
- Column widths, colors, fonts — modify cell formatting in the workbook creation section
