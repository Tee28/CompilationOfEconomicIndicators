---
name: signal-rulebook
description: Rulebook standards - rule YAML schema, evidence, locked holdout, BH-FDR and rule caps against data snooping, rules as regularised model features, rule lifecycle, and narrative templates tied to model contributions.
user-invocable: false
---
# Signal rulebook

Rules encode analyst knowledge ("if the yield curve has been inverted for 3+ months, recession risk in 12M
rises"). They are **features** of a regularised model, not standalone trading signals, and they feed the
deterministic narrative. The model decides the weight; the rule supplies the idea.

## Rule schema (`rulebook/<market>.yaml`)
```yaml
- id: MACRO_CURVE_INVERSION_3M        # stable UPPER_SNAKE, never reused
  market: us-macro                    # markets in config/markets.yaml
  horizon: [12M]                      # 1M | 12M | 5Y
  inputs: [US_T10Y3M]                 # indicator IDs only (registry), never raw series
  condition: "rolling_min(US_T10Y3M, 3) < 0"   # expression DSL evaluated by `econ rule test`
  direction: risk_up                  # up | down | risk_up | risk_down (for the target)
  rationale: "Inverted curve precedes US recessions with a 6-18M lag."
  evidence:
    - "Estrella & Mishkin (1998) [n]"
    - "NY Fed yield-curve recession probability model [n]"
  base_rate_expected: "~8 of 8 post-1968 recessions preceded; ~1-2 false positives"
  phrase_key: curve_inversion        # template in rulebook/phrases.vi.yaml
  status: candidate                   # candidate | tested | active | retired
  author: macro-strategist
  tests: {}                           # filled by quant-researcher: hit rate, n_eff, q-value, holdout result
```

## Discipline against data snooping
1. **Holdout locked**: the most recent 5 years are never used while designing or selecting rules.
   Only the final evaluation touches them, once per rule version.
2. **Log every try**: each condition/threshold variant tested is recorded (`econ rule test` appends to the
   trials log). The FDR denominator is the number of trials, not the number of survivors.
3. **Benjamini-Hochberg FDR** at q = 0.10 across all trials in a market; optionally White's Reality Check /
   Hansen SPA when comparing many variants of one idea.
4. **Cap** active rules per market (default 12). A new rule must replace a weaker one beyond the cap.
5. Economic rationale first: a rule without a mechanism and prior literature is not tested at all.
6. Thresholds: prefer round, literature-based values (0, 50, 2 sd) over optimised ones.

## Rules inside the model
- Each active rule becomes a binary/continuous feature; the model (logistic / ridge / elastic net) estimates
  its weight with regularisation, walk-forward. A rule whose weight shrinks to ~0 is a retirement candidate.
- The narrative lists the top drivers by **actual contribution** (weight x feature value at the origin),
  so text direction always matches the published probability. Rules that fire but contribute little are
  mentioned as "tín hiệu phụ" or not at all.

## Lifecycle
candidate (strategist) -> tested (quant: in-sample + walk-forward + FDR) -> red-teamed (risk-manager) ->
active (Owner approval, logged decision) -> monitored (monthly score) -> retired (with reason, kept in file).

## Writing a rule well
- One idea per rule; inputs <= 3; horizon explicit; no hidden look-ahead (use lagged indicators).
- State the failure mode ("false positive in 1966, 1998").
- Specify what would invalidate the rule (regime change, structural break).

## Templates (phrases)
- One `phrase_key` per rule; templates take slots: `{indicator_name}`, `{value_fmt}`, `{asof}`, `{horizon}`.
- Internal-license inputs: template must not include `{value_fmt}` (signal only).
