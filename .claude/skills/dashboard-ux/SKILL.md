---
name: dashboard-ux
description: Dashboard UX for probabilistic forecasts - information hierarchy, semantic color, visualising uncertainty (fan charts, bands, probability bars), license-aware display, freshness badges, mobile-first and accessibility, Vietnamese UI conventions.
user-invocable: false
---
# Dashboard UX

## Information hierarchy (every market page)
1. **Headline** (BLUF): view per horizon - "1 tháng: Trung lập · 12 tháng: Nghiêng tăng · 5 năm: 4-7%/năm".
2. Probability + confidence: P(tăng) bar with climatology tick, label Cao/Trung bình/Thấp, n_eff.
3. Drivers: top 3 contributions (signed bars) with one-line template text each.
4. Charts: history + forecast fan (only for open/attributed series), indicator panels.
5. Track record: hit rate / Brier vs baseline, link to Độ chính xác page.
6. Methodology, sources/attribution, disclaimer, data as-of.
Overview page: one card per market (headline + P(up) + change since last update), regime summary, heatmap.

## Visualising uncertainty
- Fan chart: p10-p90 light band, p25-p75 darker, median line; forecast region shaded differently from history.
- Probability bar 0-100% with the climatology base rate marked - shows whether we deviate from "normal".
- Never show a single point forecast without its band. Long horizon: range bars, no P(up).
- Confidence label visually tied to the number (same card), with a tooltip explaining it.

## Semantic color (dark theme #070b14)
- Up/positive: teal-green; down/negative: coral-red; neutral: slate; warning/stale: amber; info: cyan;
  accent: violet. Never rely on color alone: add arrows/signs/text (color-blind safe).
- Consistent mapping across pages; diverging scales centred on the neutral value (heatmaps).

## License-aware display
- Series with `internal` license: show signal state (e.g. "Tín dụng: thắt chặt"), percentile or P(up);
  no axis values, no level, no history chart, no CSV download.
- Attribution text near each chart; FRED required line in footer.

## Freshness
Badge per card: "Cập nhật 2 giờ trước" (green), "dữ liệu chậm" (amber, beyond SLA), "thiếu nguồn"
(red, degraded). Always show `data_asof` in the page header.

## Mobile-first
- Cards stack vertically; tables become cards < 640px; charts 16:10 with touch tooltips; tap targets 44px.
- Lazy-load ECharts per route; JSON per page < 200 KB.

## Accessibility
WCAG AA contrast (4.5:1 text), focus rings, keyboard navigation (shortcuts: g o overview, g a accuracy,
1-8 markets, ? help), aria-labels on charts + a text summary sentence, prefers-reduced-motion respected.

## Vietnamese UI conventions
- Labels in Vietnamese with English term on hover/first use (e.g. "Lợi suất thực (real yield)").
- Numbers en-US format (1,234.5), percent with 1 decimal, dates YYYY-MM-DD or "24/11/2026" consistently
  (pick one in i18n and keep it); currency switcher USD / JPY / VND remembered in localStorage.

## Anti-patterns
Gauges/speedometers for probabilities · 3D charts · rainbow scales · red/green only · hiding bad track
records · animations that imply precision · "buy/sell" buttons or wording.
