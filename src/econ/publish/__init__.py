"""Publish: forecasts + composites -> narrative -> license-gated, content-hashed site JSON + manifest.

Library API (ADR 0001): build(asof, paths, runs=None, comps=None, write=True) -> Manifest.
Gate: internal-license series carry no dates/values and internal composites no level (types enforce it; `scan`
re-derives licenses from the registry and re-checks the files on disk). Size budget: audit.site_json_kb per file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .. import composites as comp_mod
from .. import models, registry, store
from ..common import EconError, Paths, Result, cfg, today, utcnow
from ..schemas import FileEntry, HorizonForecast, Manifest, MarketPage, MarketSummary, Overview, SiteSeries
from . import narrative

HASHED = re.compile(r"^[a-z_]+\.[0-9a-f]{8}\.json$")
MAX_POINTS = {"D": 260, "W": 260, "M": 180, "Q": 80}


class GateError(EconError):
    """License or size gate violation (exit 2)."""


def _dump(model) -> bytes:
    return (json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n").encode("utf-8")


def _site_indicator(spec, asof, paths) -> SiteSeries:
    base = dict(id=spec.id, name_vi=spec.name, unit=spec.unit, license=spec.license_class,
                attribution=spec.attribution)
    if spec.license_class == "internal":
        return SiteSeries(**base)  # models only: no values, no dates
    s = store.read(spec.id, asof, paths, spec)
    n = MAX_POINTS[spec.freq]
    return SiteSeries(stale=s.stale, dates=s.dates[-n:], values=[round(v, 4) for v in s.values[-n:]], **base)


def _site_composite(cs, comp, n=MAX_POINTS["M"]) -> SiteSeries:
    base = dict(id=cs.id, name_vi=comp.name_vi, license=cs.license)
    if cs.license == "internal":
        return SiteSeries(**base)
    pts = [(d, v) for d, v in zip(cs.dates, cs.levels, strict=True) if v is not None][-n:]
    return SiteSeries(dates=[d for d, _ in pts], values=[v for _, v in pts], **base)


def _market_page(run, asof, specs, ccfg, mcfg, comps, paths, ph) -> MarketPage:
    # re-validate after the narrative is filled (model_copy skips validators)
    hs = [HorizonForecast.model_validate(
        {**h.model_dump(), "narrative_vi": narrative.horizon_text(run.market, h, asof, ph)}) for h in run.horizons]
    tid = mcfg.targets[run.market].indicator
    series = [_site_indicator(specs[tid], asof, paths)]
    for c in mcfg.models[mcfg.family_for(run.market)].features:
        if c in comps:
            series.append(_site_composite(comps[c], ccfg.composites[c]))
    return MarketPage(market=run.market, title_vi=ph["markets"][run.market]["name"], asof=asof, horizons=hs,
                      series=series, narrative_vi=narrative.page_text(run.market, hs, asof, ph))


def _overview(runs, pages, comps, ccfg, asof, ph) -> Overview:
    summ = [s for c in comps.values() if (s := comp_mod.summary(c, ccfg.composites[c.id], ccfg))]
    mk = []
    for r in runs:
        by = {h.key: h for h in pages[r.market].horizons}
        if {"short", "medium"} <= set(by):
            mk.append(MarketSummary(
                id=r.market, name_vi=ph["markets"][r.market]["name"], p_up_short=by["short"].p_up,
                p_up_medium=by["medium"].p_up, confidence_short=by["short"].confidence,
                confidence_medium=by["medium"].confidence, label=narrative.market_label(by["short"], ph),
                page=f"/{r.market}"))
    return Overview(asof=asof, composites=summ, markets=mk)


def build_files(asof, paths: Paths | None = None, runs=None, comps=None, config_dir=None) -> dict[str, bytes]:
    """Validated, gated content bytes keyed by logical name (overview, <market>)."""
    from ..models import spec as mspec

    paths = paths or Paths()
    asof = str(asof)[:10]
    specs = registry.load(config_dir)
    ccfg = comp_mod.load(config_dir, specs)
    comps = {c.id: c for c in (comps if comps is not None else comp_mod.compute(asof, paths, config_dir))}
    runs = runs if runs is not None else models.forecast_all(asof, paths)
    runs = [r for r in runs if r.horizons]
    if not runs:
        raise EconError("nothing to publish: no market produced a forecast (store empty?)")
    mcfg = mspec.load(config_dir, specs, set(ccfg.composites))
    ph = narrative.phrases()
    pages = {r.market: _market_page(r, asof, specs, ccfg, mcfg, comps, paths, ph) for r in runs}
    files = {"overview": _dump(_overview(runs, pages, comps, ccfg, asof, ph))}
    files.update({m: _dump(p) for m, p in pages.items()})
    bad = [w for b in files.values() for w in narrative.banned(b.decode("utf-8"), ph)]
    if bad:
        raise GateError(f"banned wording in narrative: {sorted(set(bad))}")
    limit = int(cfg("audit.site_json_kb", 200)) * 1024
    big = [f"{k} {len(b) // 1024}KB" for k, b in files.items() if len(b) > limit]
    if big:
        raise GateError(f"site JSON over budget {limit // 1024}KB: {', '.join(big)}")
    return files


def manifest_of(files: dict[str, bytes], asof, generated_at: str | None = None) -> Manifest:
    ent = []
    for name, b in sorted(files.items()):
        h = hashlib.sha256(b).hexdigest()
        ent.append(FileEntry(name=f"{name}.{h[:8]}.json", hash=h, bytes=len(b)))
    return Manifest(data_asof=str(asof)[:10], generated_at=generated_at or utcnow(), files=ent)


def _atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_files(files: dict[str, bytes], asof, site: Path, generated_at: str | None = None) -> Manifest:
    site = Path(site)
    site.mkdir(parents=True, exist_ok=True)
    man = manifest_of(files, asof, generated_at)
    for name, b in files.items():
        fe = next(f for f in man.files if f.name.startswith(name + "."))
        _atomic(site / fe.name, b)
    _atomic(site / "manifest.json", _dump(man))
    keep = {f.name for f in man.files}
    for old in site.iterdir():
        if HASHED.match(old.name) and old.name not in keep:
            old.unlink()
    return man


def build(asof, paths: Paths | None = None, runs=None, comps=None, write: bool = True, config_dir=None) -> Manifest:
    paths = paths or Paths()
    files = build_files(asof, paths, runs, comps, config_dir)
    if not write:
        return manifest_of(files, asof)
    man = write_files(files, asof, paths.site)
    problems = scan(paths.site, config_dir)
    if problems:
        raise GateError("license scan failed after write: " + "; ".join(problems[:5]))
    return man


def scan(site: Path, config_dir=None) -> list[str]:
    """License gate over files on disk: licenses re-derived from the registry, never trusted from the file."""
    specs = registry.load(config_dir)
    ccfg = comp_mod.load(config_dir, specs)
    lic = {i: s.license_class for i, s in specs.items()}
    lic.update({c: comp_mod.derived_license(cs, specs) for c, cs in ccfg.composites.items()})
    out: list[str] = []
    files = sorted(p for p in Path(site).glob("*.json") if p.name != "manifest.json")
    if not files:
        out.append(f"no site JSON in {site}")
    for p in files:
        js = json.loads(p.read_text(encoding="utf-8"))
        for s in js.get("series", []):
            real = lic.get(s["id"])
            if real is None:
                out.append(f"{p.name}: series {s['id']} unknown to registry")
            elif real == "internal" and (s.get("values") or s.get("dates")):
                out.append(f"{p.name}: internal series {s['id']} carries values")
            elif s.get("license") != real:
                out.append(f"{p.name}: series {s['id']} license {s.get('license')} != registry {real}")
        for c in js.get("composites", []):
            if lic.get(c["id"]) == "internal" and c.get("level") is not None:
                out.append(f"{p.name}: internal composite {c['id']} publishes a level")
    return out


def cmd_publish(args) -> Result:
    paths = Paths.from_args(args)
    asof = getattr(args, "asof", None) or today()
    if getattr(args, "scan", False):
        problems = scan(paths.site)
        head = f"license-scan {paths.site}: {len(problems)} violation(s)"
        return Result("\n".join([head, *problems[:38]]), data={"violations": problems}, code=2 if problems else 0)
    dry = bool(getattr(args, "dry_run", False))
    try:
        man = build(asof, paths, write=not dry)
    except GateError as e:
        return Result(f"publish gate FAILED: {e}", data={"error": str(e)}, code=2)
    lines = [f"publish asof {asof}: {len(man.files)} files{' (dry-run, nothing written)' if dry else ''} -> {paths.site}"]
    lines += [f"  {f.name:<34} {f.bytes:>7} B" for f in man.files]
    return Result("\n".join(lines[:40]), data=man.model_dump())
