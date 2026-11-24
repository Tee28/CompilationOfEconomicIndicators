"""Per-fetch data quality checks. Pure functions; issues are dicts consumed by Health (never raise).

Issue: {id, level: warn|error, code, msg}. error = do not trust/store the frame; warn = store, mark degraded.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

# tolerated age of the last observation beyond lag_days, by frequency (days)
STALE_SLACK = {"D": 7, "W": 14, "M": 40, "Q": 100}
Z_LIMIT = 6.0


def _issue(sid, level, code, msg):
    return {"id": sid, "level": level, "code": code, "msg": msg}


def check_frame(df: pd.DataFrame, spec, asof=None, history: pd.DataFrame | None = None) -> list[dict]:
    """Schema, dates (sorted/unique), NaN, range/outlier vs history, unit jump, staleness vs expected lag."""
    sid = getattr(spec, "id", "?")
    out: list[dict] = []
    if df is None or df.empty:
        return [_issue(sid, "error", "empty", "no observations returned")]
    miss = {"date", "value"} - set(df.columns)
    if miss:
        return [_issue(sid, "error", "schema", f"missing columns {sorted(miss)}")]
    d = pd.to_datetime(df["date"])
    v = pd.to_numeric(df["value"], errors="coerce")
    n_nan = int(v.isna().sum())
    if n_nan:
        out.append(_issue(sid, "warn", "nan", f"{n_nan} NaN values"))
    if not np.isfinite(v.dropna()).all():
        out.append(_issue(sid, "error", "inf", "non-finite values"))
    if d.duplicated().any() and ("realtime_start" not in df or df["realtime_start"].isna().all()):
        out.append(_issue(sid, "warn", "dup_dates", f"{int(d.duplicated().sum())} duplicate dates"))
    if not d.is_monotonic_increasing and ("realtime_start" not in df or df["realtime_start"].isna().all()):
        out.append(_issue(sid, "warn", "order", "dates not monotonic"))
    vals = v.dropna()
    if (getattr(spec, "unit", "") in ("USD/toz", "USD/bbl", "index", "persons", "thousand")) and (vals < 0).any() \
            and getattr(spec, "id", "") not in ("t10y2y",):
        out.append(_issue(sid, "warn", "range", "negative values for a level series"))
    base = history["value"].dropna() if history is not None and len(history) else vals.iloc[:-1]
    if len(base) >= 30 and len(vals):
        sd = float(base.tail(500).std())
        mu = float(base.tail(500).mean())
        last = float(vals.iloc[-1])
        if sd > 0 and abs(last - mu) / sd > Z_LIMIT:
            out.append(_issue(sid, "warn", "outlier", f"last value |z|>{Z_LIMIT:g} vs history"))
        prev = float(base.iloc[-1])
        if prev and abs(prev) > 1e-9 and (abs(last / prev) >= 10 or abs(last / prev) <= 0.1):
            out.append(_issue(sid, "warn", "unit_jump", "last/prev ratio >= 10 (scale change?)"))
    out += staleness(sid, d.max(), spec, asof)
    return out


def staleness(sid, last_obs, spec, asof=None) -> list[dict]:
    asof = pd.Timestamp(asof or dt.date.today()).normalize()
    age = (asof - pd.Timestamp(last_obs).normalize()).days
    limit = int(spec.lag_days) + STALE_SLACK[spec.freq]
    if age > limit:
        return [_issue(sid, "warn", "stale", f"last obs {pd.Timestamp(last_obs).date()} is {age}d old (> {limit}d)")]
    return []


def health_entry(issues: list[dict], last_obs=None, asof=None, ok: bool = True, note: str = "") -> dict:
    """Source-level record for ledger/health.json: {ok, last_obs, lag_days, fails, note}."""
    lag = None
    if last_obs is not None:
        lag = (pd.Timestamp(asof or dt.date.today()).normalize() - pd.Timestamp(last_obs).normalize()).days
    errs = [i for i in issues if i["level"] == "error"]
    return {"ok": bool(ok and not errs), "last_obs": None if last_obs is None else str(pd.Timestamp(last_obs).date()),
            "lag_days": lag, "fails": len(errs), "note": note or "; ".join(sorted({i["code"] for i in issues}))}
