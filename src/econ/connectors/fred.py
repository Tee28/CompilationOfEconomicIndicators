"""FRED / ALFRED observations. Key from FRED_API_KEY (http.fill); never printed.

Monthly/weekly/quarterly series are fetched as ALL vintages (realtime_start..9999-12-31) so revisions are stored
with their real publication dates (as-of correctness). Daily series are not revised: plain latest values.
"""
from __future__ import annotations

import pandas as pd

from .. import http
from ..common import EconError, utcnow
from .base import Budget, get_text

URL = "https://api.stlouisfed.org/fred/series/observations"
VINTAGE_FREQS = {"M", "W", "Q"}
VINTAGE_FROM = "2010-01-01"
PAGE = 100000


class MissingKey(EconError):
    pass


def api_key() -> str:
    k = http.fill("{FRED_API_KEY}").strip()
    if not k:
        raise MissingKey("FRED_API_KEY not set")
    return k


def have_key() -> bool:
    return bool(http.fill("{FRED_API_KEY}").strip())


def parse(js: dict, vintage: bool) -> pd.DataFrame:
    """Pure: FRED JSON -> [date, value, realtime_start]. '.' (missing) rows are dropped."""
    cols = ["date", "value", "realtime_start"]
    rows = js.get("observations") or []
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"]) if vintage else pd.NaT
    return df.reset_index(drop=True)


def fetch(spec, since, budget: Budget) -> pd.DataFrame:
    vintage = spec.freq in VINTAGE_FREQS
    key = api_key()
    out, offset = [], 0
    while True:
        budget.take(1)
        params = {"series_id": spec.series, "api_key": key, "file_type": "json", "limit": PAGE, "offset": offset}
        if since:
            params["observation_start"] = str(since)[:10]
        if vintage:
            params.update(realtime_start=VINTAGE_FROM, realtime_end="9999-12-31")
        js = get_text(URL, params, source="fred").json()
        out.append(parse(js, vintage))
        if len(js.get("observations") or []) < PAGE:
            break
        offset += PAGE
    df = pd.concat(out, ignore_index=True)
    return df.assign(series_id=spec.series, source="fred", fetched_at=pd.Timestamp(utcnow()))


def vintage_batches(df: pd.DataFrame) -> list[pd.DataFrame]:
    """store.append keeps one row per date per call: split vintages into ordered batches (k-th vintage of every
    date goes in batch k), so revisions land as new rows."""
    if df.empty or df["realtime_start"].isna().all():
        return [df]
    d = df.sort_values(["date", "realtime_start"]).copy()
    d["_k"] = d.groupby("date").cumcount()
    return [g.drop(columns="_k") for _, g in d.groupby("_k")]
