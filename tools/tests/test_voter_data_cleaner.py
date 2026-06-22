"""Tests for the municipality-resolution helpers in voter_data_cleaner.

History: an earlier `_extract_city` helper parsed a city name out of the precinct
name by stripping suffixes ('KETTERING 1-A' -> 'KETTERING'). That lossy heuristic
was replaced by `_dominant_city_per_precinct`, which resolves municipality from
the SWVF's authoritative jurisdiction columns (CITY / VILLAGE / WARD / TOWNSHIP)
and only falls back to the postal RESIDENTIAL_CITY as a last resort. These tests
cover the surviving helpers plus the hierarchy resolver.
"""
import polars as pl
import pytest

from pipeline.voter_data_cleaner import (
    _normalize_city_name,
    _precinct_safe_name,
    _dominant_city_per_precinct,
    _TOWNSHIP_NAME_RE,
)


# ── _normalize_city_name ──────────────────────────────────────────────────
def test_normalize_strips_municipal_suffixes():
    assert _normalize_city_name("KETTERING CITY") == "KETTERING"
    assert _normalize_city_name("KIRBY VILLAGE") == "KIRBY"
    assert _normalize_city_name("PLEASANT CORP") == "PLEASANT"


def test_normalize_leaves_bare_names_untouched():
    assert _normalize_city_name("CLEVELAND") == "CLEVELAND"
    assert _normalize_city_name("YELLOW SPRINGS") == "YELLOW SPRINGS"


def test_normalize_handles_blank_and_whitespace():
    assert _normalize_city_name("") == ""
    assert _normalize_city_name("  DAYTON  ") == "DAYTON"


# ── _precinct_safe_name ───────────────────────────────────────────────────
def test_safe_name_slugifies():
    assert _precinct_safe_name("KETTERING 1-A") == "kettering_1_a"
    assert _precinct_safe_name("WASHINGTON TWP F") == "washington_twp_f"
    assert _precinct_safe_name("CLEVELAND -11-K") == "cleveland_11_k"


# ── _TOWNSHIP_NAME_RE ─────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["ANTRIM TS", "WASHINGTON TWP F",
                                  "UNION TOWNSHIP M", "SYCAMORE TS"])
def test_township_regex_matches_township_names(name):
    assert _TOWNSHIP_NAME_RE.search(name.upper())


@pytest.mark.parametrize("name", ["KETTERING 1-A", "CLEVELAND WARD 7",
                                  "CAREY B", "NEVADA"])
def test_township_regex_ignores_non_township_names(name):
    assert not _TOWNSHIP_NAME_RE.search(name.upper())


def test_township_regex_ts_only_trailing():
    # 'TS' must be a trailing abbreviation, not embedded mid-name.
    assert _TOWNSHIP_NAME_RE.search("JACKSON TS")
    assert not _TOWNSHIP_NAME_RE.search("TSAR PRECINCT 1")


# ── _dominant_city_per_precinct (the hierarchy) ───────────────────────────
def _df(rows):
    """Build a county-slice DataFrame from row dicts, filling missing cols ''."""
    cols = ['PRECINCT_NAME', 'CITY', 'VILLAGE', 'WARD', 'TOWNSHIP',
            'RESIDENTIAL_CITY']
    return pl.DataFrame([{c: r.get(c, '') for c in cols} for r in rows])


def test_city_column_wins():
    m = _dominant_city_per_precinct(_df([
        {'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY',
         'RESIDENTIAL_CITY': 'KETTERING'},
    ]))
    assert m['KETTERING 1-A'] == 'KETTERING'


def test_postal_never_overrides_city():
    # Greene's Sugarcreek 151 carries CITY=KETTERING though most rows blank;
    # postal would say DAYTON. CITY must win.
    m = _dominant_city_per_precinct(_df([
        {'PRECINCT_NAME': 'SUGARCREEK 151', 'CITY': 'KETTERING CITY',
         'RESIDENTIAL_CITY': 'DAYTON'},
        {'PRECINCT_NAME': 'SUGARCREEK 151', 'CITY': '',
         'RESIDENTIAL_CITY': 'DAYTON'},
    ]))
    assert m['SUGARCREEK 151'] == 'KETTERING'


def test_township_name_is_not_a_city():
    # Washington Twp F: blank CITY, postal KETTERING -> must resolve to None
    # (absent from map), NOT KETTERING.
    m = _dominant_city_per_precinct(_df([
        {'PRECINCT_NAME': 'WASHINGTON TWP F', 'CITY': '',
         'TOWNSHIP': 'WASHINGTON TOWNSHIP', 'RESIDENTIAL_CITY': 'KETTERING'},
    ]))
    assert 'WASHINGTON TWP F' not in m


def test_township_name_outranks_minority_village():
    # Wyandot's JACKSON TS contains the tiny Village of Kirby for a minority of
    # rows. The precinct-name township token must win -> None, not KIRBY.
    m = _dominant_city_per_precinct(_df([
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': 'KIRBY VILLAGE',
         'RESIDENTIAL_CITY': 'FOREST'},
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': '',
         'RESIDENTIAL_CITY': 'FOREST'},
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': '',
         'RESIDENTIAL_CITY': 'FOREST'},
    ]))
    assert 'JACKSON TS' not in m


def test_postal_last_resort_for_real_town():
    # Wyandot's CAREY B: no authoritative column, name is not a township ->
    # postal RESIDENTIAL_CITY is the last resort and DOES apply.
    m = _dominant_city_per_precinct(_df([
        {'PRECINCT_NAME': 'CAREY B', 'RESIDENTIAL_CITY': 'CAREY'},
    ]))
    assert m['CAREY B'] == 'CAREY'
