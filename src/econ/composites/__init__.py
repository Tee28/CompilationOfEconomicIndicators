"""Composites: as-of safe expanding z-scores of registry indicators, weighted with coverage renormalisation.

Config: config/composites.yaml (spec.py). Math: engine.py. Contract: schemas.CompositeSeries (ADR 0001).
`compute(asof, paths)` is deterministic: same store + same asof -> same output; no wall-clock inside.
Real-time history: every grid date T is built from the rows known at T (all stored vintages), so the series
computed today equals what a run at T would have printed (truncation/vintage tests in tests/test_composites.py).
A revision of an old observation never rewrites history; it matters only while that date is the latest one.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .. import store
from ..common import EconError, Paths, Result, today, write_json
from ..schemas import CompositeSeries, CompositeSummary
from . import engine
from .spec import CompositeSpec, CompositesConfig, derived_license, load  # noqa: F401  (re-export)


def _iso(ts) -> str:
    return pd.Timestamp(ts).date().isoformat()


def _num(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 6)


def vintage_rows(source: str, series: str, asof, lag_days: int, paths: Paths) -> pd.DataFrame:
    """ALL stored rows known by `asof` (every vintage, not only the latest per date) as [date, value, known_at].
    Needed for real-time history: grid date T must see the value as known at T, not today's revision.
    Thin alias of `store.read_vintages` (tests pin: last row per date here == store.read_frame)."""
    return store.read_vintages(source, series, asof, lag_days, paths)


def frames(comp: CompositeSpec, asof, paths: Paths, specs: dict, cfg: CompositesConfig) -> dict:
    """All intermediate frames for one composite on its grid: z (signed, clipped member z-scores),
    level, coverage, used (renormalised weights per date), percentile. Models read `z`/`used` for drivers."""
    d = cfg.defaults
    vint = {m: vintage_rows(specs[m].source, specs[m].series, str(asof)[:10], specs[m].lag_days, paths)
            for m in comp.members}
    starts = [pd.to_datetime(f["known_at"]).min() for f in vint.values() if len(f)]
    if not starts:
        return {}
    g = engine.grid(min(starts), asof)
    z = {}
    for m, ms in comp.members.items():
        sp = specs[m]
        x = engine.sample(vint[m], g, ms.agg, d.max_ffill.get(sp.freq, 1), sp.lag_days)
        feat = ms.sign * engine.transform(x, ms.transform)
        z[m] = engine.zscore(feat, d.zscore_min_periods, d.clip)
    z = pd.DataFrame(z, index=g)
    weights = {m: ms.weight for m, ms in comp.members.items()}
    level, cov, used = engine.combine(z, weights, comp.min_coverage or d.min_coverage)
    pct = engine.percentile(level, d.percentile_min_periods)
    return {"grid": g, "z": z, "level": level, "coverage": cov, "used": used, "percentile": pct}


def contributions(cid: str, asof, paths: Paths | None = None, config_dir=None) -> pd.DataFrame:
    """Per-member contribution to the composite level (renormalised weight x signed z); rows sum to level."""
    from .. import registry

    specs = registry.load(config_dir)
    cfg = load(config_dir, specs)
    if cid not in cfg.composites:
        raise EconError(f"unknown composite '{cid}'")
    fr = frames(cfg.composites[cid], asof, paths or Paths(), specs, cfg)
    if not fr:
        return pd.DataFrame()
    c = fr["z"].fillna(0.0) * fr["used"]
    return c.where(fr["level"].notna(), axis=0)


def _series(comp: CompositeSpec, fr: dict, asof, specs: dict) -> CompositeSeries:
    lic = derived_license(comp, specs)
    base = dict(id=comp.id, name=comp.name, members=list(comp.members), license=lic, asof=str(asof)[:10])
    if not fr:
        return CompositeSeries(coverage=0.0, **base)
    last = fr["grid"][-1]
    used = fr["used"].loc[last]
    weights = {m: round(float(w), 6) for m, w in used.items() if np.isfinite(w) and w > 0}
    return CompositeSeries(
        coverage=round(float(min(max(fr["coverage"].loc[last], 0.0), 1.0)), 6), weights=weights,
        dates=[_iso(t) for t in fr["grid"]], levels=[_num(v) for v in fr["level"]],
        percentiles=[_num(v) for v in fr["percentile"]], **base)


def compute(asof, paths: Paths | None = None, config_dir=None) -> list[CompositeSeries]:
    """All configured composites as known at `asof` (library API, ADR 0001)."""
    from .. import registry

    paths = paths or Paths()
    specs = registry.load(config_dir)
    cfg = load(config_dir, specs)
    return [_series(c, frames(c, asof, paths, specs, cfg), asof, specs) for c in cfg.composites.values()]


def latest(cs: CompositeSeries) -> tuple[str | None, float | None, float | None]:
    """(date, level, percentile) of the last point that has a percentile."""
    for d, lv, p in zip(reversed(cs.dates), reversed(cs.levels), reversed(cs.percentiles)):
        if p is not None:
            return d, lv, p
    return None, None, None


def summary(cs: CompositeSeries, comp: CompositeSpec, cfg: CompositesConfig) -> CompositeSummary | None:
    """Site-facing summary; level is None for internal-class composites (license rule). None if no percentile."""
    d, lv, p = latest(cs)
    if p is None:
        return None
    return CompositeSummary(id=cs.id, name_vi=comp.name_vi, license=cs.license,
                            level=None if cs.license == "internal" else lv, percentile=p,
                            label=engine.label(p, cfg.defaults.label_bands, comp.labels_vi), asof=d)


def out_dir(asof, paths: Paths, args=None) -> Path:
    od = getattr(args, "out_dir", None) if args is not None else None
    return (Path(od) if od else paths.data) / "derived" / "composites" / str(asof)[:10]


def cmd_compute(args) -> Result:
    from .. import registry

    asof = getattr(args, "asof", None) or today()
    paths = Paths.from_args(args)
    specs = registry.load()
    cfg = load(None, specs)
    res = compute(asof, paths)
    dest = out_dir(asof, paths, args)
    dry = bool(getattr(args, "dry_run", False))
    lines = [f"compute asof {asof}: {len(res)} composites{' (dry-run, nothing written)' if dry else ''}"]
    for cs in res:
        comp = cfg.composites[cs.id]
        d, lv, p = latest(cs)
        lab = engine.label(p, cfg.defaults.label_bands, comp.labels_vi) if p is not None else "n/a"
        lvs = "hidden" if cs.license == "internal" else ("n/a" if lv is None else f"{lv:+.2f}")
        pcs = "n/a" if p is None else f"{p:.0f}"
        lines.append(f"  {cs.id:<20} {cs.license:<10} cov {cs.coverage:.2f} n={len(cs.dates):<4} "
                     f"last {d or '-'} level {lvs} pct {pcs} [{lab}]")
        missing = [m for m in cs.members if m not in cs.weights]
        if missing:
            lines.append(f"    missing at asof: {', '.join(missing)}")
        if not dry:
            write_json(dest / f"{cs.id}.json", cs.model_dump())
    if not dry:
        lines.append(f"wrote {dest}")
    return Result("\n".join(lines[:40]), data=[cs.model_dump() for cs in res])
