---
name: commodities-analysis
description: Commodities analysis - gold (real yields, USD, central-bank buying, post-2022 break, PAXG proxy, SJC premium), silver, crude oil (OPEC+, EIA inventories, SPR, curve), natural gas, copper; supply/demand and curve-structure signals.
user-invocable: false
---
# Commodities

## Gold
- Classic drivers: 10Y real yield (inverse), broad USD (inverse), inflation expectations, risk-off demand.
- **Break since 2022**: gold rose despite sharply higher real yields - central-bank purchases (EM reserves
  diversification after Russia sanctions, > 1,000 t/yr in 2022-2024 per WGC), Asian demand. Treat the
  real-yield relationship as regime-dependent; include CB buying (WGC quarterly) as a feature.
- Data: PAXG-USD (Coinbase) is the daily proxy (tokenised 1 oz, tracks spot closely; small premium/discount,
  weekend trading); World Bank Pink Sheet monthly average for long history. LBMA prices are licensed -> not used.
- **Vietnam SJC**: SJC bar price trades at a premium to world gold converted at USD/VND; premium driven by
  SBV control of bar supply (premium swung ~VND 5-20m/tael 2023-24 before SBV auctions/direct sales).
  1 tael (lượng) = 37.5 g = 1.2057 troy oz. SJC site blocks bots -> manual/degraded.
- Silver: higher beta to gold plus industrial demand (solar); gold/silver ratio > 80 historically high.

## Crude oil
- Benchmarks: WTI (DCOILWTICO), Brent (DCOILBRENTEU) on FRED/EIA.
- Supply: OPEC+ quotas and spare capacity (concentrated in Saudi/UAE), US shale response (rig count lag
  ~6M), sanctions/geopolitics. Demand: global IP/PMI, China, seasonality (driving season).
- Inventories: EIA weekly US crude + products vs 5Y seasonal average (surplus = bearish); SPR levels.
- Curve: backwardation (front > back) = tight market and positive roll yield; contango = surplus.
  Front-month vs 12M spread is a robust state variable.
- Shocks are asymmetric (supply disruptions spike prices) - forecasts need fat right tails.

## Natural gas
- Henry Hub (US) vs TTF (Europe) vs JKM (Asia) disconnected by LNG capacity; storage vs 5Y average and
  weather (HDD/CDD) dominate; extreme volatility -> wide intervals, low confidence.

## Copper ("Dr. Copper")
- China property/grid demand, global PMI; copper/gold ratio co-moves with 10Y yields (growth proxy).
- Energy-transition demand vs mine supply growth: structural story, weak short-horizon power.

## Signals by horizon
| Horizon | Signals |
|---|---|
| 1M | trend/momentum, curve structure changes, inventory surprises, positioning extremes (CFTC COT) |
| 12M | global growth cycle, USD, real rates (gold), OPEC+ policy, inventory trend |
| 5Y | cost curves (marginal cost of supply), real price vs long history (mean reversion slow), CB demand |

## Base rates and caution
- Commodity spot returns have weak long-run real drift; total return from futures includes roll yield.
- P(gold up over 12M) historically ~55-60% - modest edge needed to beat climatology.
- Geopolitical events are not forecastable from data: express them as scenarios (risk-scenario-analysis).

## Pitfalls
Spot vs futures returns confusion · ignoring roll yield · using LBMA/ICE data without license ·
assuming the pre-2022 gold model still holds.
