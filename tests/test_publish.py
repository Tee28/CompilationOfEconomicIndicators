"""Publish: golden narrative, license gate, schema validation of site JSON, offline e2e `update --dry-run`."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from econ import registry
from econ.common import Paths
from econ.publish import GateError, build, narrative, scan
from econ.schemas import BaselineSkill, Driver, HorizonForecast, Manifest, MarketPage, Overview, ReturnBand

REPO = Path(__file__).resolve().parents[1]
PH = narrative.phrases()
META = PH["_meta"]


def hf(key="short", p=0.6, conf="Med", band=(-0.05, 0.02, 0.1), drivers=None, n_eff=20) -> HorizonForecast:
    beats = conf != "Low"
    return HorizonForecast(
        key=key, window="1-3m" if key == "short" else "6-12m", p_up=p, return_band=ReturnBand(p10=band[0], p50=band[1], p90=band[2]),
        confidence=conf, skill=BaselineSkill(vs_random_walk=0.1 if beats else -0.1, vs_climatology=0.05, n_eff=n_eff,
                                             beats_baselines=beats),
        drivers=drivers if drivers is not None else [Driver(indicator="growth", label_vi="Tăng trưởng", contribution=0.3, direction="up")],
        narrative_vi="")


# ------------------------------------------------------------------ narrative (golden)
def _texts(node):
    return [t for v in node.values() for t in _texts(v)] if isinstance(node, dict) else [node]


def test_slots_match_meta():
    for tpl, slots in META["templates"].items():
        node = PH
        for part in tpl.split("."):
            node = node[part]
        for t in _texts(node):
            got = set(re.findall(r"\{(\w+)\}", t))
            assert got <= set(slots) | set(META["common_slots"]), (tpl, got)


def test_band_edges():
    cases = {0: "b0_15", 0.149: "b15_30", 0.15: "b15_30", 0.299: "b30_45", 0.45: "b45_55", 0.549: "b55_70",
             0.55: "b55_70", 0.70: "b70_85", 0.85: "b85_100", 1.0: "b85_100", 0.14: "b0_15"}
    for p, b in cases.items():
        assert narrative.band(p) == b, p
    assert set(cases.values()) == set(META["bands"])


@pytest.mark.parametrize("conf", ["High", "Med", "Low"])
@pytest.mark.parametrize("p", [0.05, 0.2, 0.4, 0.5, 0.6, 0.8, 0.95])
def test_short_all_bands_conf(p, conf):
    h = hf("short", p, conf)
    t = narrative.horizon_text("gold", h, "2026-11-24", PH)
    assert PH["prob_phrase"][narrative.band(p)] in t
    assert narrative.pct(p) in t
    assert PH["confidence_vi"][conf] in t
    assert PH["short"]["confidence_note"][conf] in t
    assert not narrative.banned(t, PH)
    assert "{" not in t
    # text never states another band's phrase
    for b, ph in PH["prob_phrase"].items():
        if b != narrative.band(p) and ph not in PH["prob_phrase"][narrative.band(p)]:
            assert ph not in t


def test_golden_short_text():
    t = narrative.horizon_text("gold", hf("short", 0.62, "Med"), "2026-11-24", PH)
    assert t == ("Vàng: nghiêng về tăng (62%) trong 1-3 tháng tới, độ tin cậy Trung bình (tính đến 2026-11-24). "
                 "Mô hình nhỉnh hơn mức so sánh cơ bản, nhưng biên độ còn nhỏ. "
                 "Kiểm định dựa trên 20 mốc độc lập (n_eff). Tăng trưởng đang hỗ trợ xu hướng tăng.")


def test_medium_sign_consistency_and_no_point_p():
    pos = narrative.horizon_text("oil", hf("medium", 0.6, "Low", (-0.1, 0.03, 0.2)), "2026-11-24", PH)
    neg = narrative.horizon_text("oil", hf("medium", 0.4, "Low", (-0.2, -0.03, 0.1)), "2026-11-24", PH)
    assert "+3.0%" in pos and "lệch về phía tăng" in pos and "lệch về phía giảm" not in pos
    assert "-3.0%" in neg and "lệch về phía giảm" in neg and "lệch về phía tăng" not in neg
    assert "-10.0%" in pos and "+20.0%" in pos
    assert "%)" not in pos.split("lợi suất kỳ vọng")[0]  # no P(up) in the medium headline


def test_driver_direction_from_contribution_sign():
    down = [Driver(indicator="x", label_vi="Lạm phát", contribution=-0.4, direction="down"),
            Driver(indicator="y", label_vi="Tăng trưởng", contribution=0.1, direction="up")]
    t = narrative.horizon_text("gold", hf("short", 0.3, "Low", drivers=down), "2026-11-24", PH)
    assert "Lạm phát đang gây áp lực giảm." in t and "Tăng trưởng đang hỗ trợ" not in t
    none = narrative.horizon_text("gold", hf("short", 0.5, "Low", drivers=[]), "2026-11-24", PH)
    assert PH["driver"]["none"] in none


def test_banned_words_absent_from_all_templates():
    blob = json.dumps({k: v for k, v in PH.items() if k != "_meta"}, ensure_ascii=False)
    assert not narrative.banned(blob, PH)


# ------------------------------------------------------------------ build / gate / schema
@pytest.fixture(scope="module")
def built(synth_store, tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    paths = Paths(data=synth_store.data, ledger=out / "ledger", site=out / "data")
    man = build("2026-11-20", paths)
    return paths, man


def test_published_json_validates_and_hashes(built):
    paths, man = built
    Manifest.model_validate_json((paths.site / "manifest.json").read_text(encoding="utf-8"))
    names = {f.name.split(".")[0] for f in man.files}
    assert names == {"overview", "global_macro", "us_equities", "gold", "oil"}
    import hashlib

    for f in man.files:
        raw = (paths.site / f.name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == f.hash and f.hash[:8] in f.name and len(raw) == f.bytes
        js = json.loads(raw)
        (Overview if f.name.startswith("overview") else MarketPage).model_validate(js)
        assert len(raw) <= 200 * 1024
        assert not narrative.banned(raw.decode("utf-8"), PH)
    assert scan(paths.site) == []


def test_license_gate_internal_has_no_values(built):
    paths, _ = built
    specs = registry.load()
    us = next(p for p in paths.site.glob("us_equities.*.json"))
    page = json.loads(us.read_text(encoding="utf-8"))
    sp = next(s for s in page["series"] if s["id"] == "sp500")
    assert specs["sp500"].license_class == "internal"
    assert sp["values"] == [] and sp["dates"] == []
    ov = json.loads(next(paths.site.glob("overview.*.json")).read_text(encoding="utf-8"))
    for c in ov["composites"]:
        if c["license"] == "internal":
            assert c["level"] is None


def test_scan_catches_tampered_file(built, tmp_path):
    paths, _ = built
    site = tmp_path / "s"
    shutil.copytree(paths.site, site)
    f = next(site.glob("us_equities.*.json"))
    js = json.loads(f.read_text(encoding="utf-8"))
    for s in js["series"]:
        if s["id"] == "sp500":
            s["values"], s["dates"] = [1.0], ["2026-01-01"]
    f.write_text(json.dumps(js), encoding="utf-8")
    assert any("sp500" in p for p in scan(site))
    js["series"][0]["license"] = "open"
    f.write_text(json.dumps(js), encoding="utf-8")
    assert scan(site)


def test_size_budget_fails_build(synth_store, tmp_path, monkeypatch):
    import econ.publish as pub

    monkeypatch.setattr(pub, "cfg", lambda k, d=None: 0)
    with pytest.raises(GateError):
        build("2026-11-20", Paths(data=synth_store.data, site=tmp_path / "d"), write=False)


def test_build_is_deterministic(built, synth_store, tmp_path):
    paths, man = built
    again = build("2026-11-20", Paths(data=synth_store.data, site=tmp_path / "d2"))
    assert [f.hash for f in again.files] == [f.hash for f in man.files]


# ------------------------------------------------------------------ e2e (subprocess, offline)
def test_update_dry_run_out_dir(synth_store, tmp_path):
    import os

    env = dict(os.environ, PYTHONUTF8="1", ECON_NO_VENV="1", ECON_DATA_DIR=str(synth_store.data))
    env.pop("FRED_API_KEY", None)
    r = subprocess.run([sys.executable, str(REPO / "econ.py"), "update", "--dry-run", "--asof", "2026-11-20",
                        "--out-dir", str(tmp_path)], capture_output=True, text=True, encoding="utf-8", env=env,
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(r.stdout.splitlines()) <= 40
    site = tmp_path / "web" / "public" / "data"
    assert (site / "manifest.json").exists() and len(list(site.glob("*.json"))) == 6
    assert not (tmp_path / "ledger").exists() or not any((tmp_path / "ledger").rglob("*.jsonl"))
    for step in ("fetch", "compute", "forecast", "ledger", "publish"):
        assert re.search(rf"^\s+{step}\s+(ok|degraded)", r.stdout, re.M), r.stdout
    assert subprocess.run([sys.executable, str(REPO / "econ.py"), "publish", "--scan", "--out-dir", str(tmp_path)],
                          capture_output=True, text=True, env=env, timeout=60).returncode == 0


def test_update_missing_key_degrades_not_crashes(synth_store, tmp_path, monkeypatch):
    from econ.publish.update import run

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("econ.connectors.fred.have_key", lambda: False)
    res = run("2026-11-20", Paths(data=synth_store.data, out_dir=tmp_path), dry_run=False, write_site=True,
              source="fred")
    assert res["steps"]["fetch"]["status"] == "degraded" and "skipped" in res["steps"]["fetch"]["note"]
    assert res["code"] == 0 and res["steps"]["publish"]["status"] == "ok"
    h = json.loads((tmp_path / "ledger" / "health.json").read_text(encoding="utf-8"))
    assert any(v["status"] == "degraded" and "skipped" in v["note"] for v in h["sources"].values())


def test_update_empty_store_fails_softly(tmp_path):
    from econ.publish.update import run

    res = run("2026-11-20", Paths(data=tmp_path / "empty", out_dir=tmp_path), dry_run=True)
    assert res["code"] == 1
    assert res["steps"]["publish"]["status"] in ("failed", "skipped")
