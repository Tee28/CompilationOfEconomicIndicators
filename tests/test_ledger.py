"""Ledger: append idempotent, score appends outcome lines, verify catches any rewrite, health.json."""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
import pytest

from econ import ledger, models, registry, store
from econ.common import Paths
from econ.schemas import ForecastRecord, Health, ReturnBand
from tests.conftest import run_cli

ORIGIN = "2020-06-30"
LATER = "2026-11-24"
CREATED = "2026-11-24T00:00:00Z"


def _rec(i: int, origin="2026-10-31", **kw) -> ForecastRecord:
    base = dict(id=f"gold|3m|{origin}|gold.short.composite_ridge.v1#{i}", origin=origin, horizon="3m",
                market="gold", model_id="gold.short.composite_ridge.v1", p_up=0.55,
                quantiles=ReturnBand(p10=-0.05, p50=0.01, p90=0.06), baseline_rw_p_up=0.5, baseline_clim_p_up=0.52,
                features_hash="ab" * 32, data_asof={"gold_pink": "2026-09-01"}, created_at=CREATED)
    return ForecastRecord(**{**base, **kw})


def _paths(tmp_path) -> Paths:
    return Paths(data=tmp_path / "data", out_dir=tmp_path / "out")


def test_append_idempotent_and_layout(tmp_path):
    p = _paths(tmp_path)
    assert p.ledger == tmp_path / "out" / "ledger"
    added, skipped = ledger.append([_rec(1), _rec(2), _rec(3, origin="2026-11-30")], p)
    assert len(added) == 3 and not skipped
    assert ledger.append([_rec(1)], p) == ([], [_rec(1).id])
    f = p.ledger / "forecasts" / "2026-10.jsonl"
    assert len(f.read_text(encoding="utf-8").splitlines()) == 2
    assert (p.ledger / "forecasts" / "2026-11.jsonl").exists() and (p.ledger / "chain.json").exists()
    assert ledger.verify(p) == []
    # dry run writes nothing
    q = Paths(data=tmp_path / "data", out_dir=tmp_path / "dry")
    assert ledger.append([_rec(9)], q, dry_run=True)[0] == [_rec(9).id] and not q.ledger.exists()


@pytest.mark.parametrize("tamper,msg", [
    (lambda f: f.write_text(f.read_text(encoding="utf-8").replace("0.55", "0.65", 1), encoding="utf-8"), "rewritten"),
    (lambda f: f.write_text("\n".join(f.read_text(encoding="utf-8").splitlines()[:1]) + "\n", encoding="utf-8"),
     "truncated"),
    (lambda f: f.write_text(f.read_text(encoding="utf-8") + _rec(7).model_dump_json() + "\n", encoding="utf-8"),
     "unchained"),
    (lambda f: f.unlink(), "deleted"),
])
def test_verify_detects_edits(tmp_path, tamper, msg):
    p = _paths(tmp_path)
    ledger.append([_rec(1), _rec(2)], p)
    tamper(p.ledger / "forecasts" / "2026-10.jsonl")
    issues = ledger.verify(p)
    assert issues and any(msg in i for i in issues)


def test_verify_rejects_score_line_changing_forecast(tmp_path):
    p = _paths(tmp_path)
    ledger.append([_rec(1)], p)
    bad = _rec(1, p_up=0.9, scored_at=CREATED, realized_return=0.01, realized_up=True, brier=0.01,
               brier_rw=0.25, brier_clim=0.2)
    from econ.ledger.book import _write_lines

    _write_lines({"forecasts/2026-10.jsonl": [bad.model_dump_json()]}, p)  # chained, but semantically wrong
    assert any("changes forecast fields" in i for i in ledger.verify(p))


def test_score_appends_outcome_and_is_idempotent(tmp_path, synth_store):
    p = Paths(data=synth_store.data, out_dir=tmp_path / "out")
    recs = [r for run in models.forecast_all(ORIGIN, p, ["gold", "us_equities"], CREATED) for r in run.records]
    ledger.append(recs, p)
    assert ledger.score("2020-07-15", p) == []  # nothing matured yet
    scored = ledger.score(LATER, p)
    assert {s.id for s in scored} == {r.id for r in recs}
    assert ledger.score(LATER, p) == [] and ledger.verify(p) == []
    last = ledger.read_all(p)
    g = next(s for s in scored if s.market == "gold" and s.horizon == "3m")
    assert last[g.id].scored_at is not None
    # realized return = log(target obs 3 months after the anchor / anchor), values from the store
    sp = registry.load()["gold_pink"]
    f = store.read_frame(sp.source, sp.series, LATER, sp.lag_days, p).set_index("date")["value"]
    a = pd.Timestamp(g.data_asof["anchor:gold_pink"])
    assert g.realized_return == pytest.approx(np.log(f[a + pd.DateOffset(months=3)] / f[a]), abs=1e-6)
    assert g.brier == pytest.approx((g.p_up - float(g.realized_up)) ** 2, abs=1e-6)
    lines = (p.ledger / "forecasts" / "2020-06.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 * len(recs)


def test_health_json(tmp_path, synth_store):
    p = Paths(data=synth_store.data, out_dir=tmp_path / "out")
    a = argparse.Namespace(asof="2026-11-24", data_dir=str(synth_store.data), ledger_dir=None,
                           out_dir=str(tmp_path / "out"), site_dir=None, dry_run=False)
    r = ledger.cmd_health(a)
    h = Health(**json.loads((p.ledger / "health.json").read_text(encoding="utf-8")))
    assert set(h.sources) == set(registry.load()) and len(r.text.splitlines()) <= 40
    assert h.sources["sp500"].status in ("ok", "degraded") and h.sources["sp500"].last_obs <= "2026-11-24"
    stale = ledger.health("2027-12-31", p)
    assert stale.sources["gold_pink"].status == "late"
    empty = Paths(data=tmp_path / "empty", out_dir=tmp_path / "out")
    h1 = ledger.health("2026-11-24", empty)
    assert all(s.status == "failed" and s.fails == 1 for s in h1.sources.values())


def test_cli_verify_exit_codes(root, tmp_path):
    p = Paths(data=tmp_path / "d", ledger=tmp_path / "led")
    ledger.append([_rec(1)], p)
    r = run_cli(root, "ledger", "verify", "--ledger-dir", str(p.ledger))
    assert r.returncode == 0 and "0 issue" in r.stdout
    f = p.ledger / "forecasts" / "2026-10.jsonl"
    f.write_text(f.read_text(encoding="utf-8").replace("0.55", "0.56"), encoding="utf-8")
    r = run_cli(root, "ledger", "verify", "--ledger-dir", str(p.ledger))
    assert r.returncode == 2 and "rewritten" in r.stdout
