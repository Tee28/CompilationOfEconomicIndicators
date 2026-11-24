# Architecture

Read this only when changing the lab itself. Code locations: docs/CODEMAP.md (generated). Full plan (VI):
docs/PLAN.md. Decisions: work/decisions.md and docs/adr/.

## 1. System
```
GitHub Actions update-data.yml (cron 23:17 + 09:17 UTC weekdays, manual)
  econ update: fetch (budgets) -> store (append-only vintages, private repo econ-data) -> quality -> compute
               -> forecast -> ledger (CI only) -> publish (license gate) -> web build -> Pages
Browser: manifest.json (no-store) -> hashed JSON; live crypto prices + FX conversion client-side.
Dev machine: Claude Code (agents/skills) -> `python econ.py ...` (deterministic CLI). No live fetching locally
(corporate TLS inspection / web filter): fixtures or `econ pull-site` (gh run download).
```

## 2. Repo layers
| Layer | Path | Notes |
|---|---|---|
| Launcher | econ.py | hooks run in-process (stdlib, fail-open, exit 0); other commands re-exec in .venv |
| CLI | src/econ/ | `cli.py` registers subcommands; each returns `Result(text, data, code)` |
| Work ledger | src/econ/work.py | tasks.json, notes.csv, handoff.md, decisions.md, state.json, activity.log |
| Guards | src/econ/hooks.py + config/hooks.json | token guard, ownership guard, spawn allowlist |
| Registries | config/*.yaml | sources (P0), indicators/composites/markets/models/calendar (P2+) |
| Knowledge | knowledge/ + src/econ/kb.py | cards + SQLite FTS5 (.econ/kb.sqlite) |
| Site | web/ (P2) | React + Vite + TS + ECharts, HashRouter |
| Ledger | ledger/ (P2) | forecasts JSONL (append-only), scores, health.json - CI writes only |

## 3. Claude Code organisation
- **Main thread = CIO** (role in CLAUDE.md; no settings `agent` key, because an agent body would replace
  the default system prompt). All Owner approvals happen in the main thread (subagents lack AskUserQuestion).
- **10 subagents** (.claude/agents): managers `engineering-manager`, `research-lead`; specialists
  data-engineer, quant-researcher (opus), frontend-engineer, platform-engineer, macro-strategist,
  markets-strategist, risk-manager (opus), content-editor (effort low).
- **Dispatch**: main -> manager (background) -> up to 4 specialists in parallel (manager waits).
  `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2`; spawn allowlist in config/hooks.json `spawn`.
- **Ownership**: PreToolUse(Write|Edit|NotebookEdit|Agent|Task) reads `agent_type` and checks
  config/hooks.json `owners`; main thread unrestricted; agents not listed unrestricted.
  Known gap: Bash is not covered (an agent can write via shell). Mitigation: managers' DoD checks
  `git status --short`; a Bash write guard is a candidate if it becomes a problem.
- **Skills**: 13 expertise skills (`user-invocable: false`, preloaded per agent via `skills:`; asia-markets
  arrives in P6), workflow skills (`disable-model-invocation: true`, `shell: bash`, `!` lines with `--soft`).
  Workflow skills whose commands do not exist yet are added in the phase that builds the command:
  P2 `/update-data`, `/add-indicator`, `/add-rule`, `/outlook`, `/deploy-site`; P4 `/backtest`, `/model-review`.
- **Rules** (.claude/rules, path-scoped, <= 40 lines): python-core, connectors, models, registries,
  frontend, knowledge, ci-workflows. They load only when a matching file is read/edited.

## 4. Memory layers
| Layer | Where | Loaded |
|---|---|---|
| L0 charter | CLAUDE.md (<= 120 lines) | every session and subagent |
| L1 brief | SessionStart hook -> `econ status` (<= 20 lines) | startup/resume/clear/compact |
| L2 rules | .claude/rules/ | on matching file access |
| L3 agent memory | .claude/agent-memory/<agent>/MEMORY.md (<= 120 lines) | when the agent runs |
| L4 code map | docs/ARCHITECTURE.md + docs/CODEMAP.md | when changing code |
| L5 registries/digest | `ind get`, `rule list`, `digest` (P2+) | on demand |
| L6 KB | knowledge/** via `kb search` | on demand |
| L7 ledger | work/ via the brief | each session |
Budgets in config/econ.yaml `audit:`; `python econ.py audit` enforces them (CI too).

## 5. Hooks (all stdlib-only, one process, fail-open, silent unless needed)
| Event | Handler | Does |
|---|---|---|
| SessionStart | session-start | prints the brief |
| PreToolUse Read | pre-read | denies data/, parquet, site JSON, node_modules, dist, text files > 40 KB unsliced |
| PreToolUse Write/Edit/Agent | pre-write | ownership + spawn guard by agent_type |
| PostToolUse Write/Edit | post-edit | JSON/YAML validation of config/rulebook/content |
| SubagentStop | subagent-stop | appends `ts, agent_type, agent_id, transcript` to work/activity.log |
| PreCompact | pre-compact | writes work/compact-snapshot.md, prints <= 5 lines |
Token usage is parsed later from transcripts (`econ log tokens`, deduped by message id).

## 6. P0 probe results (2026-11-24, Windows 11, VS Code extension)
| Check | Result | Consequence |
|---|---|---|
| hooks fire (exec form, non-ASCII path) | PASS | keep `python ${CLAUDE_PROJECT_DIR}/econ.py hook <event>` |
| main-thread payload has no agent_type | PASS | empty agent_type = main thread = unrestricted |
| subagent payloads carry agent_type | PASS | ownership guard by agent_type works |
| token guard denies big Read | PASS | |
| ownership guard denies foreign write | PASS | |
| spawn guard denies unlisted spawn | PASS | |
| nested spawn, manager waits for result | PASS | default fork mode kept (`CLAUDE_CODE_FORK_SUBAGENT` unset) |
| SubagentStop has agent_id, agent_transcript_path, agent_type | PASS | token log from transcripts |
| transcript token parse > 0 | PASS | |
| skill `!` commands run (shell: bash) | PASS after fix | `!` lines may run **concurrently**: never rely on their order |

## 7. Split path (10 -> 17 agents)
Split when an agent's memory exceeds 80 lines or its tasks queue up (see `econ log tokens`):
- macro-strategist -> macro-economist + rates-fx-strategist + asia-strategist
- markets-strategist -> equity-strategist + commodities-analyst + crypto-analyst
- platform-engineer -> tech-lead + qa-engineer + devops-engineer
Skills are already split, so a split = new agent files + owners/spawn entries in config/hooks.json.

## 8. Conventions
- Internal files English; Owner-facing text Vietnamese. Dates ISO, UTC in data.
- CLI output <= 40 lines, `--json`, exit 0/1/2, `--soft` for skills; global flags may precede the subcommand.
- Windows: UTF-8 everywhere (PYTHONUTF8=1), pathlib, argv not shell strings; truststore for TLS.
- Secrets: .env (Read denied) + GitHub Secrets; `common.redact` on URLs, logs, fixtures.
