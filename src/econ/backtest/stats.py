"""Forecast scores and tests: Brier / skill, pinball, DM-HLN (HAC), Clark-West, calibration, confidence label.

Conventions: loss differentials d = loss_model - loss_baseline (negative = model better); p-values one-sided
for "model beats baseline". Inputs are non-overlapping origins, so the HAC lag (h-1) is in evaluation steps.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as st

NAN = float("nan")


def brier(p, y) -> np.ndarray:
    return (np.asarray(p, float) - np.asarray(y, float)) ** 2


def skill(loss_model, loss_base) -> float:
    """1 - mean(loss_model) / mean(loss_base); > 0 beats the baseline. NaN when undefined."""
    lm, lb = np.mean(loss_model) if len(loss_model) else NAN, np.mean(loss_base) if len(loss_base) else NAN
    return NAN if not np.isfinite(lb) or lb <= 0 else float(1.0 - lm / lb)


def pinball(y, q, tau: float) -> np.ndarray:
    u = np.asarray(y, float) - np.asarray(q, float)
    return np.maximum(tau * u, (tau - 1.0) * u)


def _hac_var(x: np.ndarray, lag: int) -> float:
    """Newey-West long-run variance of x (Bartlett weights)."""
    x = x - x.mean()
    n = len(x)
    v = float(x @ x) / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2.0 * (1 - k / (lag + 1)) * float(x[k:] @ x[:-k]) / n
    return v


def dm_hln(d, h: int = 1) -> tuple[float, float]:
    """Diebold-Mariano with HAC variance (lag h-1) and the Harvey-Leybourne-Newbold correction.
    Returns (statistic, one-sided p for mean(d) < 0, i.e. model better). NaN when n < 3 or var = 0."""
    d = np.asarray(d, float)
    n = len(d)
    if n < 3:
        return NAN, NAN
    v = _hac_var(d, h - 1)
    if v <= 0:
        return NAN, NAN
    dm = d.mean() / math.sqrt(v / n)
    corr = math.sqrt(max((n + 1 - 2 * h + h * (h - 1) / n) / n, 1e-12))
    stat = dm * corr
    return float(stat), float(st.t.cdf(stat, df=n - 1))


def clark_west(y, f_big, f_small, h: int = 1) -> tuple[float, float]:
    """Clark-West (2007) MSPE-adjusted test, big model nests the small one (here: logit vs climatology).
    Returns (t statistic, one-sided p for the big model being better)."""
    y, fb, fs = (np.asarray(a, float) for a in (y, f_big, f_small))
    n = len(y)
    if n < 3:
        return NAN, NAN
    f = (y - fs) ** 2 - ((y - fb) ** 2 - (fs - fb) ** 2)
    v = _hac_var(f, h - 1)
    if v <= 0:
        return NAN, NAN
    t = f.mean() / math.sqrt(v / n)
    return float(t), float(1.0 - st.t.cdf(t, df=n - 1))


def calibration(p, y, bins: int = 10) -> dict:
    """Reliability slope (logistic regression of y on logit p; 1 = calibrated) and ECE over equal-width bins."""
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    y = np.asarray(y, float)
    out = {"slope": NAN, "ece": NAN}
    if len(p) < 5:
        return out
    idx = np.minimum((p * bins).astype(int), bins - 1)
    out["ece"] = float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).sum()
                           for b in range(bins) if (idx == b).any()) / len(p))
    if 0 < y.mean() < 1 and np.std(p) > 1e-9:
        from ..models.fit import logit_ridge

        _, b = logit_ridge(np.log(p / (1 - p))[:, None], y, l2=1e-6)
        out["slope"] = float(b[0])
    return out


def coverage(y, lo, hi) -> float:
    y = np.asarray(y, float)
    return NAN if not len(y) else float(np.mean((y >= np.asarray(lo)) & (y <= np.asarray(hi))))


def confidence(m: dict, rule, medium: bool = False) -> tuple[str, bool]:
    """(label, beats_baselines) from OOS metrics `m`. Low unless the model beats BOTH baselines (Brier skill
    > 0; medium also needs pinball skill > 0 vs climatology) and n_eff >= rule.low_below_n_eff.
    High needs n_eff >= high_min_n_eff, DM-HLN and Clark-West p < high_max_p and slope within high_slope."""
    ok = lambda x: x is not None and np.isfinite(x)  # noqa: E731
    beats = ok(m.get("bss_rw")) and ok(m.get("bss_clim")) and m["bss_rw"] > 0 and m["bss_clim"] > 0
    if medium:
        beats = beats and ok(m.get("pinball_skill_clim")) and m["pinball_skill_clim"] > 0
    if not beats or m.get("n_eff", 0) < rule.low_below_n_eff:
        return "Low", bool(beats)
    lo, hi = rule.high_slope
    high = (m["n_eff"] >= rule.high_min_n_eff and ok(m.get("dm_p_rw")) and m["dm_p_rw"] < rule.high_max_p
            and ok(m.get("cw_p_clim")) and m["cw_p_clim"] < rule.high_max_p
            and ok(m.get("calib_slope")) and lo <= m["calib_slope"] <= hi)
    return ("High" if high else "Med"), True
