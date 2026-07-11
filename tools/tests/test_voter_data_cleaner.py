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
    _place_per_precinct,
    _place_slug,
    _ward_map_per_county,
    _ward_parent_slugs,
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


# ── _place_per_precinct (the single place resolver) ───────────────────────
def test_place_city_type_and_normalized_name():
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
    ]))
    assert p['KETTERING 1-A'] == {'type': 'city', 'name': 'KETTERING'}


def test_place_village_is_own_type_with_raw_name():
    # Villages get their own type and keep the RAW value (' VILLAGE' suffix) so
    # the slug matches the village bundle; they no longer resolve as cities.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'FARMERSVILLE', 'VILLAGE': 'FARMERSVILLE VILLAGE'},
    ]))
    assert p['FARMERSVILLE'] == {'type': 'village', 'name': 'FARMERSVILLE VILLAGE'}


def test_place_township_by_column_keeps_name():
    # A township precinct is its own place type carrying the TOWNSHIP name,
    # where the city wrapper drops it entirely.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'WASHINGTON TWP F', 'CITY': '',
         'TOWNSHIP': 'WASHINGTON TOWNSHIP', 'RESIDENTIAL_CITY': 'KETTERING'},
    ]))
    assert p['WASHINGTON TWP F'] == {'type': 'township', 'name': 'WASHINGTON TOWNSHIP'}


def test_place_township_name_token_fallback():
    # Wyandot 'ANTRIM TS' with a blank TOWNSHIP column falls back to the
    # precinct-name token for the display name.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'ANTRIM TS', 'RESIDENTIAL_CITY': 'CAREY'},
    ]))
    assert p['ANTRIM TS'] == {'type': 'township', 'name': 'ANTRIM TS'}


def test_place_township_outranks_minority_village():
    # The Kirby-in-Jackson-Township pattern: township name token wins, the
    # minority village cannot claim the precinct.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': 'KIRBY VILLAGE'},
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': ''},
        {'PRECINCT_NAME': 'JACKSON TS', 'VILLAGE': ''},
    ]))
    assert p['JACKSON TS']['type'] == 'township'


def test_place_resolves_every_precinct():
    # The 'no Other bucket' guarantee: every precinct gets exactly one place.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
        {'PRECINCT_NAME': 'WASHINGTON TWP F', 'TOWNSHIP': 'WASHINGTON TOWNSHIP'},
        {'PRECINCT_NAME': 'FARMERSVILLE', 'VILLAGE': 'FARMERSVILLE VILLAGE'},
        {'PRECINCT_NAME': 'CAREY B', 'RESIDENTIAL_CITY': 'CAREY'},
    ]))
    names = {'KETTERING 1-A', 'WASHINGTON TWP F', 'FARMERSVILLE', 'CAREY B'}
    assert set(p) == names
    assert all(v['type'] and v['name'] for v in p.values())


# == A3: Cuyahoga sub-precinct suffix must not fragment a township =========
def test_place_subprecinct_suffix_does_not_fragment_township():
    # Cuyahoga appends '-00-A'..'-00-I' to a blank-TOWNSHIP township precinct.
    # Without stripping, each suffix would become a distinct fake township;
    # all nine must collapse to one 'OLMSTED TOWNSHIP'.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': f'OLMSTED TOWNSHIP-00-{s}'} for s in 'ABCDEFGHI'
    ]))
    assert len(p) == 9
    assert {v['name'] for v in p.values()} == {'OLMSTED TOWNSHIP'}
    assert all(v['type'] == 'township' for v in p.values())


def test_place_subprecinct_suffix_populated_township_column_unaffected():
    # When TOWNSHIP is populated the strip is irrelevant: the column value is
    # used verbatim and still yields one township.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'OLMSTED TOWNSHIP-00-A', 'TOWNSHIP': 'OLMSTED TOWNSHIP'},
        {'PRECINCT_NAME': 'OLMSTED TOWNSHIP-00-B', 'TOWNSHIP': 'OLMSTED TOWNSHIP'},
    ]))
    assert {v['name'] for v in p.values()} == {'OLMSTED TOWNSHIP'}


def test_place_subprecinct_suffix_only_strips_the_suffix_shape():
    # The strip removes only a trailing '-NN-X'; an ordinary township token
    # like 'ANTRIM TS' (no suffix) is left intact, and 'CHAGRIN FALLS TWP-00-A'
    # keeps its TWP token.
    p = _place_per_precinct(_df([
        {'PRECINCT_NAME': 'ANTRIM TS'},
        {'PRECINCT_NAME': 'CHAGRIN FALLS TWP-00-A'},
    ]))
    assert p['ANTRIM TS']['name'] == 'ANTRIM TS'
    assert p['CHAGRIN FALLS TWP-00-A'] == {'type': 'township', 'name': 'CHAGRIN FALLS TWP'}


def test_city_wrapper_derives_from_place():
    # _dominant_city_per_precinct keeps only type=='city'; villages/townships
    # are absent (the bugfix — villages no longer leak into the city layer).
    rows = _df([
        {'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
        {'PRECINCT_NAME': 'FARMERSVILLE', 'VILLAGE': 'FARMERSVILLE VILLAGE'},
        {'PRECINCT_NAME': 'WASHINGTON TWP F', 'TOWNSHIP': 'WASHINGTON TOWNSHIP'},
    ])
    cities = _dominant_city_per_precinct(rows)
    assert cities == {'KETTERING 1-A': 'KETTERING'}


# ── _place_slug (routing slug parity with the jurisdiction bundles) ───────
def test_place_slug_city_is_bare_name():
    # Cities use the bare name slug; the frontend appends '_city'.
    assert _place_slug({'type': 'city', 'name': 'KETTERING'}, 'montgomery') == 'kettering'


def test_place_slug_township_is_county_prefixed():
    assert _place_slug({'type': 'township', 'name': 'WASHINGTON TOWNSHIP'},
                       'montgomery') == 'montgomery_washington_township'


def test_place_slug_village_keeps_suffix():
    assert _place_slug({'type': 'village', 'name': 'NEW LEBANON VILLAGE'},
                       'montgomery') == 'montgomery_new_lebanon_village'


# == _ward_parent_slugs (route vs bundle slug parity) ======================
def test_ward_parent_slugs_city_gets_city_suffix():
    # route slug is bare (matches precinct place_slug); bundle carries '_city'
    # (matches the data/city bundle filename the frontend appends, v2.js:262).
    assert _ward_parent_slugs('city', 'KETTERING', 'montgomery') == ('kettering', 'kettering_city')


def test_ward_parent_slugs_village_and_township_are_county_prefixed():
    assert _ward_parent_slugs('village', 'WAVERLY VILLAGE', 'pike') == (
        'pike_waverly_village', 'pike_waverly_village')
    assert _ward_parent_slugs('township', 'CANTON', 'stark') == (
        'stark_canton', 'stark_canton')


# == _ward_map_per_county (the single ward resolver) =======================
def test_ward_parent_from_resolved_city_not_string_parsed():
    # KETTERING WARD 2 -> parent city KETTERING, slug kettering_city_kettering_ward_2.
    wm = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'KETTERING 2-A', 'CITY': 'KETTERING CITY', 'WARD': 'KETTERING WARD 2'},
    ]), 'montgomery')
    d = wm['KETTERING WARD 2']
    assert d['parent_type'] == 'city' and d['parent_name'] == 'KETTERING'
    assert d['slug'] == 'kettering_city_kettering_ward_2'
    assert d['abuse'] is False


def test_ward_parent_derived_from_city_column_for_unprefixed_ward():
    # 'FIRST WARD' carries no city in its name; the parent comes from the CITY
    # column via the place resolver -- never from parsing the ward string. Two
    # different cities therefore yield two different entity slugs (the split that
    # keeps the five statewide 'FIRST WARD's from merging).
    marion = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'MARION 1-A', 'CITY': 'MARION CITY', 'WARD': 'FIRST WARD'},
    ]), 'marion')['FIRST WARD']
    chillicothe = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'CHILLICOTHE 1-A', 'CITY': 'CHILLICOTHE CITY', 'WARD': 'FIRST WARD'},
    ]), 'ross')['FIRST WARD']
    assert marion['slug'] == 'marion_city_first_ward'
    assert chillicothe['slug'] == 'chillicothe_city_first_ward'
    assert marion['slug'] != chillicothe['slug']


def test_ward_parent_ignores_abbreviated_ward_string():
    # 'CINTI WARD 3' must resolve its parent from CITY=CINCINNATI, not the 'CINTI'
    # abbreviation baked into the ward value.
    d = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'CINCINNATI 3-A', 'CITY': 'CINCINNATI CITY', 'WARD': 'CINTI WARD 3'},
    ]), 'hamilton')['CINTI WARD 3']
    assert d['parent_name'] == 'CINCINNATI'
    assert d['slug'] == 'cincinnati_city_cinti_ward_3'


def test_ward_village_parent():
    # Waverly's numeric wards (blank CITY) parent to the village.
    d = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'WARD 1', 'VILLAGE': 'WAVERLY VILLAGE', 'WARD': 'WARD 1'},
    ]), 'pike')['WARD 1']
    assert d['parent_type'] == 'village'
    assert d['slug'] == 'pike_waverly_village_ward_1'


def test_ward_abuse_township_name_value():
    # Lucas stuffs a township name into WARD; the WARD-prefix fallback mints a
    # bogus CITY parent, so the value-matches-township-regex guard is what flags it.
    d = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'PRECINCT WASHINGTON 2', 'WARD': 'WASHINGTON TOWNSHIP'},
    ]), 'lucas')['WASHINGTON TOWNSHIP']
    assert d['abuse'] is True


def test_ward_abuse_township_parent():
    # Stark stuffs the township name 'CANTON' into WARD; the precinct resolves to
    # township CANTON, so the township-parent guard flags it (the value 'CANTON'
    # carries no township token).
    d = _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'CANTON TWP 1', 'TOWNSHIP': 'CANTON', 'WARD': 'CANTON'},
    ]), 'stark')['CANTON']
    assert d['parent_type'] == 'township'
    assert d['abuse'] is True


def test_ward_map_empty_when_no_wards():
    assert _ward_map_per_county(_df([
        {'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
    ]), 'montgomery') == {}
