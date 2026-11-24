---
paths:
  - "web/**"
---
# Frontend (web/)

- React 18 + Vite + TypeScript strict + ECharts; HashRouter (GitHub Pages). Scripts via
  `npm --prefix web run typecheck|test|build`.
- Data: fetch `data/manifest.json` with `cache: "no-store"`, then the hashed files it lists. Never hard-code
  data file names. Types in `web/src/types/` are generated from the JSON schema - do not edit by hand.
- Do not Read `web/public/data/**` or `web/dist/**` in full; use fixtures in `web/src/test/fixtures/`.
- UI strings from i18n (`web/src/i18n/vi.ts`); numbers en-US, tabular monospace; currency switcher USD/JPY/VND.
- License-aware rendering: series flagged `internal` show only signal / probability / percentiles.
- Uncertainty always visible (bands, confidence label, n_eff). Disclaimer + attribution on every page.
- a11y: semantic HTML, focus states, keyboard navigation, WCAG AA contrast, charts have text summaries.
- Each component: a vitest render test with fixture data. Watch bundle size (lazy-load ECharts per page).
