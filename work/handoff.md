# Handoff - 2026-11-24

## Done
- P2 live slice, Python side (T001-T007, T010, T011): schemas, ADR 0001/0002, 20 indicators, 3 composites
- Connectors fred/pinksheet/oecd; baselines + ridge; ledger; VI phrases; publish + license gate
- Orchestrator at src/econ/publish/update.py; workflows update-data / deploy-site / ci; docs/runbook.md
- pytest green, audit clean, codemap --check clean; gate G1 lacks only ledger/health.json + ledger/forecasts (first CI run)
- Owner decisions: scope macro+US+gold+oil, horizons 1-3m & 6-12m; workflows local only; git status/diff allowed
- P2 committed 1ce9a4d on branch p2-live-slice (pushed; NOT merged to main, so cron/deploy inactive)

## In progress
- T008 web BLOCKED: npm install ETIMEDOUT (corporate proxy); web/ written but never typechecked/built; no package-lock.json
- Maybe a leftover node process PID 34180 from the failed install
- T009 web integration waits on T008

## Next
- Owner answers open questions below -> log decisions
- ruff check . = 11 findings (6 auto-fix) -> platform-engineer, else ci.yml goes red
- After npm works: frontend-engineer resumes T008, then T009
- Main thread writes skills /update-data /add-indicator /add-rule /outlook /deploy-site (.claude/skills not agent-writable)
- research-lead: rulebook/*.yaml signal layer (deferred; narrative uses model drivers + phrases for now)
- With approval: commit, push, enable Pages (Source=GitHub Actions), first workflow_dispatch
- First runner fetch must verify OECD key USA.M.LI.IX._Z.AA.IX._Z.H and Pink Sheet sheet/header names
- Expect SP500 confidence Low (FRED SP500 only ~10y history)

## Open questions (Owner)
- DATA_REPO_TOKEN secret for econ-data exists? (without it first CI run uses an empty store)
- npm: Owner configures proxy/mirror, or leave web build to CI?
- id case: lower_snake (code now) vs UPPER_SNAKE (.claude/rules/registries.md, note N002)?
- keep medium-horizon p_up as secondary field next to the return band?
- merge p2-live-slice into main? (activates cron + deploy; fix ruff first)
