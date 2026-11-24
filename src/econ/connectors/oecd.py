"""OECD Data Explorer SDMX (CSV). CLI dataflow: OECD.SDD.STES,DSD_STES@DF_CLI.
Key order: REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY, so
USA.M.LI.IX._Z.AA.IX._Z.H = US, monthly, leading indicator, index, amplitude adjusted, OECD standard methodology.
The key follows the published DSD but is NOT yet confirmed live: verify on the runner at the first fetch."""
from __future__ import annotations

import io

import pandas as pd

from ..common import EconError, utcnow
from .base import Budget, get_text

BASE = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/"
CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv; charset=utf-8"}


def parse(text: str) -> pd.DataFrame:
    """Pure: SDMX-CSV -> [date, value]. TIME_PERIOD 'YYYY-MM' -> first of month."""
    if not (text or "").strip():
        raise EconError("oecd: empty response")
    df = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in df or "OBS_VALUE" not in df:
        raise EconError("oecd: CSV lacks TIME_PERIOD/OBS_VALUE")
    t = df["TIME_PERIOD"].astype(str)
    t = t.where(t.str.len() != 7, t + "-01")
    out = pd.DataFrame({"date": pd.to_datetime(t), "value": pd.to_numeric(df["OBS_VALUE"], errors="coerce")})
    return out.dropna().sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def fetch(spec, since, budget: Budget) -> pd.DataFrame:
    budget.take(1)
    params = {"format": "csvfile"}
    if since:
        params["startPeriod"] = str(since)[:7]
    r = get_text(BASE + spec.series, params, headers=CSV_ACCEPT, source="oecd")
    return parse(r.text).assign(series_id=spec.series, source="oecd", fetched_at=pd.Timestamp(utcnow()))
