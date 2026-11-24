"""Append-only vintage store under data/ (the durable copy is the private econ-data repo).

Layout: data/raw/<source>/<series_id>/<fetched_at-stamp>.parquet - one new immutable part file per append;
existing files are never opened for writing. Columns: date, value, fetched_at, backfill, realtime_start.

Vintage rules (no look-ahead), for an as-of date T and publication lag L:
- an observation dated d is usable only if d + L <= T;
- known_at of a row = realtime_start if given (ALFRED), else d + L for `backfill` rows (bulk history load: the
  fetch time says nothing about when it was first published), else fetched_at;
- per date the latest row with known_at <= T wins, so revisions are visible only after they were fetched.
The first load of a series is flagged backfill automatically. Unchanged re-fetches are not stored again.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from .common import EconError, Paths, utcnow
from .schemas import IndicatorSeries

COLS = ["date", "value", "fetched_at", "backfill", "realtime_start"]
_STALE_DAYS = {"D": 7, "W": 14, "M": 75, "Q": 140}


def _dir(paths: Paths, source: str, series: str):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", series)
    return paths.data / "raw" / source / safe


def _load_all(d) -> pd.DataFrame:
    parts = sorted(d.glob("*.parquet")) if d.exists() else []
    if not parts:
        return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype=float),
                             "fetched_at": pd.Series(dtype="datetime64[ns, UTC]"),
                             "backfill": pd.Series(dtype=bool), "realtime_start": pd.Series(dtype="datetime64[ns]")})
    df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    return df


def append(df: pd.DataFrame, paths: Paths | None = None, backfill: bool | None = None) -> int:
    """Append rows (columns: source, series_id, date, value; optional fetched_at, realtime_start) and return the
    number of rows written. Only new dates or changed values are stored (a revision = a new row)."""
    paths = paths or Paths()
    if df is None or df.empty:
        return 0
    need = {"source", "series_id", "date", "value"} - set(df.columns)
    if need:
        raise EconError(f"store.append: missing columns {sorted(need)}")
    written = 0
    for (source, sid), g in df.groupby(["source", "series_id"], sort=False):
        d = _dir(paths, source, sid)
        old = _load_all(d)
        new = pd.DataFrame({
            "date": pd.to_datetime(g["date"]).dt.normalize(),
            "value": pd.to_numeric(g["value"], errors="coerce"),
            "fetched_at": pd.to_datetime(g["fetched_at"] if "fetched_at" in g else utcnow(), utc=True),
            "realtime_start": (pd.to_datetime(g["realtime_start"]).dt.normalize()
                               if "realtime_start" in g else pd.NaT),
        }).dropna(subset=["value"]).sort_values("date").drop_duplicates("date", keep="last")
        new["backfill"] = bool(old.empty) if backfill is None else bool(backfill)
        if not old.empty:
            latest = old.sort_values(["fetched_at"]).drop_duplicates("date", keep="last").set_index("date")["value"]
            prev = new["date"].map(latest)
            new = new[prev.isna() | ((prev - new["value"]).abs() > 1e-12)]
        if new.empty:
            continue
        new = new[COLS].reset_index(drop=True)
        stamp = new["fetched_at"].max().strftime("%Y%m%dT%H%M%S")
        d.mkdir(parents=True, exist_ok=True)
        path, n = d / f"{stamp}.parquet", 0
        while path.exists():  # never overwrite an existing part
            n += 1
            path = d / f"{stamp}-{n}.parquet"
        new.to_parquet(path, index=False)
        written += len(new)
    return written


def read_vintages(source: str, series: str, asof, lag_days: int = 0, paths: Paths | None = None) -> pd.DataFrame:
    """ALL stored rows known by `asof` (every vintage, not only the latest per date) as [date, value, known_at],
    sorted by (date, known_at, fetched_at). Real-time history: grid date T must see the value known at T."""
    paths = paths or Paths()
    t = pd.Timestamp(asof).normalize()
    raw = _load_all(_dir(paths, source, series))
    if raw.empty:
        return pd.DataFrame({"date": [], "value": [], "known_at": []})
    lagged = raw["date"] + pd.Timedelta(days=lag_days)
    fetched = raw["fetched_at"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    known = fetched.where(~raw["backfill"].astype(bool), lagged)
    known = raw["realtime_start"].where(raw["realtime_start"].notna(), known)
    raw = raw.assign(known_at=pd.concat([known, lagged], axis=1).max(axis=1))  # never before date + lag
    raw = raw[raw["known_at"] <= t].sort_values(["date", "known_at", "fetched_at"], kind="mergesort")
    return raw[["date", "value", "known_at"]].reset_index(drop=True)


def read_frame(source: str, series: str, asof, lag_days: int = 0, paths: Paths | None = None) -> pd.DataFrame:
    """Vintage view as a DataFrame [date, value, known_at] (one row per date, ascending), as known at `asof`."""
    v = read_vintages(source, series, asof, lag_days, paths)
    return v.drop_duplicates("date", keep="last").reset_index(drop=True)


def read(id: str, asof, paths: Paths | None = None, spec=None) -> IndicatorSeries:
    """Indicator as known at `asof` (publication lag + vintages honoured)."""
    if spec is None:
        from . import registry

        spec = registry.load().get(id)
        if spec is None:
            raise EconError(f"unknown indicator '{id}'")
    asof_s = str(asof)[:10]
    f = read_frame(spec.source, spec.series, asof_s, spec.lag_days, paths)
    last = f["date"].iloc[-1].date().isoformat() if len(f) else asof_s
    stale = bool(len(f)) is False or (
        dt.date.fromisoformat(asof_s) - dt.date.fromisoformat(last)).days > spec.lag_days + _STALE_DAYS[spec.freq]
    return IndicatorSeries(
        id=spec.id, name=spec.name, unit=spec.unit, freq=spec.freq, source=spec.source,
        license=spec.license_class, attribution=spec.attribution, asof=last, stale=stale,
        dates=[d.date().isoformat() for d in f["date"]], values=[float(v) for v in f["value"]])


def to_series(ser: IndicatorSeries) -> pd.Series:
    """IndicatorSeries -> pandas Series (DatetimeIndex) for transforms."""
    return pd.Series(ser.values, index=pd.to_datetime(ser.dates), name=ser.id, dtype=float)
