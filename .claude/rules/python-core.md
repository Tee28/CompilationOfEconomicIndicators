---
paths:
  - "src/econ/**"
  - "econ.py"
  - "tests/**"
---
# Python core (CLI, hooks, ledger)

- Python 3.13, deps only from requirements*.txt. Module map: docs/CODEMAP.md (`python econ.py codemap` after
  adding/removing modules or public functions).
- Commands return `Result(text, data, code)`: text <= 40 lines of IDs/paths, `data` for `--json`, exit
  0 ok / 1 error / 2 issues found. Raise `EconError` for user errors (one line, no traceback).
- Register subcommands with `parents=[common]` so `--json` / `--soft` work everywhere.
- `common.py`, `hooks.py`, `status.py` are imported by hooks: **stdlib only at import time** (yaml lazily).
  Hooks never exit non-zero and never print tracebacks; errors go to `.econ/hook-errors.log`.
- Shared files (work/*, config writes) go through `common.lock(...)` and atomic `write_json` / `save_yaml`.
- Windows + non-ASCII repo path: pathlib everywhere, UTF-8 I/O explicitly, pass paths as argv, never as shell strings.
- Never print secrets: run outbound URLs and log lines through `common.redact`.
- Every change adds or adjusts a test; `python -m pytest -q` must pass offline (no network in tests).
