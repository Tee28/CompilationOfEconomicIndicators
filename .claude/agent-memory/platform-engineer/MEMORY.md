# platform-engineer memory (durable lessons only; <= 120 lines; curate, do not append forever)

- Windows path contains non-ASCII 'その他': hooks use exec form `python ${CLAUDE_PROJECT_DIR}/econ.py hook <ev>`,
  PYTHONUTF8=1, stdlib-only hooks (no venv re-exec).
- Skill `!` lines may run CONCURRENTLY - never depend on their order (P0 probe race, fixed by `probe enable --mark`).
- Ownership guard covers Write/Edit/Agent only; Bash can still write anywhere - check CLI writes in reviews.
- argparse global flags use default=SUPPRESS so `econ --json <cmd>` works.
