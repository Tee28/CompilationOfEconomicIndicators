---
name: engineering-standards
description: Engineering standards - data contracts and JSON schemas, test pyramid, CI gates, ADRs, code review checklist and Definition of Done for this repo.
user-invocable: false
---
# Engineering standards

## Data contract (pipeline -> site)
- `econ publish` writes `web/public/data/manifest.json` + content-hashed files (`overview.<hash>.json`, ...).
- Each file has a JSON Schema in `src/econ/schemas.py` (pydantic models -> JSON Schema); TS types are
  generated (`json-schema-to-typescript`) into `web/src/types/`. Never hand-edit generated types.
- Contract change order: schema + version bump -> publisher -> generated types -> UI -> tests.
  Additive changes are minor; removing/renaming a field is major and needs a migration note.
- Manifest carries `schema_version`, `data_asof`, `generated_at`, file list with hashes and sizes.

## Test pyramid
| Layer | Where | What |
|---|---|---|
| unit | tests/unit | transforms, composites, rule DSL, scoring, redaction |
| golden | tests/golden | narrative text for fixed inputs; sign consistency text vs probability |
| contract | tests/contract | published JSON validates against schema; license-scan clean |
| hooks | tests/test_hooks.py | via subprocess: fail-open, guards, brief length |
| connectors | tests/connectors | fixtures only, no network |
| web | web/src/**/*.test.tsx | render each page with fixtures |
Rules: offline, deterministic (fixed seeds, `asof` injected), fast (< 60 s total locally).

## CI gates (ci.yml)
ruff · pytest · `econ audit` · `econ codemap --check` · schema validation · `ledger verify` ·
`license-scan` · redaction test · web typecheck + vitest + build + size budget.

## ADR (docs/adr/NNNN-kebab-title.md)
Context · Decision · Alternatives considered · Consequences · Status. One decision per ADR; supersede,
never rewrite.

## Code review checklist
1. Correctness: edge cases (empty series, NaN, holidays, DST/timezones - store dates in UTC/ISO).
2. As-of leaks: any use of data after the origin? full-sample statistics?
3. Contract drift: output shape changed without schema/version bump?
4. Licensing: can an `internal` value reach published output?
5. Secrets: keys in logs, fixtures, exceptions, URLs?
6. Windows: paths, encodings, shell quoting.
7. Token cost: does the command print > 40 lines by default? does an agent need to read big files?
8. Tests: new behaviour covered; failure paths covered.

## Definition of Done
Tests added and green · audit and codemap clean · docs/ARCHITECTURE.md or ADR updated if structure changed ·
no files outside the task's owner paths · report in the charter format.
