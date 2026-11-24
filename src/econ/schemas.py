"""Data contracts (pydantic v2): pipeline internals + published site JSON + ledger lines.

Contract change order: schema + SCHEMA_VERSION bump -> publisher -> generated TS types -> UI -> tests.
Additive = minor bump; rename/remove = major bump + migration note in the ADR.

Two families:
- internal interchange (IndicatorSeries, CompositeSeries): may carry internal-license values, never published;
- site-facing (Site*, Manifest, Overview, MarketPage, Health): internal-license values are NOT representable.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"

License = Literal["open", "attributed", "internal"]
Confidence = Literal["High", "Med", "Low"]
Direction = Literal["up", "down", "neutral"]
HorizonKey = Literal["short", "medium"]  # short = 1-3m, medium = 6-12m (long = scenario bands, later)
MarketId = Literal["global_macro", "us_equities", "gold", "oil"]
Date = str  # ISO yyyy-mm-dd (UTC); datetimes are ISO-8601 with Z


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ internal interchange
class IndicatorSeries(_M):
    """Output of connectors/transforms; input of composites/models. Internal-license values allowed here."""

    id: str
    name: str = ""
    unit: str = ""
    freq: Literal["D", "W", "M", "Q"] = "D"
    source: str
    license: License
    attribution: str = ""
    asof: Date  # last observation date
    stale: bool = False
    dates: list[Date] = Field(default_factory=list)
    values: list[float | None] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aligned(self):
        if len(self.dates) != len(self.values):
            raise ValueError("dates and values must have equal length")
        return self


class CompositeSeries(_M):
    id: str
    name: str = ""
    members: list[str]
    weights: dict[str, float] = Field(default_factory=dict)  # weights actually used (after coverage renorm)
    coverage: float = Field(ge=0, le=1)
    license: License  # most restrictive member license
    asof: Date
    dates: list[Date] = Field(default_factory=list)
    levels: list[float | None] = Field(default_factory=list)  # z-score style level
    percentiles: list[float | None] = Field(default_factory=list)  # expanding, as-of safe, 0-100

    @model_validator(mode="after")
    def _aligned(self):
        if not (len(self.dates) == len(self.levels) == len(self.percentiles)):
            raise ValueError("dates, levels, percentiles must have equal length")
        return self


# ------------------------------------------------------------------ site: shared
class SiteSeries(_M):
    """Chart series safe for publication. internal license => values/dates forbidden (empty)."""

    id: str
    name_vi: str
    unit: str = ""
    license: License
    attribution: str = ""
    stale: bool = False
    dates: list[Date] = Field(default_factory=list)
    values: list[float | None] = Field(default_factory=list)

    @model_validator(mode="after")
    def _license_gate(self):
        if self.license == "internal" and (self.dates or self.values):
            raise ValueError(f"series {self.id}: internal-license values must not be published")
        if len(self.dates) != len(self.values):
            raise ValueError("dates and values must have equal length")
        return self


class FileEntry(_M):
    name: str  # e.g. overview.ab12cd34.json
    hash: str  # sha256 hex (first 16+ chars of content hash also embedded in name)
    bytes: int = Field(ge=0)


class Manifest(_M):
    schema_version: str = SCHEMA_VERSION
    data_asof: Date
    generated_at: str
    files: list[FileEntry]


# ------------------------------------------------------------------ site: overview
class CompositeSummary(_M):
    id: str
    name_vi: str
    license: License
    level: float | None = None  # None required when license == internal
    percentile: float = Field(ge=0, le=100)
    label: str  # VI band label, e.g. "Thận trọng"
    asof: Date

    @model_validator(mode="after")
    def _license_gate(self):
        if self.license == "internal" and self.level is not None:
            raise ValueError(f"composite {self.id}: internal-license level must not be published")
        return self


class MarketSummary(_M):
    id: MarketId
    name_vi: str
    p_up_short: float = Field(ge=0, le=1)
    p_up_medium: float = Field(ge=0, le=1)
    confidence_short: Confidence
    confidence_medium: Confidence
    label: str
    page: str  # route, e.g. "/gold"


class Overview(_M):
    schema_version: str = SCHEMA_VERSION
    asof: Date
    composites: list[CompositeSummary]
    markets: list[MarketSummary]
    disclaimer_vi: str = "Không phải lời khuyên đầu tư"


# ------------------------------------------------------------------ site: market page
class ReturnBand(_M):
    p10: float
    p50: float
    p90: float

    @model_validator(mode="after")
    def _ordered(self):
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError("return band must satisfy p10 <= p50 <= p90")
        return self


class BaselineSkill(_M):
    """Skill = 1 - Brier_model / Brier_baseline (>0 beats the baseline)."""

    vs_random_walk: float
    vs_climatology: float
    n_eff: int = Field(ge=0)
    beats_baselines: bool


class Driver(_M):
    indicator: str  # indicator or composite id
    label_vi: str = ""
    contribution: float  # signed, from the model's actual contributions
    direction: Direction


class HorizonForecast(_M):
    key: HorizonKey
    window: Literal["1-3m", "6-12m"]
    p_up: float = Field(ge=0, le=1)
    return_band: ReturnBand
    confidence: Confidence
    skill: BaselineSkill
    drivers: list[Driver] = Field(default_factory=list)
    narrative_vi: str

    @model_validator(mode="after")
    def _charter(self):
        if not self.skill.beats_baselines and self.confidence != "Low":
            raise ValueError("a model that does not beat its baselines must ship with confidence Low")
        if (self.key, self.window) not in (("short", "1-3m"), ("medium", "6-12m")):
            raise ValueError("key/window mismatch")
        return self


class MarketPage(_M):
    schema_version: str = SCHEMA_VERSION
    market: MarketId
    title_vi: str
    asof: Date
    horizons: list[HorizonForecast]
    series: list[SiteSeries] = Field(default_factory=list)
    narrative_vi: str
    disclaimer_vi: str = "Không phải lời khuyên đầu tư"


# ------------------------------------------------------------------ ledger + health
class ForecastRecord(_M):
    """One JSONL line in ledger/forecasts/*.jsonl (append-only). Outcome fields are filled by a score
    record appended later (never by rewriting): the scored record repeats `id` with `scored_at` set."""

    id: str  # f"{market}|{horizon}|{origin}|{model_id}"
    origin: Date
    horizon: str  # "3m", "12m", ...
    market: MarketId
    model_id: str
    p_up: float = Field(ge=0, le=1)
    quantiles: ReturnBand
    baseline_rw_p_up: float = Field(ge=0, le=1)
    baseline_clim_p_up: float = Field(ge=0, le=1)
    features_hash: str
    data_asof: dict[str, Date]  # source id -> last vintage date used
    created_at: str
    # outcome (null until scored)
    scored_at: str | None = None
    realized_return: float | None = None
    realized_up: bool | None = None
    brier: float | None = None
    brier_rw: float | None = None
    brier_clim: float | None = None


class SourceHealth(_M):
    ok: bool
    status: Literal["ok", "late", "degraded", "failed"]
    last_obs: Date | None = None
    lag_days: int | None = None
    fails: int = 0
    note: str = ""


class Health(_M):
    schema_version: str = SCHEMA_VERSION
    asof: Date
    last_run: str
    sources: dict[str, SourceHealth]


# ------------------------------------------------------------------ export
SITE_MODELS = {"manifest": Manifest, "overview": Overview, "market": MarketPage, "health": Health}
ALL_MODELS = {**SITE_MODELS, "forecast_record": ForecastRecord, "indicator_series": IndicatorSeries,
              "composite_series": CompositeSeries}


def json_schema() -> dict[str, dict]:
    """name -> JSON Schema (draft 2020-12) for every contract; feeds json-schema-to-typescript."""
    return {k: m.model_json_schema() for k, m in ALL_MODELS.items()}
