---
name: feature
description: Build a feature through the engineering-manager - clarify scope, approve the plan, dispatch, report.
argument-hint: "\"<feature description>\""
disable-model-invocation: true
shell: bash
---
!`python econ.py status --soft`
!`python econ.py task list --soft`

Feature request: $ARGUMENTS

1. Clarify only what blocks planning (AskUserQuestion, max 2 questions): scope, markets/horizons,
   anything outward-facing (new secrets, workflows, public pages).
2. Spawn `engineering-manager` with the brief:
   `TASK: plan and deliver "<feature>" | TARGET: <area> | INPUTS: docs/ARCHITECTURE.md, docs/CODEMAP.md |
   OUTPUT: task DAG + implemented files | CONSTRAINTS: <from step 1>, no pushes, no new secrets |
   DONE-WHEN: pytest green, audit clean, codemap --check clean`.
   It runs in the background; continue talking with the Owner meanwhile.
3. When it reports: relay to the Owner in Vietnamese (<= 8 lines). Questions in its ASK go to the Owner via
   AskUserQuestion; log answers with `python econ.py log decision "..."`.
4. Never commit or push without asking.
