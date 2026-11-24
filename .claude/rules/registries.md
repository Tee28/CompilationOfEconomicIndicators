---
paths:
  - "config/**"
  - "rulebook/**"
  - "content/**"
---
# Registries, rulebook, content (YAML)

- YAML is validated by the PostToolUse hook after every edit; fix reported errors immediately.
- IDs are stable and UPPER_SNAKE for indicators/composites (`US_UNRATE_3M_CHG`), lowercase for sources and
  markets. Renaming an ID breaks the ledger: add a new one and deprecate the old (`deprecated: <date>`).
- config/sources.yaml: every source has license class + attribution text + key env + budget + fallback.
- config/hooks.json (JSON - hooks are stdlib-only): token guard, `owners`, `spawn`. Changing ownership is a
  main-thread decision; log it with `python econ.py log decision`.
- rulebook/<market>.yaml: schema in skill signal-rulebook. New rules start `status: candidate`; only the
  main thread sets `active` after Owner approval. Keep `evidence` and `tests` fields filled.
- phrases.*.yaml: slot templates only; no number written as text; banned words list lives in the file.
- Edit with small Edits; never rewrite a whole registry file.
