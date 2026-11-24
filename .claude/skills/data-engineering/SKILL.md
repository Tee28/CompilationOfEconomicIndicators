---
name: data-engineering
description: Data engineering for free economic/market APIs - source registry, connector template, call budgets, retry/cache/TLS, vintages and revisions, 3-class licensing, key redaction, freshness SLA with holiday calendars, degraded mode.
user-invocable: false
---
# Data engineering

## Source registry entry (config/sources.yaml)
id, name, base_url, auth (`env: FRED_API_KEY` or none), license `{class: open|attributed|internal,
attribution: "...", url: terms}`, budget `{per_run, per_day}`, cadence (daily/weekly/monthly/quarterly),
sla_days (business days after expected release), fallback (other source id or `degrade`), phase, notes.
Verified status lives in docs/source-verification.md (runner `src-check` workflow).

## License classes
- **open**: public domain / CC0 / government open data -> may be republished with credit.
- **attributed**: CC BY or terms allowing display with attribution -> show attribution next to the chart.
- **internal**: no redistribution (third-party series on FRED, CC BY-NC used commercially, exchange data
  with display limits) -> models only; publish signals/probabilities, never values, deltas or history.
When in doubt, classify `internal` and ask research-lead to check the terms.

## Connector template
```python
def fetch(series: SeriesSpec, since: date | None, budget: Budget) -> pd.DataFrame:
    budget.take(1)                                    # raises when the per-run budget is exhausted
    js = http.get_json(url, params, source="fred")    # retries, cache, truststore, redaction
    df = parse(js)                                    # pure function, unit-tested on a fixture
    return df.assign(series_id=series.id, source="fred", fetched_at=utcnow())
```
- Incremental: request from `last_date - revision_window` (e.g. 400 days for monthly macro) to capture revisions.
- Pagination and rate limits per source; sleep between calls when the API asks (Retry-After).

## HTTP rules
- Timeouts (25 s), 3 retries with exponential backoff on 429/5xx/timeouts only; no retry on 4xx.
- Cache GET responses in `.econ/cache` for development; CI uses `actions/cache` only as acceleration.
- truststore for corporate TLS; library-default User-Agent (IMF CDN blocks custom ones). No personal data.
- `common.redact` on every URL/log/exception message; fixtures saved through the same redaction.

## Store and vintages
- Raw: private `econ-data` repo `raw/<source>/<series>.parquet`, append-only, each row with `fetched_at`.
- Vintage view: "value of series X as known at time T" = latest row with fetched_at <= T per date
  (or ALFRED realtime_start/end when available). Models read through this view only.
- Never delete or rewrite rows; corrections are new rows plus a quality note.

## Quality checks (per fetch)
schema/columns · date monotonic and unique · value range vs history (|z| > 6 flags) · staleness vs SLA ·
unexpected gap · unit/scale change (ratio jump x10/x100) · count of revised points.
Output: `ledger/health.json` `{asof, sources: {id: {ok, last_obs, lag_days, fails, note}}}`.

## Freshness SLA and calendars
- Expected release dates from config/calendar.yaml (US/JP/VN holidays, release schedules).
- A source is late when today > expected_release + sla_days (business days). Late -> degraded, not failed.
- 3 consecutive failures -> CI opens/updates a GitHub issue (labels `data`, source id).

## Degraded mode
Missing source -> use fallback; else carry last value with `stale: true` flag and widen intervals;
composites recompute weights over available members (min coverage 60%, else composite marked unavailable).
The site shows a "dữ liệu chậm" badge - never silently stale.

## Known source quirks (P0)
Binance 451 from US runners (client-only) · SJC 403 anti-bot · TCBS API retired · Stooq needs key/CAPTCHA ·
Twelve Data free tier forbids display · ICE BofA on FRED: 3y history, internal · Wilshire 5000 removed from FRED.
