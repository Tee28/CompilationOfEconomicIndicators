"""Expanding walk-forward with as-of labels, baselines, non-overlapping evaluation and the live forecast.

At every origin t: train on labels known at t (target.labels_at(t)), refit, predict. Evaluation keeps origins
whose calendar month index % h == 0 (stable as data grows) -> n_eff. Parameters are pinned in config (never
tuned); the last `holdout_years` are reported as a separate slice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import fit
from . import stats

TAUS = (0.1, 0.5, 0.9)
Z90 = 1.2815515655446004


def predict(Xtr, ytr, x, l2: float, medium: bool) -> dict:
    """Model + baselines for one origin. Short: P(up) from the ridge-logit; medium: P(up) from the predictive
    distribution ridge mean + training residuals (consistent with the band). Band = ridge mean + residual
    quantiles for both horizons. `contrib` = coef x feature value (log-odds short, log-return medium)."""
    Xtr, ytr, x = np.asarray(Xtr, float), np.asarray(ytr, float), np.asarray(x, float)
    up = (ytr > 0).astype(float)
    a_r, b_r = fit.ridge(Xtr, ytr, l2)
    resid = ytr - (a_r + Xtr @ b_r)
    mu = a_r + x @ b_r
    q = np.sort(mu + np.quantile(resid, TAUS))
    if medium:
        p = (np.sum(resid > -mu) + 1.0) / (len(resid) + 2.0)
        contrib = b_r * x
    else:
        a_l, b_l = fit.logit_ridge(Xtr, up, l2)
        p = float(fit.sigmoid(a_l + x @ b_l))
        contrib = b_l * x
    sd0 = float(np.sqrt(np.mean(ytr ** 2)))  # zero-drift random walk scale
    qc = np.quantile(ytr, TAUS)
    return {"p": float(p), "q10": float(q[0]), "q50": float(q[1]), "q90": float(q[2]),
            "p_clim": float(up.mean()), "qc10": float(qc[0]), "qc50": float(qc[1]), "qc90": float(qc[2]),
            "p_rw": 0.5, "qr10": -Z90 * sd0, "qr50": 0.0, "qr90": Z90 * sd0, "contrib": contrib,
            "n_train": int(len(ytr))}


def evaluate(df: pd.DataFrame) -> dict:
    """Scores on (non-overlapping) OOS rows with columns y, p, p_clim, p_rw, q*/qc*/qr*."""
    n = int(len(df))
    m = {"n_eff": n}
    if n == 0:
        return m
    y, up = df["y"].to_numpy(), (df["y"].to_numpy() > 0).astype(float)
    bm, bc, br = stats.brier(df["p"], up), stats.brier(df["p_clim"], up), stats.brier(df["p_rw"], up)
    pin = {k: np.mean([stats.pinball(y, df[f"{k}{int(t * 100)}"], t).mean() for t in TAUS])
           for k in ("q", "qc", "qr")}
    cal = stats.calibration(df["p"], up)
    m.update(
        brier=float(bm.mean()), brier_clim=float(bc.mean()), brier_rw=float(br.mean()),
        bss_clim=stats.skill(bm, bc), bss_rw=stats.skill(bm, br),
        dm_p_rw=stats.dm_hln(bm - br, 1)[1], dm_p_clim=stats.dm_hln(bm - bc, 1)[1],
        cw_p_clim=stats.clark_west(up, df["p"], df["p_clim"], 1)[1],
        pinball=float(pin["q"]), pinball_skill_clim=float(1 - pin["q"] / pin["qc"]) if pin["qc"] > 0 else np.nan,
        pinball_skill_rw=float(1 - pin["q"] / pin["qr"]) if pin["qr"] > 0 else np.nan,
        coverage80=stats.coverage(y, df["q10"], df["q90"]), calib_slope=cal["slope"], ece=cal["ece"],
        base_rate=float(up.mean()), first=str(df.index[0].date()), last=str(df.index[-1].date()))
    return m


def walk_forward(X: pd.DataFrame, target, live, h: int, l2: float, d, medium: bool = False) -> dict:
    """X: origins x features (as-of levels); target: data.Target; live: as-of origin (last row of X).
    Returns {metrics, holdout, live, oos, need, short_sample, features}."""
    live = pd.Timestamp(live)
    X = X[X.notna().any(axis=1)]
    X = X[X.index <= live].fillna(0.0)
    target.prepare(X.index)
    final = target.labels_at(live)
    hold = d.holdout_years * 12
    need = d.min_train_months if len(final) >= d.min_train_months + hold else d.min_train_floor
    rows = []
    for t in X.index[X.index < live]:
        if t not in final.index:
            continue
        tr = target.labels_at(t)
        if len(tr) < need:
            continue
        pr = predict(X.loc[tr.index].to_numpy(), tr["y"].to_numpy(), X.loc[t].to_numpy(), l2, medium)
        pr.pop("contrib")
        rows.append({"origin": t, "y": float(final.at[t, "y"]), **pr})
    oos = pd.DataFrame(rows).set_index("origin") if rows else pd.DataFrame()
    ne = oos[[(t.year * 12 + t.month) % h == 0 for t in oos.index]] if len(oos) else oos
    cut = live - pd.DateOffset(years=d.holdout_years)
    out = {"metrics": evaluate(ne), "holdout": evaluate(ne[ne.index > cut]) if len(ne) else {"n_eff": 0},
           "holdout_start": str(cut.date()), "oos": oos, "need": need,
           "short_sample": need < d.min_train_months, "features": list(X.columns), "live": None}
    if live in X.index and len(final) >= d.min_train_floor:
        out["live"] = predict(X.loc[final.index].to_numpy(), final["y"].to_numpy(), X.loc[live].to_numpy(),
                              l2, medium)
        out["live"]["x"] = X.loc[live].to_numpy()
    return out
