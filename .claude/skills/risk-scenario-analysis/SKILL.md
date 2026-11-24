---
name: risk-scenario-analysis
description: Risk and red-team methods - trigger-based scenarios with probability bands, pre-mortems, red-team checklist for models/rules/outlooks, tail-risk and drawdown framing, and compliance checks for published outlooks.
user-invocable: false
---
# Risk & scenario analysis

## Scenarios (not forecasts)
Each scenario set covers one market/horizon with 3-4 mutually exclusive, collectively plausible paths:
```
name: "Hard landing 2027"
trigger: what must happen first (observable, dated) - e.g. payrolls < 0 for 2 months + claims > 300k
path: sequence of macro/market moves with rough magnitudes and timing
first signs: 2-3 indicators we would see move first (with IDs)
probability band: 10-20% (state the base rate it is anchored to)
market impact: direction and rough range per market on the site
invalidated if: what would rule it out
```
- Anchor probabilities to base rates, then adjust; bands, not point estimates; they need not sum to 100%
  when scenarios overlap - say so.
- Always include one scenario where our main model is wrong in the opposite direction.

## Pre-mortem (before promoting a model or publishing a new outlook type)
"It is 12 months later and this forecast embarrassed us. Why?" List 5 reasons, rank by likelihood x
damage, and add a monitor or mitigation for the top 3.

## Red-team checklist (model / rule / outlook)
1. Data: look-ahead, vintage use, survivorship, license class of each input.
2. Selection: number of variants tried, FDR honesty, holdout untouched, threshold optimisation.
3. Sample: n_eff, regimes covered (high inflation, GFC, COVID, 2022 rate shock), crypto short history.
4. Performance: vs baseline out of sample, CI of the gain, stability across sub-periods.
5. Calibration: reliability slope, tail coverage (p10/p90 breaches ~10% each?), overconfidence.
6. Mechanism: does a plausible economic story exist; would it survive a structural break?
7. Narrative: text direction matches probability; drivers are actual contributions.
8. Communication: confidence label correct; uncertainty displayed; no advice wording.
Verdict: pass / pass-with-conditions (list them) / fail (list blockers).

## Tail risk
- Report drawdown risk separately from P(up): e.g. P(drawdown > 20% within 12M) from model or history.
- Fat tails: use empirical or Student-t quantiles; never assume normal tails for crypto, oil, equities.
- Correlations go to 1 in crises: cross-market scenarios must move together.
- Known tail catalysts list (maintain in docs/risk/tail-catalysts.md): policy errors, credit events, JPY
  carry unwind, oil supply shock, geopolitical escalation, stablecoin de-peg, sovereign debt stress.

## Compliance (every published outlook)
- "Không phải lời khuyên đầu tư" present; no "nên mua/bán/chắc chắn"; probabilities, not promises.
- Track record link and confidence label visible; data freshness badge correct.
- Licensed data respected (internal values absent). Attribution present.

## Output format
`docs/risk/<YYYY-MM-DD>-<subject>.md` with sections: Verdict · Findings (severity high/med/low) ·
Required fixes · Scenarios · Monitors (indicator IDs + thresholds).
