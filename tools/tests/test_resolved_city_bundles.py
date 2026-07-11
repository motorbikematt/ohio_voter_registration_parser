"""Tests for the A2 resolved-city grouping key (jurisdictional_groupings.
_add_resolved_city_column).

Contract (CLAUDE.md 4, two-totals hero semantics): the CITY stats bundles group
on `_resolved_city`, which equals the raw CITY value verbatim wherever CITY is
populated, and only falls back to the single place resolver for counties that
populate CITY for *zero* rows (Cuyahoga-style ward/residential encoding). A county
that populates CITY for even one row must be byte-identical to grouping on raw CITY
-- a blank-CITY row there is never silently reassigned to a city hero.
"""
import logging

import polars as pl

import pipeline.jurisdictional_groupings as jg

_LOG = logging.getLogger("test_resolved_city")
_LOG.addHandler(logging.NullHandler())

_COLS = ['COUNTY_NUMBER', 'PRECINCT_NAME', 'CITY', 'VILLAGE', 'WARD',
         'TOWNSHIP', 'RESIDENTIAL_CITY']


def _df(rows):
    return pl.DataFrame([{c: r.get(c, '') for c in _COLS} for r in rows])


def _resolved(rows):
    out = jg._add_resolved_city_column(_df(rows), _LOG)
    return out['_resolved_city'].to_list()


def test_populated_city_kept_verbatim():
    # Raw CITY (with its ' CITY' suffix) is preserved so the slug is unchanged.
    vals = _resolved([
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
    ])
    assert vals == ['KETTERING CITY']
    assert jg._slugify('KETTERING CITY') == 'kettering_city'


def test_blank_city_in_populated_county_stays_null():
    # County 57 populates CITY, so a blank-CITY row -- even one carrying a ward
    # prefix -- must NOT gain a resolved city (byte-identical protection).
    out = jg._add_resolved_city_column(_df([
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY',
         'WARD': 'KETTERING WARD 1'},
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'KETTERING 9-Z', 'CITY': '',
         'WARD': 'KETTERING WARD 9'},
    ]), _LOG)
    by_prec = dict(zip(out['PRECINCT_NAME'].to_list(), out['_resolved_city'].to_list()))
    assert by_prec['KETTERING 1-A'] == 'KETTERING CITY'
    assert by_prec['KETTERING 9-Z'] is None


def test_zero_city_county_resolves_ward_encoded_municipality():
    # Cuyahoga (18): CITY blank for every row, municipality encoded via WARD
    # prefix. The fallback resolves it and re-suffixes ' CITY' so the slug matches
    # the raw-CITY bundle convention (cleveland_city).
    out = jg._add_resolved_city_column(_df([
        {'COUNTY_NUMBER': '18', 'PRECINCT_NAME': 'CLEVELAND WARD 7', 'WARD': 'CLEVELAND WARD 7'},
        {'COUNTY_NUMBER': '18', 'PRECINCT_NAME': 'CLEVELAND WARD 7', 'WARD': 'CLEVELAND WARD 7'},
    ]), _LOG)
    assert set(out['_resolved_city'].to_list()) == {'CLEVELAND CITY'}
    assert jg._slugify('CLEVELAND CITY') == 'cleveland_city'


def test_zero_city_county_uses_residential_last_resort():
    # A Cuyahoga suburb with no CITY/WARD but a postal RESIDENTIAL_CITY resolves
    # via the place resolver's last resort -- matching the geo tree's city node.
    out = jg._add_resolved_city_column(_df([
        {'COUNTY_NUMBER': '18', 'PRECINCT_NAME': 'WESTLAKE 1-A', 'RESIDENTIAL_CITY': 'WESTLAKE'},
    ]), _LOG)
    assert out['_resolved_city'].to_list() == ['WESTLAKE CITY']


def test_zero_city_county_does_not_invent_city_for_township():
    # A township precinct in a zero-CITY county must stay null -- the resolver
    # types it as a township, so it never becomes a city bundle.
    out = jg._add_resolved_city_column(_df([
        {'COUNTY_NUMBER': '18', 'PRECINCT_NAME': 'OLMSTED TOWNSHIP-00-A'},
    ]), _LOG)
    assert out['_resolved_city'].to_list() == [None]


def test_grouping_byte_identical_for_populated_county():
    # The multiset of (city -> count) groups must match between raw CITY and
    # _resolved_city for a populated-CITY county (blank rows excluded both ways).
    rows = [
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'KETTERING 1-A', 'CITY': 'KETTERING CITY'},
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'KETTERING 1-B', 'CITY': 'KETTERING CITY'},
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'OAKWOOD 2-A', 'CITY': 'OAKWOOD CITY'},
        {'COUNTY_NUMBER': '57', 'PRECINCT_NAME': 'WASHINGTON TWP F', 'CITY': '',
         'TOWNSHIP': 'WASHINGTON TOWNSHIP'},
    ]
    out = jg._add_resolved_city_column(_df(rows), _LOG)

    def groups(col):
        return dict(
            out.filter(pl.col(col).str.strip_chars().fill_null('').str.len_chars() > 1)
               .group_by(col).agg(pl.len().alias('n')).iter_rows()
        )

    assert groups('CITY') == groups('_resolved_city') == {
        'KETTERING CITY': 2, 'OAKWOOD CITY': 1,
    }
