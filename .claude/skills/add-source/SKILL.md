---
name: add-source
description: Add a data source - license and terms check, registry entry, runner verification, connector task.
argument-hint: "<source name or URL>"
disable-model-invocation: true
shell: bash
---
!`python econ.py src list --soft`
!`python econ.py kb search "$ARGUMENTS" --soft`

New source: $ARGUMENTS

1. Spawn `data-engineer` with the brief:
   `TASK: evaluate and register source "$ARGUMENTS" | TARGET: config/sources.yaml |
   INPUTS: docs/source-verification.md, skill data-engineering | OUTPUT: registry entry (license class +
   attribution + terms URL, auth env, budget, cadence, SLA, fallback), KB card knowledge/sources/<id>.md |
   CONSTRAINTS: no live fetch from this machine; no secrets in files | DONE-WHEN: `python econ.py src list`
   shows it and pytest is green`.
2. Relay its findings to the Owner in Vietnamese (<= 8 lines): license class and what the site may show,
   key needed (free?), call budget, risks. If a key or repo secret is needed, ask the Owner - only they create it.
3. On Owner OK: tell them to run the `src-check` workflow on GitHub (or offer to trigger it with
   `gh workflow run src-check.yml` after confirmation), then add a connector task via `/feature` or
   `python econ.py task add --owner data-engineer ...`.
