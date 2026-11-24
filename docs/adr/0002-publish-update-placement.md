# ADR 0002 - Publish/update behaviour and module placement

## Status
Accepted (T007). Supplements ADR 0001; supersede, never rewrite.

## Context
ADR 0001 names `econ.update.cmd_update`, but the platform-engineer ownership guard covers only
`src/econ/publish/*` for this feature, and `--dry-run` must still allow inspecting site JSON.

## Decision
- Orchestrator lives in `src/econ/publish/update.py`; `cli.py` maps `update` to `publish.update.cmd_update`.
- `update --dry-run`: plan-only fetch (no network), no ledger writes, no write to the real `web/public/data`.
  With an explicit `--out-dir` the site JSON is written under `<out-dir>/web/public/data` (inspection/tests).
- Steps report `ok | degraded | skipped | failed`; a failed step skips dependents. Missing FRED key => fetch
  `degraded` (skipped series) and those sources `degraded` in health, exit 0. Exit 1 = step failure, 2 = gate.
- Narrative: band chosen from the rounded printed percent; driver sentences from contribution sign only.
- Gate: internal series/composites carry no values/level (types) + `publish --scan` re-derives licenses from the
  registry and checks files on disk; per-file size budget `audit.site_json_kb`; banned-word scan on output.
- Site files are `<name>.<sha256[:8]>.json` + `manifest.json`; older hashed files are removed on write.

## Consequences
`publish --scan` is the CI `license-scan` entry point (T011). Health is written to `ledger/health.json` only.
