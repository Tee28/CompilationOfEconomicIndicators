# ADR 0001 - Live-slice data contracts and CLI wiring

## Status
Accepted (T001, schema_version 1.0.0). Supersede, never rewrite.

## Context
The P2 live slice (global macro, US equities, gold, oil) is built by several agents in parallel. They need one
contract for data crossing module boundaries, for the published site JSON, and for the ledger.

## Decision
- `src/econ/schemas.py` (pydantic v2, `extra=forbid`) is the single source: `Manifest`, `Overview`, `MarketPage`,
  `Health`, `ForecastRecord` (JSONL line), plus internal `IndicatorSeries` / `CompositeSeries`. `json_schema()`
  exports all schemas for TS generation into `web/src/types/` (never hand-edited).
- Licensing is enforced by types: `SiteSeries` with `license=internal` must have empty dates/values;
  `CompositeSummary` internal => `level=None`. Internal values live only in the internal interchange models.
- Charter rule in the schema: `HorizonForecast.confidence` must be `Low` when `skill.beats_baselines` is false.
- Ledger is append-only. Scoring appends a second line with the same `id` and outcome fields set; readers take
  the last line per `id`. `ledger verify` checks that old lines are byte-identical (hash chain / git history).
- Paths: raw store `data/` (`$ECON_DATA_DIR`, `--data-dir`), ledger `ledger/` (`--ledger-dir`), site JSON
  `web/public/data/`; `--out-dir D` redirects to `D/ledger` and `D/web/public/data`.
  Use `common.Paths.from_args(args)`.
- Site files: `<name>.<sha256[:8]>.json` + `manifest.json`; `files[].hash` is the full sha256 of the content.
- CLI handlers are `fn(args) -> Result` in the modules below, imported lazily by `cli._lazy`; a missing module
  or function prints `error: not implemented yet: econ.<mod>.<fn>` and exits 1.

### Module map (`args` carries `asof`, `data_dir`, `ledger_dir`, `out_dir`, `dry_run`)
| Command | Handler | Library API (owner) |
|---|---|---|
| `ind list [--market --license]` | `econ.registry.cmd_ind_list` | `registry.load() -> dict[str, IndicatorSpec]` (data-eng) |
| `ind get ID [--tail N]` | `econ.registry.cmd_ind_get` | `store.read(id, asof) -> IndicatorSeries` (vintage view) |
| `fetch [--id ..]` | `econ.connectors.cmd_fetch` | `connectors.fred.fetch(spec, since: date or None, budget) -> DataFrame`; `store.append(df, paths)` |
| `compute` | `econ.composites.cmd_compute` | `transforms.*`; `composites.compute(asof, paths) -> list[CompositeSeries]` |
| `forecast [--market ..]` | `econ.models.cmd_forecast` | `models.forecast(market, asof, paths) -> list[ForecastRecord]` (quant) |
| `ledger append/score/verify/health` | `econ.ledger.cmd_<name>` | `ledger.append(records, paths)`, `score(asof, paths)`, `verify(paths) -> list[str]`, `health(asof, paths) -> Health` |
| `publish` | `econ.publish.cmd_publish` | `publish.build(asof, paths) -> Manifest` (license gate, narrative) |
| `update [--dry-run]` | `econ.update.cmd_update` | fetch > compute > forecast > ledger append/score/health > publish; `--dry-run` writes nothing to ledger/ or site |

Exit codes: 0 ok, 1 error, 2 issues found (e.g. `ledger verify` detects a rewrite, license gate violation).

## Alternatives considered
- Hand-written TS types and sample JSON: drifts silently; rejected.
- Rewriting ledger lines in place when scoring: breaks append-only; rejected.
- All logic inside cli.py: couples the agents; rejected.

## Consequences
- Fixtures in `tests/fixtures/site/` are the frontend contract; regenerate them with every schema bump.
- Additive field = minor bump; rename/remove = major bump plus a migration note appended here.
- Producers must construct the models (validation is the contract test); `tests/test_schemas.py` guards the gate.
