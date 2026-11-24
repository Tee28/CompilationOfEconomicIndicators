---
name: wrap
description: End the session cleanly - update the handoff, check budgets, list uncommitted work, so the next session (or /clear) starts from the brief.
disable-model-invocation: true
shell: bash
---
!`python econ.py task list --soft`
!`python econ.py audit --soft`
!`git status --short`

1. Write the handoff (<= 30 lines, English) from this session's work:
   `python econ.py handoff set --done "..." --doing "..." --next "..." --ask "..."` (repeat flags per item).
   Next items name an owner (Owner / agent). Open questions only if the Owner must decide.
2. If `audit` reports issues, fix the trivial ones (or add a task for platform-engineer).
3. If code changed: `python econ.py codemap` and `python -m pytest -q`.
4. Tell the Owner in Vietnamese (<= 6 lines): what got done, what is next, uncommitted files, and that
   they can `/clear` now. Ask before committing or pushing - never do it unasked.
