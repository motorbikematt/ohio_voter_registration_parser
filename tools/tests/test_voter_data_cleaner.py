import pytest

# Import the specific function we want to test
from pipeline.voter_data_cleaner import _extract_city

def test_extract_city_standard_dash():
    """Test that standard dash suffixes (e.g. '1-A', '10-B') are stripped."""
    assert _extract_city("KETTERING 1-A") == "KETTERING"
    assert _extract_city("DAYTON 18-B") == "DAYTON"
    assert _extract_city("CINCINNATI 23-C") == "CINCINNATI"

def test_extract_city_ward_suffix():
    """Test that explicit 'WARD' or 'COUNCIL' suffixes are stripped."""
    assert _extract_city("COLUMBUS WARD 9") == "COLUMBUS"
    assert _extract_city("TROTWOOD WARD 2") == "TROTWOOD"
    assert _extract_city("DAYTON WARD 19") == "DAYTON"

def test_extract_city_lone_letter():
    """Test that lone letters at the end are stripped."""
    assert _extract_city("CENTERVILLE-Q") == "CENTERVILLE"
    assert _extract_city("WASHINGTON TWP E") == "WASHINGTON TWP"
    assert _extract_city("DAYTON J") == "DAYTON"

def test_extract_city_no_suffix():
    """Test that names with no valid suffix are left alone."""
    # Pure city names shouldn't be touched
    assert _extract_city("CLEVELAND") == "CLEVELAND"
    assert _extract_city("YELLOW SPRINGS") == "YELLOW SPRINGS"

def test_extract_city_number_only_suffix():
    """Test that three-digit number suffixes are correctly stripped."""
    # Beavercreek 090 matches the \d+ regex and is intentionally stripped
    assert _extract_city("BEAVERCREEK 090") == "BEAVERCREEK"

def test_extract_city_handles_whitespace():
    """Test that extra spaces are handled gracefully."""
    assert _extract_city("  DAYTON 10-A  ") == "DAYTON"
    assert _extract_city(" COLUMBUS WARD 4 ") == "COLUMBUS"
