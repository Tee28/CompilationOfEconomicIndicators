---
name: rates-fx-analysis
description: Rates, credit and FX analysis - yield curve shape, term premium (ACM), real yields and breakevens, credit spreads (BAA10Y, NFCI), rate differentials and carry, USD cycle, JPY/BOJ/MOF intervention, VND managed band.
user-invocable: false
---
# Rates, credit & FX

## Yield curve
- Levels: 3M (DGS3MO), 2Y (DGS2), 10Y (DGS10), 30Y. Spreads: 10Y-3M (T10Y3M, best recession record),
  10Y-2Y (T10Y2Y). Shape regimes: bull/bear x steepener/flattener (which end moves more).
- Bull steepening after inversion (front end falls fast) often comes near/at recession start - the
  "un-inversion" is a later-stage warning, not an all-clear.
- Term premium: ACM (NY Fed) 10Y term premium; rising term premium = supply/uncertainty, not growth optimism.

## Real yields and breakevens
- 10Y TIPS real yield (DFII10); breakeven = nominal - real (T10YIE). 5Y5Y forward (T5YIFR) = long-run
  inflation expectations anchor (~2.0-2.6% normal for CPI basis).
- Real yields drive long-duration assets (growth stocks, gold historically) - relationship can break (gold 2022+).

## Credit
- BAA10Y and AAA10Y (Moody's, long history), NFCI and its credit subindex (Chicago Fed, weekly).
  ICE BofA HY/IG OAS on FRED: only ~3 years of history and no redistribution -> `internal`, features only.
- Spread widening > 150bp from the cycle low within 6M has preceded most equity drawdowns > 20%.
- SLOOS (senior loan officer survey, quarterly): net tightening > 20% is a credit-crunch warning.

## FX
- Drivers by horizon: 1M momentum + risk sentiment; 12M rate differentials (2Y spread), terms of trade,
  growth differentials; 5Y valuation (REER vs 10Y mean, PPP) - mean reversion is slow (half-life 3-5 years).
- **USD smile**: USD strong when US outperforms and in global risk-off; weak in synchronised global growth.
- Carry: high-yielders earn carry but crash in risk-off (negative skew) - report skew with the forecast.
- Broad USD: DTWEXBGS (Fed nominal broad). DXY is EUR-heavy - prefer the broad index.

## Japan (JPY, JGB)
- BOJ ended negative rates (Mar 2024) and yield-curve control; rate path and JGB purchase taper drive JGB 10Y.
- USD/JPY tracks the US-JP 2Y/10Y differential most of the time; MOF intervention risk rises with speed
  of depreciation (e.g. moves > ~10 yen in a month, levels near 150-160 in 2022/2024). Verbal warnings
  ("watching with a high sense of urgency") precede actual intervention.
- Carry-trade unwinds (Aug 2024) cause sharp JPY rallies and global risk-off - a tail scenario.

## Vietnam (VND)
- SBV sets a daily central rate; commercial banks trade within +/- 5% band. Pressure signs: USD/VND near the
  band top, SBV selling reserves/forward sales, interbank VND rates spiking, rising free-market premium.
- Drivers: USD strength, US-VN rate gap, trade surplus/FDI inflows (supportive), gold-import demand.
- Data mostly monthly with lags; Vietnamese sources may block US IP -> degraded mode, see data-engineering.

## Indicators to compute
curve spreads and their 3M min/max · real policy rate · 2Y differentials vs USD · REER gap · credit spread
z-score and 6M change · NFCI level/change · breakeven change · FX realised vol 1M vs 1Y.

## Pitfalls
- Comparing yields across tenors without duration context; mixing CPI and PCE bases.
- Treating intervention levels as hard thresholds.
- Using today's BAA series definition for old data without checking methodology breaks.
