---
name: project-management
description: How managers plan and dispatch - task DAG with `econ task`, brief and report formats, nested dispatch limits, Definition of Done checks, gates, decisions and handoff.
user-invocable: false
---
# Project management (managers)

## Plan
- Goal -> tasks. One task = one owner, one main output file, verifiable DONE-WHEN.
- Add with dependencies; contract/producer tasks first, consumers after:
  `python econ.py task add --title "..." --owner data-engineer --deps T003 --inputs "config/sources.yaml" --outputs "src/econ/connectors/fred.py"`
- Size: a task should finish in < 30 agent turns. Bigger -> split.

## Dispatch
- `python econ.py task next` lists ready tasks. Send up to **4** in ONE message (parallel Agent calls).
- Before dispatch: `task set <id> --status doing`.
- Brief (<= 10 lines):
```
TASK: <imperative, one sentence>        TARGET: <task id + main path>
INPUTS: <paths / IDs to read - not contents>
OUTPUT: <files to write>                CONSTRAINTS: <scope limits, budgets, no-go>
DONE-WHEN: <commands that must pass, e.g. pytest -q green, `econ src check --id fred` ok>
```
- Depth limit is 2 (main -> manager -> specialist). Specialists cannot spawn or ask the Owner.

## Verify (Definition of Done)
- Run DONE-WHEN commands yourself. Also: `python -m pytest -q`, `python econ.py audit`,
  `python econ.py codemap --check` when code changed.
- Outputs exist and are within the owner's paths; no unrelated files touched (`git status --short`).
- Pass -> `task done <id>` (it prints newly ready tasks). Fail -> re-dispatch with the failure output
  (max 2 retries), then `task set <id> --status blocked --note "<why>"`.

## Consolidated report (<= 10 lines)
```
STATUS: done | partial | blocked | needs-approval
DONE: T004 connectors/fred.py; T005 tests (pytest 34 passed)
BLOCKED: T006 - EIA key missing (Owner)
DECIDE: <decisions the Owner must take, one line each>
NEXT: <next ready tasks -> owners>
```

## Gates and decisions
- `python econ.py gate check G#` lists deterministic gaps. Managers never approve gates: the main thread
  asks the Owner, then runs `gate approve G# --note "..."` (it logs the decision).
- Other Owner choices: main thread logs `python econ.py log decision "..." --gate G#`.

## Notes and ownership
- Change needed in a file you do not own: `python econ.py notes add --target <path> --note "..."`;
  the owner resolves it with `notes resolve N0xx`.

## Handoff (main thread, end of session)
`python econ.py handoff set --done "..." --next "..." --ask "..."` (<= 30 lines). The SessionStart brief
shows it next time.
