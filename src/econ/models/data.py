"""As-of datasets: composite features on the origin grid and vintage-aware target labels.

Features: composite levels from composites.frames (real-time history: value at grid date T uses rows known at T).
Target: log change of the target series from the anchor (latest obs known at the origin) to the obs h months
later. A label is usable at time T only once that later obs is known (first known_at <= T), and its values are
taken as known at T (vintages), so training at an old origin never sees later revisions or later prices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import composites, store
from ..common import Paths

_TOL_DAYS = {"D": 7, "W": 14}


def features(asof, paths: Paths, names: list[str], specs: dict, ccfg) -> pd.DataFrame:
    """Composite levels (columns = composite ids) on the month-end grid + the as-of date."""
    cols = {}
    for cid in names:
        fr = composites.frames(ccfg.composites[cid], str(asof)[:10], paths, specs, ccfg)
        cols[cid] = fr["level"] if fr else pd.Series(dtype=float)
    df = pd.DataFrame(cols)
    if df.empty:
        return pd.DataFrame(columns=names, dtype=float)
    return df.reindex(columns=names).sort_index().astype(float)


def last_known(specs: dict, ids, asof, paths: Paths) -> dict[str, str]:
    """indicator id -> last observation date known at `asof` (provenance for ForecastRecord.data_asof)."""
    out = {}
    for i in sorted(set(ids)):
        sp = specs[i]
        f = store.read_frame(sp.source, sp.series, str(asof)[:10], sp.lag_days, paths)
        if len(f):
            out[i] = pd.Timestamp(f["date"].iloc[-1]).date().isoformat()
    return out


class Target:
    """Vintage rows [date, value, known_at] of the target series + horizon h (months)."""

    def __init__(self, rows: pd.DataFrame, freq: str, h: int):
        r = rows.assign(date=pd.to_datetime(rows["date"]), known_at=pd.to_datetime(rows["known_at"]))
        self.rows = r.sort_values(["date", "known_at"], kind="mergesort").reset_index(drop=True)
        self.freq, self.h = freq, int(h)
        self.first = self.rows.groupby("date")["known_at"].min().sort_index()  # first time each date was known
        self._cache: dict = {}

    # ---------------------------------------------------------------- dates
    def anchors(self, origins) -> pd.Series:
        """Latest observation date known at each origin (NaT before the first one)."""
        o = pd.DatetimeIndex(origins)
        if self.first.empty:
            return pd.Series(pd.NaT, index=o)
        byk = self.first.sort_values(kind="mergesort")
        cummax = pd.Series(byk.index.to_numpy()).cummax().to_numpy()
        pos = np.searchsorted(byk.to_numpy(), o.to_numpy(), side="right") - 1
        vals = np.where(pos >= 0, cummax[np.clip(pos, 0, None)], np.datetime64("NaT", "ns"))
        return pd.Series(pd.to_datetime(vals), index=o)

    def target_date(self, d0):
        """Obs date h months after anchor d0 (monthly/quarterly: exact period; daily/weekly: last obs on or
        before d0 + h months within tolerance). NaT if that obs does not exist (yet)."""
        if pd.isna(d0):
            return pd.NaT
        goal = pd.Timestamp(d0) + pd.DateOffset(months=self.h)
        if self.freq in ("M", "Q"):
            return goal if goal in self.first.index else pd.NaT
        idx = self.first.index
        p = idx.searchsorted(goal, side="right") - 1
        if p < 0 or idx[p] <= pd.Timestamp(d0) or (goal - idx[p]).days > _TOL_DAYS.get(self.freq, 7):
            return pd.NaT
        return idx[p]

    def values_at(self, t) -> pd.Series:
        """date -> value as known at t (latest vintage with known_at <= t)."""
        r = self.rows[self.rows["known_at"] <= pd.Timestamp(t)]
        return r.drop_duplicates("date", keep="last").set_index("date")["value"].astype(float)

    def realized(self, d0, t) -> tuple[float | None, pd.Timestamp | None]:
        """(log return anchor -> target obs, target date) if known at t, else (None, None)."""
        d1 = self.target_date(d0)
        if pd.isna(d1) or self.first.get(d1, pd.Timestamp.max) > pd.Timestamp(t):
            return None, None
        v = self.values_at(t)
        if d0 not in v.index or d1 not in v.index or v[d0] <= 0 or v[d1] <= 0:
            return None, None
        return float(np.log(v[d1] / v[d0])), d1

    # ---------------------------------------------------------------- labels
    def prepare(self, origins) -> None:
        o = pd.DatetimeIndex(origins)
        a = self.anchors(o)
        d1 = pd.Series([self.target_date(x) for x in a], index=o, dtype="datetime64[ns]")
        k1 = d1.map(self.first)
        self._o = pd.DataFrame({"anchor": a, "tdate": d1, "known_at": pd.to_datetime(k1)}, index=o)
        self._cache = {}

    def labels_at(self, t) -> pd.DataFrame:
        """Labels known at t: index origin, columns [y, known_at]. Requires prepare(origins) first."""
        t = pd.Timestamp(t)
        if t in self._cache:
            return self._cache[t]
        o = self._o[(self._o["known_at"] <= t) & (self._o.index <= t)].dropna()
        v = self.values_at(t)
        va = o["anchor"].map(v).to_numpy(dtype=float)
        vb = o["tdate"].map(v).to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            y = np.where((va > 0) & (vb > 0), np.log(vb / va), np.nan)
        out = pd.DataFrame({"y": y, "known_at": o["known_at"]}, index=o.index).dropna(subset=["y"])
        self._cache[t] = out
        return out


def target_for(spec, h: int, asof, paths: Paths) -> Target:
    rows = store.read_vintages(spec.source, spec.series, str(asof)[:10], spec.lag_days, paths)
    return Target(rows, spec.freq, h)
