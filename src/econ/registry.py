"""Indicator registry: load/validate config/indicators.yaml against config/sources.yaml; `ind list|get`."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .common import CONFIG, EconError, Paths, Result, load_yaml, today

_RANK = {"open": 0, "attributed": 1, "internal": 2}


class IndicatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    name: str
    source: str
    series: str
    freq: Literal["D", "W", "M", "Q"]
    lag_days: int = Field(ge=0)
    transform: Literal["level", "diff", "log_diff", "yoy", "zscore"] = "level"
    unit: str = ""
    license_class: Literal["open", "attributed", "internal"]
    markets: list[Literal["global_macro", "us_equities", "gold", "oil"]] = Field(min_length=1)
    attribution: str = ""  # filled from the source entry


def load(config_dir=None) -> dict[str, IndicatorSpec]:
    """Load + validate. Raises EconError listing problems: unknown source, series not declared by the source,
    license weaker than the source's, duplicate (source, series)."""
    cfg = config_dir or CONFIG
    raw = load_yaml(cfg / "indicators.yaml").get("indicators") or {}
    srcs = load_yaml(cfg / "sources.yaml").get("sources") or {}
    out: dict[str, IndicatorSpec] = {}
    errs: list[str] = []
    seen: dict[tuple, str] = {}
    for iid, d in raw.items():
        try:
            spec = IndicatorSpec(id=iid, **d)
        except (ValidationError, TypeError) as e:
            errs.append(f"{iid}: {str(e).splitlines()[0]}")
            continue
        s = srcs.get(spec.source)
        if s is None:
            errs.append(f"{iid}: unknown source '{spec.source}'")
            continue
        if spec.series not in (s.get("series") or []):
            errs.append(f"{iid}: series '{spec.series}' not declared under sources.{spec.source}.series")
        if _RANK[spec.license_class] < _RANK[s.get("license_class", "internal")]:
            errs.append(f"{iid}: license {spec.license_class} weaker than source {s.get('license_class')}")
        key = (spec.source, spec.series)
        if key in seen:
            errs.append(f"{iid}: duplicates {seen[key]}")
        seen[key] = iid
        spec.attribution = s.get("attribution", "") or ""
        out[iid] = spec
    if errs:
        raise EconError("config/indicators.yaml invalid:\n  " + "\n  ".join(errs[:10]))
    return out


# ------------------------------------------------------------------ CLI
def cmd_ind_list(args) -> Result:
    specs = load()
    rows = [s for s in specs.values()
            if (not getattr(args, "market", None) or args.market in s.markets)
            and (not getattr(args, "license", None) or s.license_class == args.license)]
    lines = [f"{len(rows)}/{len(specs)} indicators", f"{'id':<10} {'src':<8} {'series':<13} f lag lic        tf"]
    for s in rows[:34]:
        lines.append(f"{s.id:<10} {s.source[:8]:<8} {s.series:<13} {s.freq} {s.lag_days:>3} "
                     f"{s.license_class:<10} {s.transform}")
    if len(rows) > 34:
        lines.append(f"... +{len(rows) - 34} more")
    return Result("\n".join(lines), data=[s.model_dump() for s in rows])


def cmd_ind_get(args) -> Result:
    from . import store

    spec = load().get(args.id)
    if spec is None:
        raise EconError(f"unknown indicator '{args.id}' (try: ind list)")
    asof = getattr(args, "asof", None) or today()
    ser = store.read(args.id, asof, Paths.from_args(args), spec=spec)
    lines = [f"{spec.id}: {spec.name} [{spec.source}:{spec.series} {spec.freq} lag {spec.lag_days}d "
             f"{spec.license_class} -> {spec.transform}]", f"markets: {', '.join(spec.markets)}"]
    if not ser.dates:
        lines.append(f"no data in store as of {asof}")
    else:
        n = max(1, min(int(args.tail), 20))
        lines.append(f"asof {ser.asof}{' STALE' if ser.stale else ''}, n={len(ser.dates)}; last {n}:")
        lines += [f"  {d}  {v}" for d, v in list(zip(ser.dates, ser.values))[-n:]]
    return Result("\n".join(lines[:40]), data=ser.model_dump())
