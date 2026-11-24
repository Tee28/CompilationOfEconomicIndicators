"""Registry, vintage store and transforms (offline, tmp_path)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econ import registry, store
from econ import transforms as tf
from econ.common import EconError, Paths


def _df(sid, source, dates, values, fetched):
    return pd.DataFrame({"source": source, "series_id": sid, "date": dates, "value": values, "fetched_at": fetched})


# ------------------------------------------------------------------ registry
def test_registry_loads_live_slice():
    specs = registry.load()
    assert len(specs) >= 19
    assert specs["sp500"].license_class == "internal"
    assert specs["cpi"].attribution.startswith("This product uses the FRED")
    assert {m for s in specs.values() for m in s.markets} == {"global_macro", "us_equities", "gold", "oil"}


def test_registry_rejects_bad_entries(tmp_path):
    (tmp_path / "sources.yaml").write_text(
        "sources:\n  fred: {license_class: attributed, series: [A]}\n  x: {license_class: internal, series: [B]}\n",
        encoding="utf-8")
    (tmp_path / "indicators.yaml").write_text(
        "indicators:\n"
        "  a: {name: a, source: fred, series: Z, freq: D, lag_days: 1, license_class: attributed, markets: [gold]}\n"
        "  b: {name: b, source: nope, series: A, freq: D, lag_days: 1, license_class: open, markets: [gold]}\n"
        "  c: {name: c, source: x, series: B, freq: D, lag_days: 1, license_class: open, markets: [gold]}\n",
        encoding="utf-8")
    with pytest.raises(EconError) as e:
        registry.load(tmp_path)
    msg = str(e.value)
    assert "not declared" in msg and "unknown source" in msg and "weaker" in msg


def test_ind_list_cli_short():
    class A:
        market, license = "gold", None

    r = registry.cmd_ind_list(A())
    assert len(r.text.splitlines()) <= 40 and "gold_pink" in r.text


# ------------------------------------------------------------------ store
def test_append_only_and_revision(tmp_path):
    p = Paths(data=tmp_path)
    d = ["2026-01-01", "2026-02-01"]
    assert store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.0], "2026-03-01T00:00:00Z"), p) == 2
    # unchanged re-fetch stores nothing; a revision stores one new row
    assert store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.0], "2026-03-05T00:00:00Z"), p) == 0
    assert store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.5], "2026-04-01T00:00:00Z"), p) == 1
    parts = sorted((tmp_path / "raw" / "fred" / "CPIAUCSL").glob("*.parquet"))
    assert len(parts) == 2  # old part untouched, revision in a new part


def test_asof_honours_lag_and_vintage(tmp_path):
    p = Paths(data=tmp_path)
    d = ["2026-01-01", "2026-02-01"]
    store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.0], "2026-06-01T00:00:00Z"), p)  # first load = backfill
    store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.5], "2026-07-01T00:00:00Z"), p)  # revision of Feb
    spec = registry.load()["cpi"]  # lag 45
    f = lambda asof: store.read("cpi", asof, p, spec=spec)  # noqa: E731
    assert f("2026-02-14").dates == []  # Jan 1 + 45d = Feb 15 -> usable from that day
    assert f("2026-02-15").dates == ["2026-01-01"]
    assert f("2026-03-10").values == [100.0]  # Feb 1 + 45d = Mar 18
    assert f("2026-03-20").values == [100.0, 101.0]  # original vintage, not the later revision
    assert f("2026-06-30").values == [100.0, 101.0]
    assert f("2026-07-01").values == [100.0, 101.5]  # revision visible only once fetched


def test_read_empty_and_missing(tmp_path):
    s = store.read("vix", "2026-01-01", Paths(data=tmp_path))
    assert s.dates == [] and s.license == "internal"
    with pytest.raises(EconError):
        store.read("nope", "2026-01-01", Paths(data=tmp_path))


def test_append_validates_columns(tmp_path):
    with pytest.raises(EconError):
        store.append(pd.DataFrame({"date": ["2026-01-01"], "value": [1.0]}), Paths(data=tmp_path))


# ------------------------------------------------------------------ transforms
def _m(n=40, start="2020-01-01"):
    return pd.Series(np.arange(1.0, n + 1), index=pd.date_range(start, periods=n, freq="MS"))


def test_yoy_and_gap():
    s = _m(15)
    y = tf.yoy(s, "M")
    assert y.iloc[:12].isna().all() and y.iloc[12] == pytest.approx(13 / 1 - 1)
    assert np.isnan(tf.yoy(s.drop(s.index[0]), "M").iloc[11])  # base month missing -> NaN, no shift


def test_diff_logdiff():
    s = pd.Series([1.0, 2.0, 4.0], index=pd.date_range("2026-01-01", periods=3))
    assert tf.diff(s).iloc[2] == 2.0
    assert tf.log_diff(s).iloc[2] == pytest.approx(np.log(2))


def test_zscore_no_lookahead():
    s = _m(40)
    z = tf.zscore(s, min_periods=12)
    s2 = s.copy()
    s2.iloc[30:] = 1000.0  # change the future
    z2 = tf.zscore(s2, min_periods=12)
    assert z.iloc[:30].equals(z2.iloc[:30]) and z.iloc[:11].isna().all()
    p = tf.percentile(s, min_periods=12)
    assert p.iloc[-1] > 95 and p.iloc[:11].isna().all()


def test_resample_and_apply():
    s = pd.Series(range(60), index=pd.date_range("2026-01-01", periods=60, freq="D"), dtype=float)
    m = tf.resample(s, "M", "last")
    assert m.index[0] == pd.Timestamp("2026-01-31") and m.iloc[0] == 30
    assert tf.apply("level", s) is s
    with pytest.raises(ValueError):
        tf.apply("bogus", s)


def test_read_vintages_all_rows_and_consistent_with_read_frame(tmp_path):
    p = Paths(data=tmp_path)
    d = ["2026-01-01", "2026-02-01"]
    store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.0], "2026-06-01T00:00:00Z"), p)
    store.append(_df("CPIAUCSL", "fred", d, [100.0, 101.5], "2026-07-01T00:00:00Z"), p)
    v = store.read_vintages("fred", "CPIAUCSL", "2026-06-30", 45, p)
    assert v["value"].tolist() == [100.0, 101.0]
    v = store.read_vintages("fred", "CPIAUCSL", "2026-07-01", 45, p)
    assert v["value"].tolist() == [100.0, 101.0, 101.5]  # both Feb vintages kept
    assert list(v.columns) == ["date", "value", "known_at"]
    last = v.drop_duplicates("date", keep="last").reset_index(drop=True)
    assert last.equals(store.read_frame("fred", "CPIAUCSL", "2026-07-01", 45, p))
    assert store.read_vintages("fred", "NOPE", "2026-07-01", 0, p).empty
