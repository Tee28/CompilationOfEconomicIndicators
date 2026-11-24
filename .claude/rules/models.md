---
paths:
  - "src/econ/models/**"
  - "src/econ/backtest/**"
  - "src/econ/composites/**"
  - "src/econ/ledger/**"
  - "config/models.yaml"
  - "config/composites.yaml"
  - "docs/models/**"
---
# Models, composites, backtests, ledger

- As-of correctness first: features use only data known at the origin (vintages + publication lags from
  config/calendar.yaml). Each feature gets a truncation test: drop rows after the origin -> identical output.
- Deterministic: fixed seeds, no wall-clock in model code (pass `asof` explicitly).
- Evaluation: non-overlapping origins, report n_eff; baselines always included; DM-HLN (HAC) / Clark-West;
  Brier skill vs climatology; reliability + interval coverage. See skill forecasting-methods.
- Composites: z-scores on expanding windows only (no full-sample standardisation), documented weights.
- Model ids are stable (`<market>.<horizon>.<name>.v<N>`); changing behaviour = new version + model card.
- Ledger lines are append-only JSONL; `ledger verify` fails on any edit. Only CI writes ledger/ -
  local runs use `--no-ledger`.
- Promotion (champion/challenger) needs a model card, a red-team review in docs/risk/ and Owner approval.
