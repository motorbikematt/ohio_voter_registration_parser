"""
Pass B — manifest.json + frontend structure tests.

Validates jurisdictionScopes registry in manifest.json, the Jurisdictions
tab in index.html, and key symbols in charts.js.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

BASE      = Path(__file__).parent.parent
DOCS      = BASE / "docs"
MANIFEST  = DOCS / "manifest.json"
CHARTS_JS = DOCS / "charts.js"
INDEX_HTML = DOCS / "index.html"
DATA_DIR  = DOCS / "data"

COUNTY_SCOPED_KEYS  = {"townships", "villages", "municipal_court_districts"}
EXPECTED_TYPE_KEYS  = {
    "townships", "villages", "municipal_court_districts",
    "cities", "local_school_districts", "city_school_districts",
    "exempted_vill_school_districts", "state_senate_districts",
    "state_rep_districts", "congressional_districts",
    "county_court_districts", "court_of_appeals",
}


# ── manifest.json ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jur_scopes(manifest):
    return manifest.get("jurisdictionScopes", [])


class TestManifestJurisdictionScopes:
    def test_jurisdiction_scopes_key_exists(self, manifest):
        assert "jurisdictionScopes" in manifest, "manifest.json missing 'jurisdictionScopes'"

    def test_all_12_types_present(self, jur_scopes):
        keys = {s["key"] for s in jur_scopes}
        missing = EXPECTED_TYPE_KEYS - keys
        assert not missing, f"jurisdictionScopes missing types: {missing}"

    def test_each_scope_has_required_fields(self, jur_scopes):
        required = {"key", "display", "displayPlural", "dirName", "countyScoped"}
        for sc in jur_scopes:
            missing = required - set(sc.keys())
            assert not missing, f"scope {sc.get('key')} missing fields {missing}"

    def test_county_scoped_flags_correct(self, jur_scopes):
        for sc in jur_scopes:
            expected = sc["key"] in COUNTY_SCOPED_KEYS
            assert sc["countyScoped"] == expected, \
                f"{sc['key']}: countyScoped should be {expected}, got {sc['countyScoped']}"

    def test_dir_names_match_actual_directories(self, jur_scopes):
        for sc in jur_scopes:
            d = DATA_DIR / sc["dirName"]
            assert d.is_dir(), f"dirName {sc['dirName']!r} for {sc['key']} not found in docs/data/"

    def test_index_json_exists_for_each_scope(self, jur_scopes):
        for sc in jur_scopes:
            idx = DATA_DIR / sc["dirName"] / "index.json"
            assert idx.exists(), f"Missing index.json for {sc['key']} ({sc['dirName']})"


# ── index.html ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def html():
    return INDEX_HTML.read_text(encoding="utf-8")


class TestIndexHtml:
    def test_jurisdictions_scope_tab_present(self, html):
        assert 'data-scope="jurisdiction"' in html

    def test_jurisdiction_controls_div_present(self, html):
        assert 'id="jurisdiction-controls"' in html

    def test_jurisdiction_charts_container_present(self, html):
        assert 'id="jurisdiction-charts-container"' in html

    def test_jur_type_select_present(self, html):
        assert 'id="jur-type-select"' in html

    def test_jur_county_select_present(self, html):
        assert 'id="jur-county-select"' in html

    def test_jur_name_select_present(self, html):
        assert 'id="jur-name-select"' in html

    def test_init_config_has_jur_ids(self, html):
        assert "jurControlsId" in html
        assert "jurTypeSelectId" in html
        assert "jurChartsContainerId" in html


# ── charts.js ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def charts_src():
    return CHARTS_JS.read_text(encoding="utf-8")


REQUIRED_SYMBOLS = [
    "activeJurType", "activeJurCounty", "activeJurName", "jurIndexCache",
    "_setupJurisdictionControls", "_renderJurisdictionCharts",
    "_clearJurisdictionCharts", "_loadJurTypeIndex",
    "_populateJurNameSelect", "_onJurTypeChange",
    "_resetJurisdictionSelects",
]


class TestChartsJs:
    def test_js_syntax_valid(self):
        node = "node"
        result = subprocess.run(
            [node, "--check", str(CHARTS_JS)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"node --check failed:\n{result.stderr}"

    @pytest.mark.parametrize("symbol", REQUIRED_SYMBOLS)
    def test_required_symbol_present(self, charts_src, symbol):
        assert symbol in charts_src, f"charts.js missing symbol: {symbol}"

    def test_jurisdiction_scope_in_apply_url_state(self, charts_src):
        assert "geo === 'jurisdiction'" in charts_src

    def test_jurisdiction_hides_manifest_sections(self, charts_src):
        assert "activeScope === 'jurisdiction') return false" in charts_src

    def test_jur_index_cache_used_in_load_function(self, charts_src):
        assert "jurIndexCache[typeKey]" in charts_src

    def test_atomic_tmp_suffix_in_write_cache(self):
        src = (BASE / "voter_data_cleaner_v2.py").read_text(encoding="utf-8")
        assert ".parquet.tmp" in src
        assert "tmp.replace(ENRICHED_CACHE)" in src

    def test_classifier_mtime_in_cache_freshness(self):
        for fname in ["voter_data_cleaner_v2.py", "jurisdictional_groupings.py"]:
            src = (BASE / fname).read_text(encoding="utf-8")
            assert "classifier_mt" in src, f"{fname}: classifier_mt not found in _cache_is_fresh"
            assert "max(latest_raw, classifier_mt)" in src, \
                f"{fname}: freshness check must use max(latest_raw, classifier_mt)"
