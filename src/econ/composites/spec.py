"""config/composites.yaml -> validated CompositeSpec objects (members checked against the indicator registry)."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..common import CONFIG, EconError, load_yaml

_RANK = {"open": 0, "attributed": 1, "internal": 2}
_TF = re.compile(r"^(level|chg_(\d+)m|pct_(\d+)m)$")


class MemberSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sign: Literal[1, -1]
    weight: float = Field(gt=0)
    agg: Literal["last", "mean"] = "last"
    transform: str = "level"

    @field_validator("transform")
    @classmethod
    def _tf(cls, v: str) -> str:
        m = _TF.match(v)
        if not m or (m.group(2) or m.group(3) or "1") == "0":
            raise ValueError(f"transform must be level | chg_<N>m | pct_<N>m (N>0), got '{v}'")
        return v


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zscore_min_periods: int = Field(36, ge=6)
    clip: float = Field(4.0, gt=0)
    percentile_min_periods: int = Field(36, ge=6)
    min_coverage: float = Field(0.6, gt=0, le=1)
    max_ffill: dict[Literal["D", "W", "M", "Q"], int] = Field(default_factory=lambda: {"D": 1, "W": 1, "M": 2, "Q": 4})
    label_bands: list[float] = Field(default_factory=lambda: [20, 40, 60, 80])


class CompositeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    version: int = Field(1, ge=1)
    name: str
    name_vi: str
    orientation: str
    license: Literal["open", "attributed", "internal"]
    labels_vi: list[str]
    members: dict[str, MemberSpec] = Field(min_length=1)
    min_coverage: float | None = Field(None, gt=0, le=1)  # overrides defaults.min_coverage

    @property
    def total_weight(self) -> float:
        return sum(m.weight for m in self.members.values())


class CompositesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    defaults: Defaults = Field(default_factory=Defaults)
    composites: dict[str, CompositeSpec] = Field(min_length=1)


def derived_license(comp: CompositeSpec, specs: dict) -> str:
    """Most restrictive member license (internal member => composite internal => level hidden on the site)."""
    lic = max((specs[m].license_class for m in comp.members), key=_RANK.__getitem__)
    return lic


def load(config_dir=None, specs: dict | None = None) -> CompositesConfig:
    """Load + validate. Errors: schema, unknown member indicator, label count != bands+1, unsorted bands,
    declared license != derived license."""
    cfg_dir = config_dir or CONFIG
    raw = load_yaml(cfg_dir / "composites.yaml")
    try:
        for cid, c in (raw.get("composites") or {}).items():
            if isinstance(c, dict):
                c["id"] = cid
        cfg = CompositesConfig(**raw)
    except (ValidationError, TypeError) as e:
        lines = str(e).splitlines()
        raise EconError("config/composites.yaml invalid: " + " | ".join(lines[:4])) from None
    if specs is None:
        from .. import registry

        specs = registry.load(config_dir)
    errs: list[str] = []
    bands = cfg.defaults.label_bands
    if bands != sorted(bands) or any(not 0 < b < 100 for b in bands):
        errs.append("defaults.label_bands must be ascending within (0, 100)")
    for cid, c in cfg.composites.items():
        unknown = [m for m in c.members if m not in specs]
        if unknown:
            errs.append(f"{cid}: unknown member indicator(s) {unknown}")
            continue
        if len(c.labels_vi) != len(bands) + 1:
            errs.append(f"{cid}: labels_vi needs {len(bands) + 1} entries (label_bands + 1)")
        lic = derived_license(c, specs)
        if c.license != lic:
            errs.append(f"{cid}: declared license '{c.license}' but members imply '{lic}'")
    if errs:
        raise EconError("config/composites.yaml invalid:\n  " + "\n  ".join(errs[:10]))
    return cfg
