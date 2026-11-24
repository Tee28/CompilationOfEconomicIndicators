"""Contract tests: fixtures validate, license gate holds, CLI stubs fail cleanly."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from econ import schemas as S

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "site"
MARKETS = ["global_macro", "us_equities", "gold", "oil"]


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_fixtures_validate():
    S.Overview.model_validate(load("overview"))
    for m in MARKETS:
        assert S.MarketPage.model_validate(load(m)).market == m
    man = S.Manifest.model_validate(load("manifest"))
    assert man.schema_version == S.SCHEMA_VERSION and len(man.files) == 5


def test_manifest_hashes_match_fixtures():
    man = S.Manifest.model_validate(load("manifest"))
    for f in man.files:
        base = f.name.split(".")[0]
        data = (FIX / f"{base}.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == f.hash and len(data) == f.bytes
        assert f.hash[:8] in f.name


def test_internal_series_values_rejected():
    with pytest.raises(ValidationError):
        S.SiteSeries(id="x", name_vi="x", license="internal", dates=["2026-01-01"], values=[1.0])
    assert S.SiteSeries(id="x", name_vi="x", license="internal").values == []


def test_internal_composite_level_rejected():
    with pytest.raises(ValidationError):
        S.CompositeSummary(id="c", name_vi="c", license="internal", level=1.0, percentile=50, label="x",
                           asof="2026-01-01")


def test_low_confidence_required_without_skill():
    d = load("gold")
    d["horizons"][0]["confidence"] = "High"  # short horizon fixture does not beat baselines
    with pytest.raises(ValidationError):
        S.MarketPage.model_validate(d)


def test_band_order_and_extra_fields():
    with pytest.raises(ValidationError):
        S.ReturnBand(p10=0.1, p50=0.0, p90=0.2)
    d = load("oil")
    d["surprise"] = 1
    with pytest.raises(ValidationError):
        S.MarketPage.model_validate(d)


def test_forecast_record_outcome_null_and_series_alignment():
    r = S.ForecastRecord(id="gold|3m|2026-11-21|m1", origin="2026-11-21", horizon="3m", market="gold",
                         model_id="m1", p_up=0.55, quantiles=S.ReturnBand(p10=-0.04, p50=0.01, p90=0.06),
                         baseline_rw_p_up=0.5, baseline_clim_p_up=0.56, features_hash="ab",
                         data_asof={"fred": "2026-11-20"}, created_at="2026-11-22T00:00:00Z")
    assert r.scored_at is None and r.brier is None
    with pytest.raises(ValidationError):
        S.IndicatorSeries(id="a", source="fred", license="internal", asof="2026-01-01",
                          dates=["2026-01-01"], values=[])


def test_json_schema_export():
    js = S.json_schema()
    assert {"manifest", "overview", "market", "health", "forecast_record"} <= set(js)
    json.dumps(js)


@pytest.mark.parametrize("cmd", [["ind", "list"], ["fetch"], ["compute"], ["forecast"], ["ledger", "verify"],
                                 ["publish"], ["update", "--dry-run"]])
def test_live_cli_missing_module_is_clean_error(cmd):
    p = subprocess.run([sys.executable, str(REPO / "econ.py"), *cmd], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert "Traceback" not in p.stderr
    if "not implemented yet" in p.stdout:  # until other agents land their modules
        assert p.returncode == 1 and len(p.stdout.strip().splitlines()) == 1


def test_paths_out_dir(tmp_path):
    from econ.common import Paths

    p = Paths(out_dir=tmp_path)
    assert p.ledger == tmp_path / "ledger" and p.site == tmp_path / "web" / "public" / "data"
