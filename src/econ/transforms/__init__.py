"""Pure transforms on pandas Series (DatetimeIndex). No I/O; as-of safe: value at t uses data <= t only."""
from __future__ import annotations

import numpy as np
import pandas as pd

_YOY_TOL_DAYS = {"D": 7, "W": 14, "M": 20, "Q": 45}


def diff(s: pd.Series, periods: int = 1) -> pd.Series:
    return s.diff(periods)


def log_diff(s: pd.Series, periods: int = 1) -> pd.Series:
    return np.log(s.where(s > 0)).diff(periods)


def yoy(s: pd.Series, freq: str = "M") -> pd.Series:
    """Year-over-year growth, calendar based: each date is matched to the last observation on/before the same
    date one year earlier (tolerance by freq); NaN when no base exists, so gaps never shift the base."""
    s = s.dropna().sort_index()
    if s.empty:
        return s.astype(float)
    base_idx = s.index - pd.DateOffset(years=1)
    pos = s.index.searchsorted(base_idx, side="right") - 1
    ok = pos >= 0
    safe = np.clip(pos, 0, None)
    ok &= (base_idx - s.index[safe]) <= pd.Timedelta(days=_YOY_TOL_DAYS[freq])
    base = np.where(ok, s.to_numpy(dtype=float)[safe], np.nan)
    return pd.Series(s.to_numpy(dtype=float) / base - 1.0, index=s.index, name=s.name)


def zscore(s: pd.Series, min_periods: int = 24, window: int | None = None) -> pd.Series:
    """Expanding (default) or rolling z-score; the value at t uses observations <= t only (no look-ahead)."""
    r = s.expanding(min_periods=min_periods) if window is None else s.rolling(window, min_periods=min_periods)
    return (s - r.mean()) / r.std().replace(0, np.nan)


def percentile(s: pd.Series, min_periods: int = 24) -> pd.Series:
    """Expanding percentile rank 0-100 of the value among observations <= t (as-of safe)."""
    v = s.to_numpy(dtype=float)
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        h = v[: i + 1]
        h = h[~np.isnan(h)]
        if np.isnan(v[i]) or len(h) < min_periods:
            continue
        out[i] = 100.0 * (np.count_nonzero(h < v[i]) + 0.5 * np.count_nonzero(h == v[i])) / len(h)
    return pd.Series(out, index=s.index, name=s.name)


def resample(s: pd.Series, freq: str = "M", how: str = "last") -> pd.Series:
    """Down-sample to month-end / week-end / quarter-end. Labelled by period end and uses only observations
    inside the period, so the value is never known before its label date."""
    rule = {"M": "ME", "W": "W-SUN", "Q": "QE", "D": "D"}[freq]
    return getattr(s.dropna().resample(rule), how)().dropna()


def apply(name: str, s: pd.Series, freq: str = "D") -> pd.Series:
    """Dispatch a registry transform name."""
    if name == "level":
        return s
    if name == "diff":
        return diff(s)
    if name == "log_diff":
        return log_diff(s)
    if name == "yoy":
        return yoy(s, freq)
    if name == "zscore":
        return zscore(s)
    raise ValueError(f"unknown transform: {name}")
