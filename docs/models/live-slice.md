# Model card: live-slice (`composite_ridge` v1)

Status: **challenger** (no champion yet; promotion only via the monthly gate + Owner approval).
Config: `config/models.yaml` (all parameters pinned a priori). Engine: `src/econ/models/`, `src/econ/backtest/`.
Contract: `schemas.ForecastRecord` / `HorizonForecast` (ADR 0001). Model ids: `<market>.<horizon>.composite_ridge.v1`.

## Targets and horizons
| Market | Target indicator | Licence | Note |
|---|---|---|---|
| global_macro | `indpro` | attributed | proxy: US industrial production (no global aggregate yet) |
| us_equities | `sp500` | internal | S&P 500 price index (FRED daily, ~10y history) - price return, not total return |
| gold | `gold_pink` | attributed | World Bank Pink Sheet monthly average |
| oil | `oil_pink` | attributed | World Bank Pink Sheet monthly crude average (WTI is internal, not used as target) |

Target = log change of the target series from the anchor (latest observation known at the origin) to the
observation h months later, in USD, price only.

| Horizon key | h | Window | Headline output | l2 |
|---|---|---|---|---|
| short | 3m | 1-3m | P(up) from the L2 logistic + p10/p50/p90 band | 10 |
| medium | 12m | 6-12m | p10/p50/p90 return band (ridge mean + training-residual quantiles); P(up) derived from the same predictive distribution, secondary | 30 |

No long (5Y) horizon in v1. The contract only admits windows 1-3m and 6-12m, so a point P(up) can never be
published for a long horizon (test `test_no_point_p_up_beyond_medium_window`). A future 5Y model must publish
expected-return ranges / scenario bands only.

## Features
Composite levels at the origin from `config/composites.yaml`: `growth`, `inflation_policy`,
`financial_conditions` (missing -> 0, i.e. the composite's long-run mean). `financial_conditions` is internal
class (VIX, HY OAS, Baa spread): feeds the model, its level is never shown on the site. Drivers =
coefficient x feature value at the origin (log-odds for short, log-return for medium), sorted by |contribution|,
so the narrative cannot contradict the published number.

## Fits
Pure numpy, deterministic (no randomness; seed 20261124 pinned for future use). Short: L2 logistic (Newton),
intercept unpenalised. Medium: ridge. Penalties are round a-priori values, never tuned on data.

## Baselines (always reported)
- Random walk: P(up) = 0.5, zero drift +- training sd.
- Climatology: base rate of up-moves in the training window, unconditional training quantiles for the band.

## As-of discipline (no look-ahead)
- Features: composite history is real-time - grid date T uses only stored vintages with known_at <= T
  (`store.read_vintages`), publication lags from `config/indicators.yaml` (e.g. CPI 45d, INDPRO 47d, Pink Sheet 35d).
- Labels: a training label for origin s is used at origin t only if the target observation was known at t
  (vintage + lag), valued at the vintage known at t.
- Standardisation: expanding z-scores only.
- Tests: truncation (rows after the origin removed -> identical records), live forecast == later backtest
  prediction for that origin, training never sees unknown labels, vintage-aware labels.

## Walk-forward protocol
- Expanding window, refit at every month-end origin.
- Minimum training: 120 labelled origins when history allows 120 + 60 (holdout); else floor 36 and the run is
  labelled **short sample**.
- Evaluation on **non-overlapping origins** only: origins whose calendar month index % h == 0 (stable as data
  grows). n_eff = number of those origins with realised labels.
- **Holdout**: the last 5 years before the as-of date are reported as a separate slice and are locked from any
  tuning; changing a parameter after seeing results requires a new version + logged decision.

## Scores and tests
Brier, Brier skill vs RW and vs climatology, pinball loss (p10/p50/p90) and pinball skill vs climatology,
DM-HLN (HAC, lag h-1, one-sided) vs RW, Clark-West vs climatology (nested), reliability slope and ECE.
Calibration: none in v1; Platt on OOS predictions once n_eff >= 30. Ensemble: n/a (single family; equal
weights when members are added, until 36 OOS points each).

## Confidence label (published)
- **Low** unless the model beats BOTH baselines (BSS vs RW > 0 and vs climatology > 0; medium also needs pinball
  skill vs climatology > 0) and n_eff >= 15. The schema rejects any non-Low label when `beats_baselines` is false.
- **High**: n_eff >= 30, DM-HLN vs RW and Clark-West vs climatology both p < 0.05, reliability slope in [0.8, 1.2].
- **Med**: otherwise.

## OOS results
Pending the first CI run on the `econ-data` store (`econ forecast` writes the per-market report with n_eff,
BSS, pinball skill, p-values, holdout slice). Expectation at v1: n_eff for 12m is small (one origin per year),
so medium labels will be Low for most markets.

## Known limits / failure regimes
- `sp500` on FRED has only ~10y of daily history -> min-train floor applies, **short sample**, 12m n_eff in
  single digits; us_equities labels Low by construction until history is extended.
- `hy_oas` on FRED has ~3y of history: absent from `financial_conditions` for most of the grid (coverage
  renormalisation); its weight in early history is effectively zero.
- `global_macro` target is a US proxy (INDPRO), not global activity.
- Pink Sheet targets are monthly averages (smoother than end-of-month prices; slight autocorrelation).
- Price return only (no dividends/carry). Regime breaks (2008, 2020, 2022 inflation) can dominate small samples.

## Changes log
- v1 (2026-11-24): initial live slice (T005).
