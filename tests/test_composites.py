"""Composites engine: as-of safety (truncation + vintage tests), renormalisation, labels, license rule, CLI."""
from __future__ import annotations

import argparse
import shutil

import numpy as np
import pandas as pd
import pytest

from econ import composites, registry, store
from econ.common import EconError, Paths
from econ.composites import engine
from tests.conftest import REPO, run_cli

ORIGIN = "2020-06-30"
LATER = "2026-11-24"


def _synth(specs, ids, start="2005-01-01", end="2026-11-20", seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i, iid in enumerate(sorted(ids)):
        sp = specs[iid]
        freq = {"D": "B", "W": "W-SAT", "M": "MS", "Q": "QS"}[sp.freq]
        d = pd.date_range(start, end, freq=freq)
        v = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, len(d)))) + i  # positive levels
        rows.append(pd.DataFrame({"source": sp.source, "series_id": sp.series, "date": d, "value": v,
                                  "fetched_at": "2026-11-21T00:00:00Z"}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def specs():
    return registry.load()


@pytest.fixture(scope="module")
def cfg(specs):
    return composites.load(None, specs)


@pytest.fixture(scope="module")
def members(cfg):
    return sorted({m for c in cfg.composites.values() for m in c.members})


@pytest.fixture(scope="module")
def full(tmp_path_factory, specs, members):
    p = Paths(data=tmp_path_factory.mktemp("store_full"))
    store.append(_synth(specs, members), p)
    return p


def _by_id(res):
    return {c.id: c for c in res}


# ------------------------------------------------------------------ config
def test_config_loads_and_license_rule(cfg, specs):
    assert set(cfg.composites) == {"growth", "inflation_policy", "financial_conditions"}
    lic = {cid: composites.derived_license(c, specs) for cid, c in cfg.composites.items()}
    assert lic == {"growth": "attributed", "inflation_policy": "attributed", "financial_conditions": "internal"}
    for c in cfg.composites.values():
        assert len(c.labels_vi) == len(cfg.defaults.label_bands) + 1


@pytest.mark.parametrize("old,new,msg", [
    ("license: internal ", "license: attributed ", "members imply 'internal'"),
    ("nfci:      {sign: 1,", "nope:      {sign: 1,", "unknown member"),
    ("weight: 0.30, agg: last, transform: level}     # Chicago", "weight: 0, agg: last, transform: level}  #",
     "invalid"),
    ("transform: chg_3m}", "transform: chg_0m}", "invalid"),
])
def test_config_rejects_bad(tmp_path, old, new, msg):
    shutil.copytree(REPO / "config", tmp_path / "config")
    f = tmp_path / "config" / "composites.yaml"
    text = f.read_text(encoding="utf-8")
    assert old in text
    f.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(EconError) as e:
        composites.load(tmp_path / "config")
    assert msg in str(e.value)


# ------------------------------------------------------------------ engine units
def _frame(rows):
    return pd.DataFrame(rows, columns=["date", "value", "known_at"])


def test_publication_lag_respected():
    g = engine.grid("2026-09-01", "2026-12-31")
    f = _frame([("2026-09-01", 1.0, "2026-10-16"), ("2026-10-01", 2.0, "2026-11-15")])
    s = engine.sample(f, g, "last", max_ffill=2)
    assert np.isnan(s["2026-09-30"]) and s["2026-10-31"] == 1.0  # Oct obs not known at Oct-31
    assert s["2026-11-30"] == 2.0 and s["2026-12-31"] == 2.0     # carried 1 period (<= max_ffill)


def test_late_revision_never_overrides_newer_obs_and_staleness():
    g = engine.grid("2026-09-01", "2027-03-31")
    f = _frame([("2026-09-01", 1.0, "2026-10-15"), ("2026-10-01", 2.0, "2026-11-15"),
                ("2026-09-01", 1.5, "2026-11-20")])
    s = engine.sample(f, g, "last", max_ffill=2)
    assert s["2026-11-30"] == 2.0
    assert s["2027-01-31"] == 2.0 and np.isnan(s["2027-02-28"])  # stale beyond 2 periods -> withheld


def test_grid_ends_at_asof_and_mean_agg():
    g = engine.grid("2026-10-01", "2026-11-24")
    assert [d.date().isoformat() for d in g] == ["2026-10-31", "2026-11-24"]
    f = _frame([("2026-10-29", 1.0, "2026-10-30"), ("2026-10-30", 3.0, "2026-10-31"),
                ("2026-10-31", 5.0, "2026-11-01"), ("2026-11-20", 7.0, "2026-11-21")])
    s = engine.sample(f, g, "mean", max_ffill=1, lag_days=1)
    assert s.iloc[0] == 2.0 and s.iloc[1] == 6.0


def test_combine_renormalises_and_coverage():
    z = pd.DataFrame({"a": [1.0, 1.0, np.nan], "b": [-1.0, np.nan, np.nan], "c": [0.0, 0.0, 3.0]})
    level, cov, used = engine.combine(z, {"a": 0.5, "b": 0.3, "c": 0.2}, 0.6)
    assert level[0] == pytest.approx(0.5 - 0.3)
    assert cov[1] == pytest.approx(0.7) and level[1] == pytest.approx(0.5 / 0.7)
    assert np.isnan(level[2]) and cov[2] == pytest.approx(0.2)  # below min_coverage -> withheld
    assert used.iloc[1].sum() == pytest.approx(1.0)


def test_labels():
    labs = ["L0", "L1", "L2", "L3", "L4"]
    assert engine.label(0.0, [20, 40, 60, 80], labs) == "L0"
    assert engine.label(20.0, [20, 40, 60, 80], labs) == "L1"  # lower bound inclusive
    assert engine.label(99.9, [20, 40, 60, 80], labs) == "L4"
    assert engine.label(None, [20, 40, 60, 80], labs) is None


# ------------------------------------------------------------------ as-of safety on a synthetic store
def test_no_lookahead_later_asof_keeps_history(full):
    early = _by_id(composites.compute(ORIGIN, full))
    late = _by_id(composites.compute(LATER, full))
    for cid, e in early.items():
        lv = late[cid]
        n = len(e.dates)
        assert lv.dates[:n] == e.dates and e.dates[-1] == ORIGIN
        assert lv.levels[:n] == e.levels and lv.percentiles[:n] == e.percentiles
        assert sum(v is not None for v in e.percentiles) > 24  # the test exercised real values


def test_truncation_rows_after_origin_removed(tmp_path, specs, members, full):
    trunc = Paths(data=tmp_path)
    df = _synth(specs, members)
    store.append(df[pd.to_datetime(df["date"]) <= ORIGIN], trunc)
    a = [c.model_dump() for c in composites.compute(ORIGIN, full)]
    b = [c.model_dump() for c in composites.compute(ORIGIN, trunc)]
    assert a == b


def _revised_store(path, specs, members, obs, fetched):
    p = Paths(data=path)
    df = _synth(specs, members)
    store.append(df, p)
    rev = df[(df["series_id"] == specs["cpi"].series) & (pd.to_datetime(df["date"]) == obs)].copy()
    rev["value"] *= 1.5
    rev["fetched_at"] = fetched
    assert store.append(rev, p, backfill=False) == 1
    return p


def test_old_revision_never_rewrites_real_time_history(tmp_path, specs, members, full):
    p = _revised_store(tmp_path, specs, members, "2019-06-01", "2023-01-10T00:00:00Z")
    for asof in (ORIGIN, "2023-06-30"):
        assert [c.model_dump() for c in composites.compute(asof, p)] == \
               [c.model_dump() for c in composites.compute(asof, full)]


def test_fresh_revision_visible_only_from_fetch_date(tmp_path, specs, members, full):
    p = _revised_store(tmp_path, specs, members, "2019-06-01", "2019-07-20T00:00:00Z")  # before Jul CPI is out
    a = _by_id(composites.compute(ORIGIN, p))["inflation_policy"]
    b = _by_id(composites.compute(ORIGIN, full))["inflation_policy"]
    cut = a.dates.index("2019-06-30") + 1
    assert a.levels[:cut] == b.levels[:cut] and a.levels[cut] != b.levels[cut]  # 2019-07-31 uses revision


def test_vintage_rows_matches_store_read_frame(tmp_path, specs, members):
    p = _revised_store(tmp_path, specs, members, "2019-06-01", "2023-01-10T00:00:00Z")
    sp = specs["cpi"]
    mine = composites.vintage_rows(sp.source, sp.series, LATER, sp.lag_days, p)
    assert len(mine) == mine["date"].nunique() + 1  # both vintages of 2019-06 kept
    ref = store.read_frame(sp.source, sp.series, LATER, sp.lag_days, p)
    last = mine.drop_duplicates("date", keep="last").reset_index(drop=True)
    pd.testing.assert_frame_equal(last, ref, check_dtype=False)


def test_missing_members_renormalise(tmp_path, specs):
    p = Paths(data=tmp_path)
    store.append(_synth(specs, ["payems", "indpro", "unrate"]), p)  # 0.65 of growth weight
    g = _by_id(composites.compute(LATER, p))["growth"]
    assert g.coverage == pytest.approx(0.65)
    assert set(g.weights) == {"payems", "indpro", "unrate"} and sum(g.weights.values()) == pytest.approx(1.0)
    assert g.levels[-1] is not None
    p2 = Paths(data=tmp_path / "two")
    store.append(_synth(specs, ["payems", "indpro"]), p2)  # 0.45 < min_coverage
    g2 = _by_id(composites.compute(LATER, p2))["growth"]
    assert all(v is None for v in g2.levels)
    empty = _by_id(composites.compute(LATER, Paths(data=tmp_path / "none")))["growth"]
    assert empty.dates == [] and empty.coverage == 0.0


def test_contributions_sum_to_level_and_deterministic(full):
    c = composites.contributions("growth", LATER, full)
    g = _by_id(composites.compute(LATER, full))["growth"]
    lv = pd.Series(g.levels, index=pd.to_datetime(g.dates), dtype=float)
    ok = lv.notna()
    assert np.allclose(c.sum(axis=1)[ok], lv[ok], atol=1e-5)
    assert [x.model_dump() for x in composites.compute(LATER, full)] == \
           [x.model_dump() for x in composites.compute(LATER, full)]


def test_summary_hides_internal_level(full, cfg):
    res = _by_id(composites.compute(LATER, full))
    fc = composites.summary(res["financial_conditions"], cfg.composites["financial_conditions"], cfg)
    gr = composites.summary(res["growth"], cfg.composites["growth"], cfg)
    assert fc.license == "internal" and fc.level is None and fc.label in cfg.composites[
        "financial_conditions"].labels_vi
    assert gr.level is not None and 0 <= gr.percentile <= 100


# ------------------------------------------------------------------ CLI
def test_cmd_compute_writes_and_dry_run(tmp_path, full):
    out = tmp_path / "out"
    a = argparse.Namespace(asof=LATER, data_dir=str(full.data), ledger_dir=None, out_dir=str(out), dry_run=True)
    r = composites.cmd_compute(a)
    assert not out.exists() and len(r.text.splitlines()) <= 40
    a.dry_run = False
    r = composites.cmd_compute(a)
    files = sorted((out / "derived" / "composites" / LATER).glob("*.json"))
    assert [f.stem for f in files] == ["financial_conditions", "growth", "inflation_policy"]
    fc_line = [ln for ln in r.text.splitlines() if "financial_conditions" in ln][0]
    assert "level hidden" in fc_line and len(r.text.splitlines()) <= 40


def test_compute_help(root):
    r = run_cli(root, "compute", "--help")
    assert r.returncode == 0 and "--asof" in r.stdout and "--out-dir" in r.stdout
