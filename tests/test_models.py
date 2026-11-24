"""Models + backtest: no look-ahead (truncation, vintage labels, real-time consistency), skill/tests, contract."""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import pytest

from econ import models, registry, store
from econ.backtest import stats
from econ.backtest.walkforward import walk_forward
from econ.common import Paths
from econ.models import data, spec
from econ.models.fit import logit_ridge, ridge
from econ.schemas import BaselineSkill, HorizonForecast, ReturnBand
from tests.conftest import run_cli, synth_frame

ORIGIN = "2020-06-30"
LATER = "2026-11-24"
CREATED = "2026-11-24T00:00:00Z"
D = spec.Defaults()


# ------------------------------------------------------------------ stats
def test_scores_and_tests():
    y = np.array([1, 0, 1, 1])
    assert np.allclose(stats.brier([0.5] * 4, y), 0.25)
    assert stats.skill([0.1] * 4, [0.2] * 4) == pytest.approx(0.5)
    assert stats.pinball([1.0], [0.0], 0.9)[0] == pytest.approx(0.9)
    rng = np.random.default_rng(1)
    better = -0.05 + 0.01 * rng.standard_normal(60)
    assert stats.dm_hln(better, 1)[1] < 0.01 and stats.dm_hln(-better, 1)[1] > 0.99
    assert np.isnan(stats.dm_hln([0.1, 0.2], 1)[1])
    p = rng.uniform(0.05, 0.95, 4000)
    yy = (rng.uniform(size=4000) < p).astype(float)
    cal = stats.calibration(p, yy)
    assert 0.85 < cal["slope"] < 1.15 and cal["ece"] < 0.05
    assert stats.clark_west(yy, p, np.full_like(p, yy.mean()))[1] < 0.01


def test_confidence_rule():
    r = spec.ConfidenceRule()
    good = dict(bss_rw=0.1, bss_clim=0.05, n_eff=40, dm_p_rw=0.01, cw_p_clim=0.01, calib_slope=1.0,
                pinball_skill_clim=0.02)
    assert stats.confidence(good, r) == ("High", True)
    assert stats.confidence({**good, "n_eff": 20}, r) == ("Med", True)
    assert stats.confidence({**good, "n_eff": 10}, r) == ("Low", True)
    assert stats.confidence({**good, "bss_clim": -0.01}, r) == ("Low", False)
    assert stats.confidence({**good, "bss_rw": -0.01}, r) == ("Low", False)  # must beat BOTH baselines
    assert stats.confidence({**good, "bss_rw": float("nan")}, r) == ("Low", False)
    assert stats.confidence({**good, "pinball_skill_clim": -0.1}, r, medium=True) == ("Low", False)
    assert stats.confidence({"n_eff": 0}, r) == ("Low", False)
    with pytest.raises(ValueError):  # schema enforces the charter on whatever the model produces
        HorizonForecast(key="short", window="1-3m", p_up=0.6, return_band=ReturnBand(p10=-1, p50=0, p90=1),
                        confidence="Med", narrative_vi="",
                        skill=BaselineSkill(vs_random_walk=-0.1, vs_climatology=0.1, n_eff=30, beats_baselines=False))


def test_no_point_p_up_beyond_medium_window():
    """Charter: long horizon = ranges only. The contract admits only 1-3m / 6-12m windows, so a P(up) can never
    be published for a 5Y horizon; medium's headline is the return band (p_up kept as a secondary field)."""
    kw = dict(p_up=0.6, return_band=ReturnBand(p10=-1, p50=0, p90=1), confidence="Low", narrative_vi="",
              skill=BaselineSkill(vs_random_walk=0.0, vs_climatology=0.0, n_eff=0, beats_baselines=False))
    for key, window in (("medium", "5y"), ("long", "5y"), ("short", "6-12m")):
        with pytest.raises(ValueError):
            HorizonForecast(key=key, window=window, **kw)
    assert HorizonForecast(key="medium", window="6-12m", **kw).return_band.p90 == 1


def test_fits_shrink_and_recover():
    rng = np.random.default_rng(3)
    X = rng.standard_normal((2000, 2))
    y = (rng.uniform(size=2000) < 1 / (1 + np.exp(-(0.3 + 1.0 * X[:, 0])))).astype(float)
    a, b = logit_ridge(X, y, 1.0)
    assert abs(b[0] - 1.0) < 0.15 and abs(b[1]) < 0.1 and abs(a - 0.3) < 0.15
    assert abs(logit_ridge(X, y, 1e6)[1]).max() < 0.01  # heavy penalty -> climatology
    yr = 0.02 * X[:, 0] + 0.01 * rng.standard_normal(2000)
    assert abs(ridge(X, yr, 1.0)[1][0] - 0.02) < 0.002


# ------------------------------------------------------------------ engine on a planted signal
def _planted(signal: float, seed: int = 5, n: int = 300):
    """Monthly target (obs at period start, known 5 days later); next-month return = signal * x + noise."""
    rng = np.random.default_rng(seed)
    ends = pd.date_range("2000-01-31", periods=n, freq="ME")
    x = rng.standard_normal(n)
    starts = ends - pd.offsets.MonthBegin(1)
    lv = np.concatenate([[0.0], np.cumsum(signal * x + 0.02 * rng.standard_normal(n))])[:n]
    rows = pd.DataFrame({"date": starts, "value": 100 * np.exp(lv), "known_at": starts + pd.Timedelta(days=5)})
    X = pd.DataFrame({"f1": x, "f2": rng.standard_normal(n)}, index=ends)
    return X, rows


def test_walk_forward_detects_planted_signal():
    X, rows = _planted(0.03)
    bt = walk_forward(X, data.Target(rows, "M", 1), X.index[-1], 1, 1.0, D)
    m = bt["metrics"]
    assert m["n_eff"] == len(bt["oos"]) >= 100 and not bt["short_sample"]
    assert m["bss_clim"] > 0.1 and m["bss_rw"] > 0.1 and m["cw_p_clim"] < 0.01 and m["dm_p_rw"] < 0.01
    assert stats.confidence(m, D.confidence)[1] and bt["live"]["contrib"][0] != 0


def test_walk_forward_noise_does_not_beat_climatology_significantly():
    X, rows = _planted(0.0)
    m = walk_forward(X, data.Target(rows, "M", 1), X.index[-1], 1, 10.0, D)["metrics"]
    assert m["cw_p_clim"] > 0.05 and stats.confidence(m, D.confidence)[0] != "High"


def test_non_overlapping_origins_and_n_eff():
    X, rows = _planted(0.03)
    bt = walk_forward(X, data.Target(rows, "M", 3), X.index[-1], 3, 1.0, D)
    assert bt["metrics"]["n_eff"] == sum(t.month % 3 == 0 for t in bt["oos"].index) < len(bt["oos"])


def test_engine_training_never_sees_unknown_labels():
    """Corrupt every target value known after T0: predictions at origins <= T0 must not move."""
    X, rows = _planted(0.03)
    t0 = pd.Timestamp("2018-06-30")
    bad = rows.copy()
    late = bad["known_at"] > t0
    bad.loc[late, "value"] *= np.exp(np.linspace(0, 5, late.sum()))
    a = walk_forward(X, data.Target(rows, "M", 1), X.index[-1], 1, 1.0, D)["oos"]
    b = walk_forward(X, data.Target(bad, "M", 1), X.index[-1], 1, 1.0, D)["oos"]
    cols = ["p", "q10", "q50", "q90", "p_clim", "n_train"]
    early = a.index[a.index < t0]
    assert len(early) > 30
    pd.testing.assert_frame_equal(a.loc[early, cols], b.loc[early, cols])
    assert not np.allclose(a.loc[a.index > t0, "p"], b.loc[b.index > t0, "p"])


def test_target_labels_use_vintage_known_at_t():
    rows = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-02-01", "2020-03-01"]),
                         "value": [100.0, 110.0, 120.0, 130.0],
                         "known_at": pd.to_datetime(["2020-01-06", "2020-02-06", "2020-05-01", "2020-03-06"])})
    t = data.Target(rows, "M", 1)
    t.prepare(pd.date_range("2020-01-31", "2020-06-30", freq="ME"))
    early = t.labels_at("2020-03-31")
    assert early.loc["2020-01-31", "y"] == pytest.approx(np.log(1.1))  # revision unknown yet
    assert t.labels_at("2020-06-30").loc["2020-01-31", "y"] == pytest.approx(np.log(1.2))
    assert "2020-03-31" not in early.index.strftime("%Y-%m-%d")  # its target obs is not known yet
    assert t.realized(pd.Timestamp("2020-01-01"), "2020-02-05") == (None, None)


# ------------------------------------------------------------------ full pipeline on the synthetic store
@pytest.fixture(scope="module")
def ctx_origin(synth_store):
    return models.context(ORIGIN, synth_store)


def test_forecast_contract_and_charter(ctx_origin, synth_store):
    runs = {m: models.run_market(m, ORIGIN, synth_store, ctx_origin, CREATED) for m in ctx_origin.mcfg.targets}
    assert set(runs) == {"global_macro", "us_equities", "gold", "oil"}
    for m, r in runs.items():
        assert [h.key for h in r.horizons] == ["short", "medium"] and len(r.records) == 2
        for hf, rec in zip(r.horizons, r.records):
            assert rec.id == f"{m}|{rec.horizon}|{ORIGIN}|{rec.model_id}" and rec.model_id.endswith(".v1")
            assert rec.horizon in ("3m", "12m") and rec.baseline_rw_p_up == 0.5
            assert any(k.startswith("anchor:") for k in rec.data_asof)
            assert all(v <= ORIGIN for v in rec.data_asof.values())
            if not hf.skill.beats_baselines:
                assert hf.confidence == "Low"
            assert [abs(d.contribution) for d in hf.drivers] == sorted((abs(d.contribution) for d in hf.drivers),
                                                                       reverse=True)
            rep = r.reports[hf.key]
            assert rep["oos"]["n_eff"] == hf.skill.n_eff and rep["holdout_start"] < ORIGIN


def test_truncation_rows_after_origin_removed(tmp_path, ctx_origin, synth_store):
    specs = registry.load()
    trunc = Paths(data=tmp_path)
    df = synth_frame(specs, specs)
    store.append(df[pd.to_datetime(df["date"]) <= ORIGIN], trunc)
    for m in ("us_equities", "gold"):
        a = models.run_market(m, ORIGIN, synth_store, ctx_origin, CREATED)
        b = models.run_market(m, ORIGIN, trunc, created_at=CREATED)
        assert [x.model_dump() for x in a.records] == [x.model_dump() for x in b.records]
        assert [x.model_dump() for x in a.horizons] == [x.model_dump() for x in b.horizons]


def test_live_forecast_equals_later_backtest_prediction(ctx_origin, synth_store):
    """Real-time consistency: the forecast printed at ORIGIN is exactly the OOS prediction a later run
    reconstructs for that origin (same features, same labels known at ORIGIN)."""
    rec = models.run_market("gold", ORIGIN, synth_store, ctx_origin, CREATED).records[0]
    late = models.context(LATER, synth_store)
    mc = late.mcfg
    fam = mc.models["composite_ridge"]
    tgt = data.target_for(late.specs["gold_pink"], 3, LATER, synth_store)
    bt = walk_forward(late.X[fam.features], tgt, pd.Timestamp(LATER), 3, mc.horizons["short"].l2, mc.defaults)
    assert round(bt["oos"].loc[ORIGIN, "p"], 6) == rec.p_up
    assert round(bt["oos"].loc[ORIGIN, "q50"], 6) == rec.quantiles.p50


def test_cmd_forecast_dry_run_and_out_dir(tmp_path, synth_store):
    out = tmp_path / "out"
    a = argparse.Namespace(asof=ORIGIN, data_dir=str(synth_store.data), ledger_dir=None, out_dir=str(out),
                           dry_run=True, market=["gold"])
    r = models.cmd_forecast(a)
    assert not out.exists() and len(r.text.splitlines()) <= 40 and "gold.short.composite_ridge.v1" in r.text
    a.dry_run = False
    models.cmd_forecast(a)
    assert (out / "derived" / "forecasts" / ORIGIN / "gold.json").exists()


def test_models_config_validation(tmp_path):
    import shutil

    from econ.common import CONFIG, EconError

    shutil.copytree(CONFIG, tmp_path / "config")
    p = tmp_path / "config" / "models.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("indicator: gold_pink", "indicator: nope"), encoding="utf-8")
    with pytest.raises(EconError, match="unknown indicator 'nope'"):
        spec.load(tmp_path / "config", registry.load())


def test_cli_help(root):
    for args in (("forecast", "--help"), ("ledger", "--help"), ("ledger", "score", "--help")):
        r = run_cli(root, *args)
        assert r.returncode == 0 and "usage" in r.stdout
