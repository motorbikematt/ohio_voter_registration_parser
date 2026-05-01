# Ohio Voter Registration Parser

Parse and clean Ohio voter registration CSV files (from Ohio Board of Elections) into analysis-ready Excel workbooks with decade summaries for demographic insights and histogram generation.

## Features

- **CSV Parsing & Cleaning**: Loads voter registration data and validates/standardizes key fields
- **Demographic Grouping**: Automatically groups voters by birth decade
- **Excel Export**: Creates multi-sheet workbooks with:
  - Full cleaned dataset (300K+ rows)
  - Decade summary table with dynamic formulas for charting
- **Excel Formula Integration**: Uses COUNTIFS formulas (not hardcoded values) so charts auto-update when data changes

## Installation

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.7+
- pandas >= 2.0.0
- openpyxl >= 3.10.0

## Usage

### Basic Run

```bash
python voter_data_cleaner.py
```

**Input:** `D:\vibe\election-data\source\2026-04-30\voterfile.csv`

**Output:** `D:\vibe\election-data\voter_analysis.xlsx`

### Customize Paths

Edit the configuration at the top of `voter_data_cleaner.py`:

```python
INPUT_CSV = r"D:\vibe\election-data\source\2026-04-30\voterfile.csv"
OUTPUT_XLSX = r"D:\vibe\election-data\voter_analysis.xlsx"
```

## Output Format

### Sheet 1: "Voter Data"
Complete cleaned voter records with columns:
- Name (LASTN, FIRSTN, MIDDLEN, PREFIXN, SUFFIXN)
- Address (STNUM, STDIR, STNAME, APT, CITY, ZIP)
- Demographics (BIRTHYEAR, Decade, PARTYAFFIL)
- Jurisdictions (Congress, Senate, House, districts, etc.)
- Election Participation (8-digit date columns: 20251104G, 20250506PS, etc.)

Data cleaning applied:
- Birth year validation (1900–2024)
- Address standardization (concatenation, whitespace normalization)
- Party affiliation standardization
- Invalid records removed

### Sheet 2: "Decade Summary"
Ready-to-chart summary table:

| Decade | Voter Count |
|--------|------------|
| 1900   | 1,234 |
| 1910   | 5,678 |
| 1920   | 12,345 |
| ... | ... |

**Formulas:** Uses COUNTIFS to dynamically count voters per decade from Sheet 1. If you filter or modify the raw data, counts auto-update.

## Creating Histograms in Excel

1. Open the generated `.xlsx` file
2. Go to "Decade Summary" sheet
3. Select columns A & B (Decade + Voter Count)
4. **Insert → Chart → Column Chart**
5. Format as desired (colors, fonts, labels, gridlines, etc.)

The dynamic formulas mean your chart automatically reflects any changes to the underlying voter data.

## Data Processing Performance

- **300K rows**: ~30–60 seconds (first run)
- **Memory efficient**: pandas/openpyxl handle large datasets
- **Scalable**: Works with any size voter file

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `FileNotFoundError: voterfile.csv` | Verify input file path exists and has data (not 0 bytes) |
| `#REF!` errors in Excel | Check sheet names match exactly: "Voter Data" and "Decade Summary" |
| Script runs slowly | Normal for 300K+ rows; pandas is optimized for large files |
| Empty output workbook | Ensure input CSV has content; check data format matches expectations |

## Technical Details

- **Data Validation**: Birth years outside 1900–2024 range removed
- **String Normalization**: Addresses cleaned via regex (extra whitespace removed)
- **Decade Calculation**: `Decade = (BirthYear // 10) * 10`
- **Formula Recalculation**: Excel automatically recalculates COUNTIFS formulas on open; no manual steps required

## License

MIT

## Data Source

Ohio Board of Elections (lookup.boe.ohio.gov/vtrapp)

## Author

election-data analysis project
