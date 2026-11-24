"""`econ fetch`: pull indicators from fred / worldbank_pinksheet / oecd into the append-only store.

A failing source degrades (reported, other sources continue); a missing key is a clear 'skipped'.
Library API: fetch_all(specs, paths, asof, dry_run, budget_override) -> list[Outcome].
"""
from __future__ import annotations

import pandas as pd

from .. import registry, store
from ..common import EconError, Paths, Result, load_yaml, redact, today, CONFIG
from . import fred, oecd, pinksheet
from .base import Budget, Outcome

SOURCES = ("fred", "worldbank_pinksheet", "oecd")
DEFAULT_PER_RUN = 200
REVISION_DAYS = {"D": 30, "W": 60, "M": 400, "Q": 800}


def _per_run(src_cfg: dict, override) -> int:
    if override:
        return int(override)
    b = src_cfg.get("budget") or {}
    return int(b.get("per_run") or DEFAULT_PER_RUN)


def _since(spec, asof, paths):
    f = store.read_frame(spec.source, spec.series, asof, 0, paths)
    if f.empty:
        return None
    return (f["date"].max() - pd.Timedelta(days=REVISION_DAYS[spec.freq])).date()


def _plan(specs, ids, source):
    sel = [s for s in specs.values() if s.source in SOURCES]
    if ids:
        unknown = [i for i in ids if i not in specs]
        if unknown:
            raise EconError(f"unknown indicator id(s): {', '.join(unknown)}")
        sel = [s for s in sel if s.id in ids]
    if source:
        sel = [s for s in sel if s.source == source]
    return sel


def fetch_all(specs, paths, asof, dry_run=False, budget=None, ids=None, source=None) -> list[Outcome]:
    from ..quality import check_frame

    srcs = load_yaml(CONFIG / "sources.yaml").get("sources") or {}
    sel = _plan(specs, ids, source)
    budgets = {s: Budget(_per_run(srcs.get(s, {}), budget), s) for s in SOURCES}
    session = pinksheet.Session()
    out: list[Outcome] = []
    for spec in sel:
        o = Outcome(spec.id, spec.source, "planned" if dry_run else "ok")
        out.append(o)
        if dry_run:
            o.note = f"{spec.series} since={_since(spec, asof, paths) or 'full'}"
            continue
        if spec.source == "fred" and not fred.have_key():
            o.status, o.note = "skipped", "FRED_API_KEY not set"
            continue
        try:
            since = _since(spec, asof, paths)
            b = budgets[spec.source]
            if spec.source == "fred":
                df = fred.fetch(spec, since, b)
            elif spec.source == "oecd":
                df = oecd.fetch(spec, since, b)
            else:
                df = pinksheet.fetch(spec, since, b, session)
            hist = store.read_frame(spec.source, spec.series, asof, 0, paths)
            o.issues = check_frame(df, spec, asof, hist)
            if any(i["level"] == "error" for i in o.issues):
                o.status, o.note = "failed", "quality error, not stored"
                continue
            batches = fred.vintage_batches(df) if spec.source == "fred" else [df]
            o.rows = sum(store.append(bt, paths) for bt in batches)
            o.note = f"last={pd.to_datetime(df['date']).max().date()}"
        except Exception as e:  # degrade: never break the run
            o.status, o.note = "failed", redact(f"{type(e).__name__}: {e}")[:120]
    return out


def cmd_fetch(args) -> Result:
    paths = Paths.from_args(args)
    asof = getattr(args, "asof", None) or today()
    specs = registry.load()
    ids = getattr(args, "id", None)
    dry = bool(getattr(args, "dry_run", False))
    res = fetch_all(specs, paths, asof, dry, getattr(args, "budget", None), ids, getattr(args, "source", None))
    ok = sum(r.status in ("ok", "planned") for r in res)
    lines = [f"fetch {'(dry-run) ' if dry else ''}asof {asof}: {ok}/{len(res)} ok"]
    for r in res[:34]:
        extra = f" issues={','.join(i['code'] for i in r.issues)}" if r.issues else ""
        lines.append(f"  {r.id:<10} {r.source[:8]:<8} {r.status:<8} rows={r.rows:<5} {r.note}{extra}")
    if len(res) > 34:
        lines.append(f"  ... +{len(res) - 34} more")
    bad = any(i["level"] == "error" for r in res for i in r.issues)
    return Result("\n".join(lines[:40]), data=[r.__dict__ for r in res], code=2 if bad else 0)
