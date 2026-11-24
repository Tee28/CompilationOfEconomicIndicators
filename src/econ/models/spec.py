"""config/models.yaml -> validated ModelsConfig (targets, horizons, pinned params, model families)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..common import CONFIG, EconError, load_yaml

Market = Literal["global_macro", "us_equities", "gold", "oil"]


class _C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceRule(_C):
    low_below_n_eff: int = 15
    high_min_n_eff: int = 30
    high_max_p: float = 0.05
    high_slope: tuple[float, float] = (0.8, 1.2)


class Defaults(_C):
    origin: str = "month_end"
    seed: int = 20261124
    min_train_months: int = Field(120, ge=12)
    min_train_floor: int = Field(36, ge=12)
    holdout_years: int = Field(5, ge=1)
    scheme: Literal["expanding"] = "expanding"
    evaluation: Literal["non_overlapping"] = "non_overlapping"
    ensemble: str = "equal_weight"
    calibration: str = "none_yet"
    confidence: ConfidenceRule = Field(default_factory=ConfidenceRule)


class HorizonSpec(_C):
    months: int = Field(ge=1)
    window: Literal["1-3m", "6-12m"]
    l2: float = Field(gt=0)


class TargetSpec(_C):
    indicator: str
    note: str = ""


class ModelFamily(_C):
    version: int = Field(1, ge=1)
    card: str
    status: Literal["challenger", "champion", "retired"] = "challenger"
    markets: list[Market] = Field(min_length=1)
    horizons: list[Literal["short", "medium"]] = Field(min_length=1)
    features: list[str] = Field(min_length=1)


class ModelsConfig(_C):
    version: int = 1
    defaults: Defaults = Field(default_factory=Defaults)
    horizons: dict[Literal["short", "medium"], HorizonSpec]
    baselines: list[str] = Field(default_factory=lambda: ["random_walk", "climatology"])
    targets: dict[Market, TargetSpec]
    models: dict[str, ModelFamily] = Field(min_length=1)

    def model_id(self, family: str, market: str, horizon: str) -> str:
        return f"{market}.{horizon}.{family}.v{self.models[family].version}"

    def family_for(self, market: str) -> str:
        """First non-retired family serving `market` (v1: one family, equal-weight ensembles come later)."""
        for name, f in self.models.items():
            if market in f.markets and f.status != "retired":
                return name
        raise EconError(f"no model configured for market '{market}'")


def load(config_dir=None, specs: dict | None = None, composite_ids=None) -> ModelsConfig:
    """Load + validate; target indicators must exist in the registry, features must be composite ids."""
    raw = load_yaml((config_dir or CONFIG) / "models.yaml")
    try:
        cfg = ModelsConfig(**raw)
    except (ValidationError, TypeError) as e:
        raise EconError("config/models.yaml invalid: " + " | ".join(str(e).splitlines()[:4])) from None
    errs = []
    if specs is not None:
        errs += [f"target {m}: unknown indicator '{t.indicator}'" for m, t in cfg.targets.items()
                 if t.indicator not in specs]
    if composite_ids is not None:
        for name, f in cfg.models.items():
            errs += [f"{name}: unknown composite feature '{x}'" for x in f.features if x not in composite_ids]
    for name, f in cfg.models.items():
        errs += [f"{name}: market {m} has no target" for m in f.markets if m not in cfg.targets]
        errs += [f"{name}: horizon {h} not configured" for h in f.horizons if h not in cfg.horizons]
    if errs:
        raise EconError("config/models.yaml invalid:\n  " + "\n  ".join(errs[:10]))
    return cfg
