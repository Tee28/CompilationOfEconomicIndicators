# engineering-manager memory (durable lessons only; <= 120 lines; curate, do not append forever)

- Dispatch from `python econ.py task next`; max 4 nested tasks per message.
- Nested spawn verified by the P0 probe (2026-11-24): a manager waits for nested results; depth limit 2.
- Specialists cannot spawn agents or ask the Owner - collect their ASK lines into your report.
