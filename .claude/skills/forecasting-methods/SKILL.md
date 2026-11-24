---
name: forecasting-methods
description: Forecast evaluation and calibration standards - walk-forward, vintages/look-ahead, non-overlapping origins and n_eff, DM-HLN/Clark-West, Brier skill, ACI, Platt/beta, shrinkage, equal-weight ensembles, model cards, promotion gate.
user-invocable: false
---
# Forecasting methods

## 1. Set-up: what is being forecast
- Target per market x horizon: 1M (21 trading days), 12M, 5Y. Short/medium: P(return > 0) plus return
  percentiles (p10/p50/p90). Long: annualised expected-return range or scenario bands - **no P(up)**.
- Define the target exactly (total vs price return, currency, log vs simple) in the model card.
- Origin dates: month-end (or the publication schedule), fixed in config/models.yaml.

## 2. No look-ahead
- Use the data as known at the origin: ALFRED vintages where available; otherwise our own stored vintages
  (`econ-data`), otherwise apply a conservative publication lag from config/calendar.yaml.
- Standardise with expanding windows only. Fit hyper-parameters inside each training window.
- Truncation test for every feature: removing rows after the origin must not change the forecast.
- Survivorship: index constituents, delisted coins, discontinued series - note them in the card.

## 3. Walk-forward protocol
- Expanding window (default) or rolling (when regimes break), refit at each origin or every k origins.
- Minimum training span before the first OOS origin: 10 years monthly for macro/equities where history allows;
  crypto has short history -> label results "short sample".
- Overlapping targets (12M horizon, monthly origins) are autocorrelated: evaluate on **non-overlapping
  origins** (every h-th origin) and report **n_eff**; use overlapping only with HAC errors, clearly labelled.

## 4. Baselines (always reported)
- Random walk / zero-change for levels; historical mean drift for returns; **climatology** (base rate of
  up-moves in the training window) for P(up); unconditional quantiles for intervals.

## 5. Scores
| Output | Score | Notes |
|---|---|---|
| P(up) | Brier, log score; **Brier skill score** BSS = 1 - B/B_clim | reliability diagram (10 bins, >= 10 pts/bin) |
| Point | MAE / RMSE vs baseline ratio | report ratio < 1 means better |
| Interval | empirical coverage vs nominal, mean width, interval score | coverage meaningful only for n_eff >= 30 |
| Quantiles | pinball loss | per quantile |

## 6. Comparing models
- **Diebold-Mariano** with HAC variance (Newey-West, lag h-1) and the **Harvey-Leybourne-Newbold**
  small-sample correction; one-sided when testing "beats baseline".
- **Clark-West** when the model nests the baseline (DM is undersized there).
- Many models/markets: control the family-wise picture - report how many comparisons were made.
- Effect size matters more than p-values: report the loss ratio with a block-bootstrap CI.

## 7. Calibration
- Probabilities: **Platt** (logistic) or **beta calibration** fit on OOS predictions only. Isotonic only when
  OOS points > 500 (rare here).
- Intervals: **ACI** (adaptive conformal inference, Gibbs & Candes 2021) - updates the miscoverage level
  online, robust to drift; step gamma ~0.005-0.02. Split conformal assumes exchangeability (not true here).
- Shrink extreme probabilities towards climatology when n_eff is small: p* = w p + (1-w) p_clim.

## 8. Ensembles
- Equal weights until each member has >= 36 OOS points; after that, optional inverse-loss weights with
  shrinkage to equal. "Forecast combination puzzle": simple averages are hard to beat.

## 9. Confidence label (published)
- **High**: n_eff >= 30, beats baseline (DM/CW p < 0.05), calibrated (reliability slope 0.8-1.2).
- **Medium**: beats baseline in point estimate but not significant, or n_eff 15-30.
- **Low**: does not beat baseline, or n_eff < 15, or uncalibrated. Shown as "Thấp", with explanation.

## 10. Model card (docs/models/<id>.md)
Target and horizon · inputs (indicator IDs, license class) · training scheme · as-of handling · baselines ·
OOS results (n_eff, scores, tests, calibration) · known failure regimes · changes log · status
(challenger / champion / retired).

## 11. Promotion gate (monthly)
Challenger replaces champion only if: >= 36 OOS points, better loss with CI excluding 0 or DM p < 0.1,
calibration not worse, red-team pass (docs/risk/), Owner approval logged. Never promote on in-sample fit.

## 12. Common traps
- Tuning on the full sample, then "walk-forward" with fixed tuned params (leak).
- Using revised data (current vintage) for historical origins.
- Reporting overlapping-window accuracy as if independent.
- Choosing the evaluation period after seeing results.
- Treating 2-3 crypto cycles as a statistical sample.
