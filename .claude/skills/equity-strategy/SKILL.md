---
name: equity-strategy
description: Equity strategy - valuation (CAPE, ERP, Buffett indicator from Z.1), earnings cycle, breadth and momentum, sector rotation, Grinold-Kroner expected returns; notes for Vietnam (T+2, foreign room, margin, upgrade) and Japan (TSE reform, yen sensitivity).
user-invocable: false
---
# Equity strategy

## Horizon map
| Horizon | What has power | What does not |
|---|---|---|
| 1M | trend/momentum (price vs 10M MA), volatility regime (VIX term structure), breadth thrusts, sentiment extremes (contrarian), liquidity | valuation |
| 12M | earnings revisions/cycle (ISM, PMI new orders), credit spreads, policy cycle, recession probability | CAPE alone (weak) |
| 5-10Y | valuation (CAPE, ERP, Buffett), starting dividend/buyback yield | momentum |

## Valuation
- **CAPE** (Shiller): price / 10Y average real earnings. R^2 vs 10Y forward real returns ~0.4-0.5 in US
  history; level shifts (accounting, buybacks, sector mix) mean compare with a rolling 30Y median, not 1881 mean.
- **ERP**: earnings yield (1/CAPE or forward E/P) - 10Y real yield (DFII10). Low ERP = thin cushion.
- **Buffett indicator**: corporate equities market value / GDP from Fed Z.1 (nonfinancial corporate
  equities, FL103164103) divided by nominal GDP; quarterly, lag ~10 weeks. (Wilshire series left FRED.)
- **Grinold-Kroner**: E[R] = dividend yield + net buyback yield + real EPS growth + inflation + change
  in valuation (assume partial reversion of CAPE toward median over the horizon). Report a range from
  scenarios (no reversion / half / full).

## Earnings cycle
- EPS growth follows ISM/PMI with ~3-6M lag; recessions cut S&P 500 EPS ~15-30% on average (peak-trough).
- Revisions breadth (up vs down) is a 1-3M signal when available; margins mean-revert slowly.

## Breadth and momentum
- % of constituents above 200D MA; advance/decline line divergence; new highs - new lows.
- Time-series momentum (12M-1M return > 0) improves drawdown control historically; whipsaws in ranges.
- Volatility: VIX > 30 = stress; VIX term structure inverted (spot > 3M) = acute stress, often near lows.

## Base rates (US large caps, since 1950-ish)
- P(12M return > 0) ~ 75%; P(1M > 0) ~ 60%. Any model must beat these climatology numbers.
- Average bear market (-20%+) ~ every 5-6 years; recession bears deeper and longer than non-recession ones.

## Sector rotation (tendencies, weak evidence)
Early cycle: financials, consumer discretionary, small caps. Mid: tech, industrials. Late: energy,
materials. Recession: staples, utilities, health care, long bonds.

## Japan
- TSE governance reform (2023+: P/B < 1 disclosure push), buybacks rising, NISA inflows.
- Earnings sensitive to USD/JPY (exporters): yen weakening ~+0.5-1% EPS per 1 yen for TOPIX historically
  (rule of thumb; verify current estimates). Foreign flows drive short-term moves.

## Vietnam
- VN-Index: retail-dominated (high turnover, momentum, margin-driven swings). Settlement T+2.
- Foreign ownership limits ("room") on many stocks -> premiums in full-room names.
- Margin debt vs market cap is a key risk indicator; SBV credit growth quotas matter.
- FTSE Russell upgrade to Secondary Emerging (watch list; decision timing matters for flows) and MSCI status.
- Data access may be limited (VN sources block US IPs) - prefer monthly + degraded mode.

## Pitfalls
Valuation as a timing tool · survivorship in index history · mixing price and total return ·
ignoring currency for non-USD investors (site shows USD/JPY/VND).
