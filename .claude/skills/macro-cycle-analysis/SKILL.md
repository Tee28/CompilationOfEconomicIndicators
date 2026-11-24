---
name: macro-cycle-analysis
description: Business-cycle analysis - 4 cycle phases and growth/inflation (GIP) regimes, leading/coincident/lagging indicators, recession probit, Sahm rule, claims, nowcasts, Taylor rule and r*, liquidity, publication lags and revisions, base rates.
user-invocable: false
---
# Macro cycle analysis

## Regime frame
- **Phases**: expansion (growth above trend, rising) -> slowdown (above trend, falling) -> contraction
  (below trend, falling) -> recovery (below trend, rising). Measure "trend" with an output-gap proxy or
  the 6M change of a composite leading index vs its 10Y median.
- **GIP quadrants** (growth x inflation, each = direction of 6M change vs 12M ago): Goldilocks (G up, I down),
  Reflation (G up, I up), Stagflation (G down, I up), Deflation/slowdown (G down, I down).
  Asset tendencies (base rates, not rules): equities best in G up; long bonds best in G down & I down;
  commodities/gold relatively better in I up; USD tends to rise in global G down.

## Indicator families (US first; same logic for others)
| Type | Examples (FRED ids where available) | Lead |
|---|---|---|
| Leading | yield curve T10Y3M/T10Y2Y, building permits PERMIT, ISM new orders, initial claims ICSA, OECD CLI, credit spreads BAA10Y, NFCI, consumer expectations | 6-18M |
| Coincident | payrolls PAYEMS, industrial production INDPRO, real income ex transfers W875RX1, real sales | 0 |
| Lagging | unemployment duration, CPI services, unit labor costs, C&I loans | after |
Composite leading index: z-score of each 6M change (expanding window), equal-weighted; breadth = share
of components improving.

## Recession tools
- **Yield-curve probit** (Estrella-Mishkin; NY Fed): P(recession in 12M) from the 10Y-3M spread;
  inverted for 3+ months preceded every US recession since 1968, lead 6-24M, with few false signals (1966, 1998 marginal).
- **Sahm rule**: 3M avg unemployment rate rises >= 0.5pp above its 12M low -> recession typically started.
  Real-time signal, near-zero lead; 2024 triggered without a recession (labour supply shock) - not infallible.
- **Initial claims**: 4-week avg up > 20% from cycle low is a late-cycle warning.
- NBER dates are announced 6-18M late: label training targets with dates known later, but evaluate with
  data known at the origin.

## Inflation
- Headline vs core vs services ex housing; 3M/6M annualised for momentum; breakevens (T5YIE, T5YIFR) for
  expectations; wage growth (Atlanta Fed tracker, ECI) for persistence.
- Base rate: once core inflation > 5%, getting back to 2% has historically needed a slowdown in most cases.

## Policy and rates
- **Taylor rule**: i = r* + pi + 0.5(pi - 2) + 0.5(output gap). Compare with the policy rate to judge stance.
  r* estimates (Laubach-Williams, Holston-Laubach-Williams) are very uncertain (+/- 1pp+).
- Real policy rate = policy rate - core PCE (or 1Y expectations). Positive and rising = restrictive.

## Liquidity
- Fed balance sheet WALCL minus TGA (WTREGEN) minus reverse repo RRPONTSYD = "net liquidity" proxy.
- Global: Fed+ECB+BOJ balance sheets in USD, broad money, dollar strength (DTWEXBGS) - liquidity tends to
  lead risk assets by ~3-6M; correlation is unstable, use as a feature not a law.

## Nowcasting
- GDPNow (Atlanta Fed), NY Fed Staff Nowcast: use the value as published on each date (store vintages).
- Our own: bridge equations from monthly coincident data -> quarter GDP; report the error band.

## Publication lags and revisions
| Series | Release lag | Revisions |
|---|---|---|
| Payrolls | ~1 week after month | 2 monthly + annual benchmark (large) |
| CPI | ~2 weeks | seasonal factors revised annually |
| GDP | ~4 weeks (advance) | 2 monthly + annual, can flip sign |
| ISM | 1st business day | small |
| Claims | weekly, Thursday | small |
Always use the vintage or apply the lag (config/calendar.yaml).

## Base-rate thinking
- Unconditional P(US recession within 12M) ~ 15% (post-1945 frequency). Start there, update with evidence.
- Soft landings are rarer than forecasters expect but did happen (1966, 1984, 1995, arguably 2023-24).
- Report: regime call, P(recession 12M) with band, the 3 drivers, what would change the view.
