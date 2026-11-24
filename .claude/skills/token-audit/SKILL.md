---
name: token-audit
description: Token-hygiene audit - always-loaded size, agent/skill/rule/memory budgets, token usage per agent from transcripts.
disable-model-invocation: true
shell: bash
---
!`python econ.py audit --soft`
!`python econ.py log tokens --soft`

Explain to the Owner in Vietnamese (<= 10 lines):
- always-loaded token estimate and every file over budget (what to trim, how)
- the 3 most expensive agents by output + cache-write tokens, with one concrete saving each
  (narrower `context` pack, lower effort/model, smaller tasks, fewer files read, CLI instead of reasoning)
- agent memories over 80 lines (split-path trigger in docs/ARCHITECTURE.md) or needing curation
Offer fixes; do not edit agent or skill files without the Owner's OK.
