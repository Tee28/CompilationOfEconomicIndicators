"""Session brief and compaction snapshot. Stdlib only (called from hooks).

Sources (all optional; missing files are skipped):
  work/state.json      {"stage": "P0", "gates": {"G0": "open", ...}}
  work/tasks.json      {"tasks": [{"id","title","owner","status","deps"}]}  (managed by `econ task`)
  work/handoff.md      sections "## Next", "## Open questions"
  work/decisions.md    one decision per line, newest last
  ledger/health.json   {"asof", "sources": {"<id>": {"ok": bool, "fails": int}}}
"""
from __future__ import annotations

import re

from .common import LEDGER, WORK, clip, read_json, today

MAX_LINES = 20


def _section(md: str, title: str, n: int = 3) -> list[str]:
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", md, re.M | re.S)
    if not m:
        return []
    items = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith(("-", "*"))]
    return [clip(i.lstrip("-* "), 110) for i in items[:n]]


def _tasks() -> list[dict]:
    data = read_json(WORK / "tasks.json", {}) or {}
    return [t for t in data.get("tasks", []) if isinstance(t, dict)]


def ready_tasks(tasks: list[dict]) -> list[dict]:
    done = {t.get("id") for t in tasks if t.get("status") == "done"}
    return [t for t in tasks if t.get("status") in ("todo", "ready")
            and all(d in done for d in (t.get("deps") or []))]


def brief() -> str:
    state = read_json(WORK / "state.json", {}) or {}
    gates = state.get("gates") or {}
    gate_txt = " ".join(f"{k}:{v}" for k, v in gates.items()) or "none"
    out = [f"[ECON BRIEF] {today()} · stage {state.get('stage', 'P0')} · gates {gate_txt}"]

    health = read_json(LEDGER / "health.json")
    if health:
        srcs = health.get("sources") or {}
        bad = [k for k, v in srcs.items() if not (v or {}).get("ok", True)]
        out.append(f"Data: as of {health.get('asof', '?')} · sources {len(srcs) - len(bad)}/{len(srcs)} ok"
                   + (f" · failing: {', '.join(bad[:6])}" if bad else ""))
    else:
        out.append("Data: no pipeline run recorded yet (ledger/health.json missing).")

    tasks = _tasks()
    if tasks:
        open_ = [t for t in tasks if t.get("status") not in ("done", "dropped")]
        blocked = [t for t in open_ if t.get("status") == "blocked"]
        out.append(f"Tasks: {len(open_)} open · {len(blocked)} blocked")
        for t in ready_tasks(tasks)[:3]:
            out.append(f"  ready {t.get('id')}: {clip(t.get('title'), 70)} -> {t.get('owner', '?')}")

    hp = WORK / "handoff.md"
    if hp.exists():
        md = hp.read_text(encoding="utf-8")
        nxt = _section(md, "Next")
        if nxt:
            out.append("Handoff next:")
            out += [f"  - {x}" for x in nxt]
        ask = _section(md, "Open questions", 2)
        out += [f"  ? {x}" for x in ask]

    dp = WORK / "decisions.md"
    if dp.exists():
        lines = [ln.strip() for ln in dp.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("-")]
        if lines:
            out.append("Decisions: " + " | ".join(clip(x.lstrip("- "), 70) for x in lines[-2:]))

    out.append("Hint: start with `python econ.py status --full` or `context <role> <target>`; "
               "find code via docs/CODEMAP.md, never Glob/Grep the whole repo.")
    return "\n".join(out[:MAX_LINES])


def compact_snapshot() -> list[str]:
    """Write work/compact-snapshot.md and return short lines for the compaction summary."""
    tasks = _tasks()
    open_ = [t for t in tasks if t.get("status") not in ("done", "dropped")]
    lines = [f"Preserve: {len(open_)} open task(s): "
             + ", ".join(f"{t.get('id')} {clip(t.get('title'), 40)}" for t in open_[:4])]
    hp = WORK / "handoff.md"
    nxt = _section(hp.read_text(encoding="utf-8"), "Next") if hp.exists() else []
    if nxt:
        lines.append("Handoff next: " + " | ".join(nxt))
    lines.append("Full snapshot: work/compact-snapshot.md (re-read after compaction instead of exploring).")
    WORK.mkdir(parents=True, exist_ok=True)
    body = ["# Compact snapshot", "", *[f"- {x}" for x in lines], "", "## Open tasks",
            *[f"- {t.get('id')} [{t.get('status')}] {t.get('title')} -> {t.get('owner')}" for t in open_]]
    (WORK / "compact-snapshot.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    return lines
