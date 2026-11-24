---
name: crypto-analysis
description: Crypto analysis - BTC halving cycle and its limits, on-chain valuation (MVRV, realised cap), stablecoin supply and liquidity, derivatives (funding, basis, OI), spot ETF flows, sentiment (Fear & Greed), correlation with Nasdaq and liquidity.
user-invocable: false
---
# Crypto analysis

## Sample-size warning first
BTC has ~4 halving cycles (2012, 2016, 2020, 2024) and ~15 years of data. Cycle models (halving timing,
stock-to-flow) rest on 3-4 observations: treat them as **weak evidence**; never as a law. Stock-to-flow
failed its 2021-22 targets. Our confidence labels must reflect this (often Low/Medium).

## Drivers by horizon
| Horizon | Drivers |
|---|---|
| 1M | momentum/trend, funding rates and leverage, ETF flows, stablecoin net issuance, Fear & Greed extremes (contrarian), Nasdaq/risk sentiment |
| 12M | global liquidity and real rates, cycle phase (months since halving as a weak feature), MVRV regime, adoption flows |
| 5Y | adoption scenarios only (expected-return bands, very wide) |

## On-chain
- **MVRV** = market cap / realised cap (coins valued at last-moved price). MVRV > 3.5 marked past cycle tops;
  < 1 marked bottoms. Source: CoinMetrics community API (CC BY-NC 4.0 -> `attributed` but non-commercial:
  no ads on the site). MVRV Z-score variants are popular but add fitting freedom.
- Realised price = realised cap / supply: a support level in bear markets historically.
- Exchange balances, long-term holder supply: interesting but source-dependent; check licenses.
- mempool.space: fees, hashrate (open API) - network health, weak price signal.

## Liquidity and stablecoins
- Total stablecoin supply (DefiLlama) growth = new USD liquidity entering crypto; 30D change is a
  useful 1M-3M feature.
- Global liquidity (Fed net liquidity, global M2 in USD) leads BTC by ~1-3 months in some studies;
  relationship unstable, test walk-forward.

## Derivatives (client-side or open sources)
- Perpetual funding rate high and positive = crowded longs (liquidation risk); negative during selloffs =
  capitulation. Futures basis (CME/annualised) > 15% = euphoria.
- Open interest rising with price + high funding = leverage-driven rally (fragile).
- Binance API is blocked from US runners (HTTP 451): fetch from the browser only, not in the pipeline.

## Flows and sentiment
- US spot BTC ETFs (Jan 2024+), ETH ETFs (Jul 2024+): daily net flows; short history.
- Fear & Greed index (alternative.me, open API): extremes < 15 or > 85 are contrarian at 1M, weak.

## Cross-asset
- BTC-Nasdaq 60D correlation has ranged ~0 to 0.7; high in liquidity-driven regimes (2022).
- Drawdowns of 70-85% happened in each bear market; any 12M forecast needs fat left tails.

## Base rates
P(BTC 12M return > 0) over 2013-2024 ~ 65-70% but heavily cycle-dependent; P(1M > 0) ~ 55%.
Volatility ~60-80% annualised (falling over time).

## Live prices on the site
Coinbase/CoinGecko public endpoints from the browser for live prices; published forecasts use the
pipeline snapshot only (reproducibility).
