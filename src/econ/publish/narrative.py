"""Deterministic Vietnamese narrative: rulebook/phrases.vi.yaml templates + model numbers. No LLM, no randomness.

Every number and every band/direction word is derived from the HorizonForecast itself (p_up, return_band, driver
contribution signs), and the band is picked from the *rounded* percent that is printed, so text can never
contradict the published probability.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..common import ROOT, load_yaml
from ..schemas import HorizonForecast

PHRASES = ROOT / "rulebook" / "phrases.vi.yaml"
_SLOT = re.compile(r"\{(\w+)\}")
BAND_EDGES = ((85, "b85_100"), (70, "b70_85"), (55, "b55_70"), (45, "b45_55"), (30, "b30_45"), (15, "b15_30"))


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    return load_yaml(path)


def phrases(path=None) -> dict:
    return _load(str(path or PHRASES))


def band(p_up: float) -> str:
    """Band of the printed (rounded) percent, lower bound inclusive."""
    pct = round(p_up * 100)
    for edge, key in BAND_EDGES:
        if pct >= edge:
            return key
    return "b0_15"


def pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def ret(x: float) -> str:
    return f"{x * 100:+.1f}%"


def fill(template: str, **slots) -> str:
    need = set(_SLOT.findall(template))
    if need - set(slots):
        raise KeyError(f"unfilled slots {sorted(need - set(slots))} in '{template[:40]}'")
    return _SLOT.sub(lambda m: str(slots[m.group(1)]), template)


def _driver_sentence(h: HorizonForecast, ph: dict) -> tuple[str, str]:
    """(sentence, driver label) from the largest-|contribution| non-neutral driver."""
    for d in sorted(h.drivers, key=lambda d: -abs(d.contribution)):
        if d.direction != "neutral":
            label = d.label_vi or d.indicator
            return fill(ph["driver"][d.direction], driver=label), label
    return ph["driver"]["none"], "các yếu tố hiện tại"


def horizon_text(market: str, h: HorizonForecast, asof: str, ph: dict | None = None) -> str:
    ph = ph or phrases()
    common = dict(market_name=ph["markets"][market]["name"], horizon=ph["horizons"][h.key],
                  asof=asof, confidence_vi=ph["confidence_vi"][h.confidence])
    drv, label = _driver_sentence(h, ph)
    b = h.return_band
    if h.key == "short":
        parts = [fill(ph["short"]["headline"], prob_phrase=ph["prob_phrase"][band(h.p_up)], p_up=pct(h.p_up), **common),
                 ph["short"]["confidence_note"][h.confidence],
                 fill(ph["short"]["baseline_note"], n_eff=h.skill.n_eff), drv]
    else:
        sk = "pos" if round(b.p50 * 100, 1) >= 0 else "neg"
        parts = [fill(ph["medium"]["headline"], p10=ret(b.p10), p50=ret(b.p50), p90=ret(b.p90), **common),
                 fill(ph["medium"]["skew"][sk], p50=ret(b.p50)),
                 fill(ph["medium"]["scenario"], p10=ret(b.p10), p90=ret(b.p90), driver=label), drv,
                 ph["short"]["confidence_note"][h.confidence]]
    return " ".join(parts)


def page_text(market: str, horizons: list[HorizonForecast], asof: str, ph: dict | None = None) -> str:
    ph = ph or phrases()
    return " ".join([*(h.narrative_vi for h in horizons), fill(ph["data_asof"], asof=asof),
                     ph["footer"]["fred"], ph["disclaimer"]])


def market_label(h: HorizonForecast, ph: dict | None = None) -> str:
    ph = ph or phrases()
    return ph["prob_phrase"][band(h.p_up)]


def banned(text: str, ph: dict | None = None) -> list[str]:
    ph = ph or phrases()
    low = text.lower()
    return [w for w in ph["_meta"]["banned_words"] if w.lower() in low]
