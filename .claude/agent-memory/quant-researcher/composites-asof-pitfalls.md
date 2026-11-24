---
name: composites-asof-pitfalls
description: Data pitfalls found building the composites engine (T004) - vintage dedupe, lag alignment, short FRED histories
metadata:
  type: project
---

- store.read_frame keeps only the LATEST vintage per date. Building history from it makes every revised obs
  (payrolls revise ~2 months) disappear until its revision date -> history differs from real time. Use ALL
  vintages (store.read_vintages; composites.vintage_rows is now a thin alias) and sample "latest obs date known by T" per grid date.
  **Why:** first revision test failed at 2019-07 for exactly this. **How to apply:** models (T005) must build
  features through composites.frames / vintage_rows, never read_frame for history.
- Monthly obs are stored at period START (2026-10-01) + lag_days; transforms.resample labels by obs period,
  which is look-ahead for composites. Place values at known_at, then bucket to the grid.
- FRED HY OAS ~3y and SP500 ~10y of history: with 36m z warm-up, hy_oas is absent most of the time;
  financial_conditions runs on renormalised weights (coverage < 1). Check coverage before trusting it.
- Composite ids lowercase (matches indicators.yaml + site fixtures) although rules/registries.md says UPPER_SNAKE (note N002).
- Contract: HorizonForecast.p_up is REQUIRED for medium (6-12m) too; only windows 1-3m/6-12m exist, so the
  "no P(up)" rule applies to a future 5Y horizon, not medium. Medium headline = return band (T005, 2026-11-24).
