"""Forecast runner: features -> walk-forward per market x horizon -> ForecastRecord + HorizonForecast + report.

Library API (ADR 0001): forecast(market, asof, paths) -> list[ForecastRecord]; run_market(...) -> MarketRun also
carries the site-facing HorizonForecast objects (narrative_vi left empty: the publisher fills it from the
rulebook) and the backtest report. Deterministic for a given store + asof; created_at is the only clock field.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .. import composites, registry
from ..backtest import stats
from ..backtest.walkforward import walk_forward
from ..common import EconError, Paths, Result, today, utcnow, write_json
from ..schemas import BaselineSkill, Driver, ForecastRecord, HorizonForecast, ReturnBand
from . import data, spec


@dataclass
class Context:
    asof: str
    paths: Paths
    specs: dict
    ccfg: object
    mcfg: spec.ModelsConfig
    X: pd.DataFrame


@dataclass
class MarketRun:
    market: str
    asof: str
    records: list[ForecastRecord] = field(default_factory=list)
    horizons: list[HorizonForecast] = field(default_factory=list)
    reports: dict = field(default_factory=dict)


def context(asof, paths: Paths | None = None, config_dir=None) -> Context:
    """Load configs and compute the composite features once (shared by all markets)."""
    paths = paths or Paths()
    asof = str(asof)[:10]
    specs = registry.load(config_dir)
    ccfg = composites.load(config_dir, specs)
    mcfg = spec.load(config_dir, specs, set(ccfg.composites))
    names = sorted({f for fam in mcfg.models.values() for f in fam.features})
    return Context(asof, paths, specs, ccfg, mcfg, data.features(asof, paths, names, specs, ccfg))


def _num(x, nd: int = 4) -> float:
    return round(float(x), nd) if x is not None and np.isfinite(x) else 0.0


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _drivers(names, contrib, ccfg) -> list[Driver]:
    out = []
    for n, c in sorted(zip(names, contrib), key=lambda t: -abs(t[1])):
        c = round(float(c), 4)
        out.append(Driver(indicator=n, label_vi=ccfg.composites[n].name_vi, contribution=c,
                          direction="neutral" if abs(c) < 1e-3 else ("up" if c > 0 else "down")))
    return out


def _report(bt: dict, model_id: str, target: str, label: str, beats: bool) -> dict:
    clean = lambda m: {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in m.items()}  # noqa: E731
    return {"model_id": model_id, "target": target, "confidence": label, "beats_baselines": beats,
            "short_sample": bt["short_sample"], "min_train": bt["need"], "n_oos": int(len(bt["oos"])),
            "holdout_start": bt["holdout_start"], "oos": clean(bt["metrics"]), "holdout": clean(bt["holdout"])}


def run_market(market: str, asof, paths: Paths | None = None, ctx: Context | None = None,
               created_at: str | None = None) -> MarketRun:
    ctx = ctx or context(asof, paths)
    cfg, d = ctx.mcfg, ctx.mcfg.defaults
    if market not in cfg.targets:
        raise EconError(f"unknown market '{market}'")
    fam_name = cfg.family_for(market)
    fam = cfg.models[fam_name]
    tid = cfg.targets[market].indicator
    tspec = ctx.specs[tid]
    live = pd.Timestamp(ctx.asof)
    used = {m for c in fam.features for m in ctx.ccfg.composites[c].members} | {tid}
    prov = data.last_known(ctx.specs, used, ctx.asof, ctx.paths)
    run = MarketRun(market, ctx.asof)
    created = created_at or utcnow()
    for hk in fam.horizons:
        hs = cfg.horizons[hk]
        medium = hk == "medium"
        target = data.target_for(tspec, hs.months, ctx.asof, ctx.paths)
        bt = walk_forward(ctx.X[fam.features], target, live, hs.months, hs.l2, d, medium)
        lv = bt["live"]
        model_id = cfg.model_id(fam_name, market, hk)
        if lv is None:  # too little history: climatology fallback, never presented as model skill
            final = target.labels_at(live) if hasattr(target, "_o") else pd.DataFrame({"y": []})
            if final.empty:
                continue
            y = final["y"].to_numpy()
            qc = np.quantile(y, (0.1, 0.5, 0.9))
            lv = {"p": float((y > 0).mean()), "q10": qc[0], "q50": qc[1], "q90": qc[2],
                  "p_clim": float((y > 0).mean()), "contrib": np.zeros(len(fam.features)),
                  "x": np.zeros(len(fam.features)), "n_train": len(y)}
            model_id = f"{market}.{hk}.climatology.v1"
        m = bt["metrics"]
        label, beats = stats.confidence(m, d.confidence, medium)
        anchor = target.anchors([live]).iloc[0]
        dasof = dict(prov)
        if pd.notna(anchor):
            dasof[f"anchor:{tid}"] = anchor.date().isoformat()
        band = ReturnBand(p10=round(lv["q10"], 6), p50=round(lv["q50"], 6), p90=round(lv["q90"], 6))
        fh = _hash({"model": model_id, "features": fam.features, "x": np.round(lv["x"], 10).tolist(),
                    "l2": hs.l2, "n_train": lv["n_train"], "data_asof": dasof})
        run.records.append(ForecastRecord(
            id=f"{market}|{hs.months}m|{ctx.asof}|{model_id}", origin=ctx.asof, horizon=f"{hs.months}m",
            market=market, model_id=model_id, p_up=round(lv["p"], 6), quantiles=band, baseline_rw_p_up=0.5,
            baseline_clim_p_up=round(lv["p_clim"], 6), features_hash=fh, data_asof=dasof, created_at=created))
        run.horizons.append(HorizonForecast(
            key=hk, window=hs.window, p_up=round(lv["p"], 4), return_band=band, confidence=label,
            skill=BaselineSkill(vs_random_walk=_num(m.get("bss_rw")), vs_climatology=_num(m.get("bss_clim")),
                                n_eff=int(m.get("n_eff", 0)), beats_baselines=beats),
            drivers=_drivers(fam.features, lv["contrib"], ctx.ccfg), narrative_vi=""))
        run.reports[hk] = _report(bt, model_id, tid, label, beats)
    return run


def forecast(market: str, asof, paths: Paths | None = None, created_at: str | None = None) -> list[ForecastRecord]:
    return run_market(market, asof, paths, created_at=created_at).records


def forecast_all(asof, paths: Paths | None = None, markets=None, created_at: str | None = None) -> list[MarketRun]:
    ctx = context(asof, paths)
    mk = markets or list(ctx.mcfg.targets)
    return [run_market(m, asof, ctx.paths, ctx, created_at) for m in mk]


def out_dir(asof, paths: Paths, args=None) -> Path:
    od = getattr(args, "out_dir", None) if args is not None else None
    return (Path(od) if od else paths.data) / "derived" / "forecasts" / str(asof)[:10]


def cmd_forecast(args) -> Result:
    asof = getattr(args, "asof", None) or today()
    paths = Paths.from_args(args)
    dry = bool(getattr(args, "dry_run", False))
    runs = forecast_all(asof, paths, getattr(args, "market", None) or None)
    dest = out_dir(asof, paths, args)
    lines = [f"forecast asof {asof}: {sum(len(r.records) for r in runs)} records"
             f"{' (dry-run, nothing written)' if dry else ''}"]
    for r in runs:
        for hf, rec in zip(r.horizons, r.records):
            rep = r.reports[hf.key]
            b = hf.return_band
            lines.append(f"  {rec.model_id:<40} p_up {hf.p_up:.2f} band [{b.p10:+.3f} {b.p50:+.3f} {b.p90:+.3f}] "
                         f"bss rw {hf.skill.vs_random_walk:+.3f} clim {hf.skill.vs_climatology:+.3f} "
                         f"n_eff {hf.skill.n_eff} {hf.confidence}{' short-sample' if rep['short_sample'] else ''}")
        if not dry:
            write_json(dest / f"{r.market}.json", {
                "market": r.market, "asof": r.asof, "records": [x.model_dump() for x in r.records],
                "horizons": [x.model_dump() for x in r.horizons], "reports": r.reports})
    if not dry and runs:
        lines.append(f"wrote {dest}")
    data_out = [{"market": r.market, "records": [x.model_dump() for x in r.records], "reports": r.reports}
                for r in runs]
    return Result("\n".join(lines[:40]), data=data_out)
