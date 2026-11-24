"""Pure composite math (no I/O). Every value at grid date T uses only rows with known_at <= T.

Grid = month-ends up to the as-of date, plus the as-of date itself when it is not a month-end.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import transforms as tf


def grid(start, asof) -> pd.DatetimeIndex:
    a = pd.Timestamp(asof).normalize()
    s = pd.Timestamp(start).normalize() + pd.offsets.MonthEnd(0)
    g = pd.date_range(s, a, freq="ME")
    if len(g) == 0 or g[-1] != a:
        g = g.append(pd.DatetimeIndex([a]))
    return g


def sample(frame: pd.DataFrame, g: pd.DatetimeIndex, agg: str, max_ffill: int, lag_days: int = 0) -> pd.Series:
    """Vintage frame [date, value, known_at] -> one value per grid date.

    last: value of the latest observation date among rows known by T (a late revision of an old date never
          overrides a newer observation); withheld when that row became known > max_ffill periods ago.
    mean: mean of rows that became known in (T_prev, T] and belong to that period (revisions of older dates
          are ignored); carried forward at most max_ffill periods.
    """
    out = pd.Series(np.nan, index=g, dtype=float)
    if frame is None or len(frame) == 0:
        return out
    f = frame.assign(date=pd.to_datetime(frame["date"]), known_at=pd.to_datetime(frame["known_at"]))
    f = f.sort_values(["known_at", "date"], kind="mergesort").reset_index(drop=True)
    pos = g.searchsorted(f["known_at"].to_numpy(), side="left")  # first grid date >= known_at
    keep = pos < len(g)
    f, pos = f[keep].reset_index(drop=True), pos[keep]
    if f.empty:
        return out
    vals = f["value"].to_numpy(dtype=float)
    if agg == "last":
        dates = f["date"].to_numpy()
        best = np.empty(len(f), dtype=int)  # running argmax of observation date over the known_at prefix
        b = 0
        for i in range(len(f)):
            if dates[i] >= dates[b]:
                b = i
            best[i] = b
        # last row (in known_at order) of each grid bucket = the prefix known by that grid date
        last_in_bucket = pd.Series(np.arange(len(f))).groupby(pos).max()
        res = np.full(len(g), -1)
        res[last_in_bucket.index.to_numpy()] = best[last_in_bucket.to_numpy()]
        res = pd.Series(res).replace(-1, np.nan).ffill()
        for t, r in res.items():
            if np.isnan(r):
                continue
            r = int(r)
            if t - pos[r] <= max_ffill:
                out.iloc[t] = vals[r]
        return out
    # mean
    prev = g[np.clip(pos - 1, 0, None)].to_numpy()  # previous grid date (ignored for bucket 0)
    lagged = (f["date"] + pd.Timedelta(days=lag_days)).to_numpy()
    fresh = (pos == 0) | (lagged > prev)
    fr = pd.DataFrame({"pos": pos[fresh], "date": f["date"].to_numpy()[fresh], "v": vals[fresh]})
    fr = fr.drop_duplicates(["pos", "date"], keep="last")  # same-period revision: latest known value counts once
    m = fr.groupby("pos")["v"].mean()
    out.iloc[m.index.to_numpy()] = m.to_numpy()
    return out.ffill(limit=max_ffill) if max_ffill > 0 else out


def transform(x: pd.Series, name: str) -> pd.Series:
    """Grid transform: level | chg_<N>m (x_t - x_{t-N}) | pct_<N>m (x_t / x_{t-N} - 1), N grid periods back."""
    if name == "level":
        return x
    kind, n = name.split("_")
    n = int(n[:-1])
    if kind == "chg":
        return x - x.shift(n)
    base = x.shift(n)
    return x / base.where(base > 0) - 1.0


def zscore(f: pd.Series, min_periods: int, clip: float) -> pd.Series:
    """Expanding z-score (stats from values <= t only), winsorised at +-clip."""
    return tf.zscore(f, min_periods=min_periods).clip(-clip, clip)


def combine(z: pd.DataFrame, weights: dict[str, float], min_coverage: float):
    """Weighted mean over present members, weights renormalised per date.
    Returns (level, coverage, used_weights DataFrame)."""
    w = pd.Series(weights, dtype=float).reindex(z.columns)
    present = z.notna()
    wp = present.mul(w, axis=1)
    cov = wp.sum(axis=1) / w.sum()
    denom = wp.sum(axis=1).replace(0, np.nan)
    level = z.fillna(0.0).mul(w, axis=1).sum(axis=1) / denom
    level = level.where(cov >= min_coverage - 1e-12)
    used = wp.div(denom, axis=0)
    return level, cov, used


def percentile(level: pd.Series, min_periods: int) -> pd.Series:
    """Expanding percentile of the composite among its own past values (as-of safe)."""
    return tf.percentile(level, min_periods=min_periods)


def label(pct, bands: list[float], labels: list[str]) -> str | None:
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return None
    i = int(np.searchsorted(np.asarray(bands, dtype=float), float(pct), side="right"))
    return labels[i]
