# Runbook

## Workflows (.github/workflows)
| File | Trigger | Does |
|---|---|---|
| update-data.yml | cron `17 23 * * *`, `17 9 * * 1-5`, manual | restore econ-data (if token) -> `update` -> `ledger verify` -> `publish --scan` -> commit ledger/ + web/public/data |
| deploy-site.yml | after update-data succeeds, push to main on web/** or ledger/health.json, manual | npm ci + build -> Pages |
| ci.yml | PR, push to main | ruff, pytest, audit, codemap --check, ledger verify, license scan; web typecheck/vitest/build/size budget |
| src-check.yml | manual | probe sources from a runner |

Pushes made with GITHUB_TOKEN do not trigger other workflows, hence deploy-site uses `workflow_run`.

## One-time Owner actions (not done by agents)
1. Settings > Pages > Source = GitHub Actions.
2. Secret `FRED_API_KEY` (already used by src-check).
3. Optional: secret `DATA_REPO_TOKEN` (fine-grained PAT, contents:write on private repo `econ-data` only). Without it
   update-data skips restore/persist with a notice and runs on an empty store (degraded health).
4. Commit `web/package-lock.json` (run `npm install` in web/); until then web CI/deploy jobs skip with a warning.

## G1: how the ledger artifacts get created
`ledger/health.json` and `ledger/forecasts/*` are written only by CI. They do not exist until the first run of
update-data.yml (Actions > update-data > Run workflow). That run appends the first forecasts, writes health, and the
bot commits them. Afterwards `ledger verify` (ci.yml and update-data.yml) fails on any rewrite of an old line.
Local rehearsal (no writes to the real ledger): `python econ.py update --dry-run --out-dir <tmp>`.
