---
name: econ-status
description: Project status for the Owner - stage, gates, data freshness, open/ready tasks, open notes, handoff.
disable-model-invocation: true
shell: bash
---
!`python econ.py status --soft`
!`python econ.py gate check --soft`
!`python econ.py task list --soft`
!`python econ.py notes list --soft`

Summarise for the Owner in Vietnamese, max 10 lines, BLUF first:
- stage and the next gate: what is missing (from `gate check`) and who owns each gap
- tasks: ready / doing / blocked (blocked ones with reason)
- data freshness problems, if any
- one recommended next action, and whether it needs the Owner's approval
Do not read any other file.
