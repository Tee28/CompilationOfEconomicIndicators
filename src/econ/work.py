"""Work ledger: task DAG, review notes, handoff, decisions, gates, activity/token log.

Files (all in work/):
  tasks.json     {"tasks": [{id, title, owner, deps, inputs, outputs, status, note, created, updated}]}
  notes.csv      id,target,author,note,status,ts           (proposals for files the author does not own)
  handoff.md     sections Done / In progress / Next / Open questions (<= audit.handoff_lines)
  decisions.md   "- YYYY-MM-DD | by | gate | decision" (append-only, newest last)
  state.json     {"stage": "P1", "gates": {"G0": "approved", ...}}
  activity.log   "ts | agent_type | agent_id | transcript" (SubagentStop hook); tokens parsed on demand
JSON for tasks/state because the SessionStart brief (stdlib only) reads them.
"""
from __future__ import annotations

import csv
import re

from .common import ROOT, WORK, EconError, Result, cfg, clip, lock, now, read_json, today, write_json

TASKS = WORK / "tasks.json"
NOTES = WORK / "notes.csv"
HANDOFF = WORK / "handoff.md"
DECISIONS = WORK / "decisions.md"
STATE_F = WORK / "state.json"
ACTIVITY = WORK / "activity.log"
NOTE_FIELDS = ["id", "target", "author", "note", "status", "ts"]
TASK_STATUS = ("todo", "doing", "review", "done", "blocked", "dropped")
GATES = {"G0": "Scope & verification", "G1": "Live slice", "G2": "Data & indicators", "G3": "Models",
         "G4": "Full website"}


def _split(s) -> list[str]:
    return [x.strip() for x in re.split(r"[,;]\s*", s or "") if x.strip()]


# ---------------------------------------------------------------- tasks
def load_tasks() -> list[dict]:
    return [t for t in (read_json(TASKS, {}) or {}).get("tasks", []) if isinstance(t, dict)]


def _save_tasks(tasks):
    write_json(TASKS, {"tasks": tasks})


def _ready(tasks):
    done = {t["id"] for t in tasks if t.get("status") == "done"}
    return [t for t in tasks if t.get("status") == "todo" and all(d in done for d in t.get("deps", []))]


def _line(t) -> str:
    return (f"{t['id']} [{t.get('status')}] {t.get('owner')}: {clip(t.get('title'), 70)}"
            + (f" (deps {','.join(t['deps'])})" if t.get("deps") else ""))


def task_add(a) -> Result:
    with lock("tasks"):
        tasks = load_tasks()
        n = max([int(t["id"][1:]) for t in tasks if re.match(r"T\d+$", str(t.get("id")))] + [0]) + 1
        tid, deps = f"T{n:03d}", _split(a.deps)
        bad = [d for d in deps if d not in {t["id"] for t in tasks}]
        if bad:
            raise EconError(f"unknown deps: {', '.join(bad)}")
        tasks.append({"id": tid, "title": a.title, "owner": a.owner, "deps": deps, "inputs": _split(a.inputs),
                      "outputs": _split(a.outputs), "status": "todo", "note": a.note or "", "created": now(),
                      "updated": now()})
        _save_tasks(tasks)
    return Result(f"{tid} added -> {a.owner}: {clip(a.title, 80)}", {"id": tid})


def task_list(a) -> Result:
    sel = [t for t in load_tasks() if (a.all or t.get("status") not in ("done", "dropped"))
           and (not a.owner or t.get("owner") == a.owner)]
    return Result("\n".join(_line(t) for t in sel[-40:]) or "no tasks", sel)


def task_next(a) -> Result:
    ready = _ready(load_tasks())[: a.limit]
    lines = [f"{t['id']} {t.get('owner')}: {clip(t.get('title'), 80)} | in: {', '.join(t.get('inputs') or []) or '-'}"
             f" | out: {', '.join(t.get('outputs') or []) or '-'}" for t in ready]
    return Result("\n".join(lines) or "nothing ready (check doing/blocked tasks)", ready)


def task_get(a) -> Result:
    t = next((x for x in load_tasks() if x["id"] == a.id), None)
    if not t:
        raise EconError(f"no task {a.id}")
    keys = ("title", "owner", "status", "deps", "inputs", "outputs", "note", "updated")
    return Result("\n".join(f"{k}: {t.get(k)}" for k in keys if t.get(k)), t)


def task_set(a) -> Result:
    status = "done" if getattr(a, "done", False) else a.status
    if status and status not in TASK_STATUS:
        raise EconError(f"status must be one of {', '.join(TASK_STATUS)}")
    with lock("tasks"):
        tasks = load_tasks()
        t = next((x for x in tasks if x["id"] == a.id), None)
        if not t:
            raise EconError(f"no task {a.id}")
        for k, v in (("status", status), ("note", a.note), ("owner", getattr(a, "owner", None))):
            if v:
                t[k] = v
        t["updated"] = now()
        _save_tasks(tasks)
    unblocked = [x["id"] for x in _ready(tasks) if a.id in x.get("deps", [])] if status == "done" else []
    return Result(f"{a.id} -> {t['status']}" + (f" · now ready: {', '.join(unblocked)}" if unblocked else ""), t)


# ---------------------------------------------------------------- notes
def _notes() -> list[dict]:
    if not NOTES.exists():
        return []
    with NOTES.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_notes(rows):
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    with NOTES.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=NOTE_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def open_notes(prefix: str = "") -> list[dict]:
    return [r for r in _notes() if r.get("status") == "open"
            and (not prefix or r.get("target", "").startswith(prefix) or prefix.startswith(r.get("target") or "\0"))]


def notes_add(a) -> Result:
    with lock("notes"):
        rows = _notes()
        n = max([int(r["id"][1:]) for r in rows if re.match(r"N\d+$", r.get("id", ""))] + [0]) + 1
        nid = f"N{n:03d}"
        rows.append({"id": nid, "target": a.target, "author": a.author or "main", "note": a.note, "status": "open",
                     "ts": now()})
        _write_notes(rows)
    return Result(f"{nid} -> {a.target}", {"id": nid})


def notes_list(a) -> Result:
    rows = _notes() if a.all else open_notes()
    if a.target:
        rows = [r for r in rows if r.get("target", "").startswith(a.target)]
    lines = [f"{r['id']} [{r['status']}] {r['target']} ({r['author']}): {clip(r['note'], 90)}" for r in rows[-40:]]
    return Result("\n".join(lines) or "no notes", rows)


def notes_resolve(a) -> Result:
    with lock("notes"):
        rows = _notes()
        hit = 0
        for r in rows:
            if r.get("id") in a.ids:
                r["status"], hit = a.status, hit + 1
        _write_notes(rows)
    return Result(f"{hit} note(s) -> {a.status}", {"updated": hit})


# ---------------------------------------------------------------- handoff / decisions
def handoff_show(a) -> Result:
    return Result(HANDOFF.read_text(encoding="utf-8").strip() if HANDOFF.exists() else "no handoff yet")


def handoff_set(a) -> Result:
    limit = int(cfg("audit.handoff_lines", 30))
    lines = [f"# Handoff - {today()}", ""]
    for title, items in (("Done", a.done), ("In progress", a.doing), ("Next", a.next), ("Open questions", a.ask)):
        if items:
            lines += [f"## {title}", *[f"- {clip(i, 160)}" for i in items], ""]
    if len(lines) > limit:
        lines = lines[: limit - 1] + ["- (truncated: keep the handoff short)"]
    WORK.mkdir(parents=True, exist_ok=True)
    HANDOFF.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return Result(f"handoff written ({len(lines)} lines)")


def log_decision(a) -> Result:
    if not DECISIONS.exists():
        DECISIONS.write_text("# Decisions (newest last; one line each: - YYYY-MM-DD | by | gate | decision)\n",
                             encoding="utf-8")
    with lock("decisions"), DECISIONS.open("a", encoding="utf-8") as fh:
        fh.write(f"- {today()} | {a.by} | {a.gate or '-'} | {clip(a.text, 300)}\n")
    return Result("decision logged")


# ---------------------------------------------------------------- activity / tokens
def _activity() -> list[list[str]]:
    if not ACTIVITY.exists():
        return []
    rows = [[x.strip() for x in ln.split("|")] for ln in ACTIVITY.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if len(r) >= 4]


def log_tail(a) -> Result:
    rows = _activity()[-a.n:]
    return Result("\n".join(f"{r[0]} {r[1]} {r[2]}" for r in rows) or "no activity yet", rows)


def log_tokens(a) -> Result:
    from .probe import transcript_tokens

    agg: dict[str, dict] = {}
    seen = set()
    for ts, agent, aid, path in (r[:4] for r in _activity()):
        if (a.since and ts < a.since) or (aid, path) in seen:
            continue
        seen.add((aid, path))
        t = transcript_tokens(path)
        g = agg.setdefault(agent or "?", {"runs": 0, "in": 0, "out": 0, "cache_r": 0, "cache_w": 0, "missing": 0})
        g["runs"] += 1
        g["missing"] += 0 if t["messages"] else 1
        for k in ("in", "out", "cache_r", "cache_w"):
            g[k] += t[k]
    if not agg:
        return Result("no subagent runs logged yet (SubagentStop hook writes work/activity.log)", {})
    rows = sorted(agg.items(), key=lambda kv: -(kv[1]["out"] + kv[1]["cache_w"] + kv[1]["in"]))
    lines = ["agent | runs | in | out | cache_read | cache_write" + (" | no-transcript" if any(
        v["missing"] for v in agg.values()) else "")]
    lines += [f"{k} | {v['runs']} | {v['in']} | {v['out']} | {v['cache_r']} | {v['cache_w']}"
              + (f" | {v['missing']}" if v["missing"] else "") for k, v in rows]
    return Result("\n".join(lines), agg)


# ---------------------------------------------------------------- gates
def _exists(*paths) -> bool:
    return all((ROOT / p).exists() for p in paths)


def _probe_ok() -> list[str]:
    from .probe import PROBE

    return [] if (PROBE / "payloads").exists() or _exists("docs/ARCHITECTURE.md") else ["run /econ-probe"]


def gate_missing(gid: str) -> list[str]:
    """Deterministic pre-checks. The owner still reviews and approves; an empty list only means 'ready for review'."""
    miss: list[str] = []
    if gid == "G0":
        miss += _probe_ok()
        if not _exists("docs/source-verification.md"):
            miss.append("docs/source-verification.md (run src-check workflow)")
    elif gid == "G1":
        for p in ("ledger/health.json", "ledger/forecasts", "web/package.json", ".github/workflows/update-data.yml"):
            if not _exists(p):
                miss.append(p)
    elif gid == "G2":
        for p in ("config/indicators.yaml", "config/composites.yaml", "config/calendar.yaml"):
            if not _exists(p):
                miss.append(p)
    elif gid == "G3":
        for pat, what in (("docs/models/*.md", "model cards"), ("docs/risk/*.md", "red-team review")):
            if not any(ROOT.glob(pat)):
                miss.append(f"{pat} ({what})")
    elif gid == "G4":
        if not _exists("web/package.json"):
            miss.append("web/")
    else:
        raise EconError(f"unknown gate {gid} (known: {', '.join(GATES)})")
    return miss


def gate_check(a) -> Result:
    state = read_json(STATE_F, {}) or {}
    gids = [a.gate] if a.gate else list(GATES)
    lines, data = [], {}
    for g in gids:
        st = (state.get("gates") or {}).get(g, "open")
        miss = [] if st == "approved" else gate_missing(g)
        data[g] = {"status": st, "missing": miss}
        lines.append(f"{g} {GATES.get(g, '')}: {st}" + ("" if st == "approved" else
                     (" · READY for owner review" if not miss else " · missing: " + "; ".join(miss[:5]))))
    return Result("\n".join(lines), data, code=2 if any(v["missing"] for v in data.values()) else 0)


def gate_approve(a) -> Result:
    if a.gate not in GATES:
        raise EconError(f"unknown gate {a.gate}")
    miss = gate_missing(a.gate)
    if miss and not a.force:
        raise EconError(f"{a.gate} pre-checks fail: {'; '.join(miss)} (owner may override with --force)")
    with lock("state"):
        state = read_json(STATE_F, {}) or {}
        state.setdefault("gates", {})[a.gate] = "approved"
        if a.stage:
            state["stage"] = a.stage
        write_json(STATE_F, state)
    a.by, a.gate, a.text = "Owner", a.gate, f"{a.gate} approved" + (f": {a.note}" if a.note else "")
    log_decision(a)
    return Result(f"{a.gate} approved" + (f" · stage -> {a.stage}" if a.stage else ""))


def stage_set(a) -> Result:
    with lock("state"):
        state = read_json(STATE_F, {}) or {}
        state["stage"] = a.stage
        for g in GATES:
            state.setdefault("gates", {}).setdefault(g, "open")
        write_json(STATE_F, state)
    return Result(f"stage -> {a.stage}")


def register(sub, common):
    """Add task/notes/handoff/log/gate/stage subcommands to the CLI parser."""
    def grp(name, help_):
        return sub.add_parser(name, parents=[common], help=help_).add_subparsers(dest="sub", required=True)

    t = grp("task", "task DAG (managers dispatch from `task next`)")
    x = t.add_parser("add", parents=[common])
    x.add_argument("--title", required=True)
    x.add_argument("--owner", required=True)
    x.add_argument("--deps", default="")
    x.add_argument("--inputs", default="")
    x.add_argument("--outputs", default="")
    x.add_argument("--note", default="")
    x.set_defaults(fn=task_add)
    x = t.add_parser("list", parents=[common])
    x.add_argument("--owner")
    x.add_argument("--all", action="store_true")
    x.set_defaults(fn=task_list)
    x = t.add_parser("next", parents=[common])
    x.add_argument("--limit", type=int, default=4)
    x.set_defaults(fn=task_next)
    x = t.add_parser("get", parents=[common])
    x.add_argument("id")
    x.set_defaults(fn=task_get)
    for name in ("set", "done"):
        x = t.add_parser(name, parents=[common])
        x.add_argument("id")
        x.add_argument("--status", choices=TASK_STATUS) if name == "set" else None
        x.add_argument("--note")
        x.add_argument("--owner") if name == "set" else None
        x.set_defaults(fn=task_set, done=name == "done", status=None)

    n = grp("notes", "review notes / change proposals for files you do not own")
    x = n.add_parser("add", parents=[common])
    x.add_argument("--target", required=True)
    x.add_argument("--note", required=True)
    x.add_argument("--author", default="")
    x.set_defaults(fn=notes_add)
    x = n.add_parser("list", parents=[common])
    x.add_argument("--target")
    x.add_argument("--all", action="store_true")
    x.set_defaults(fn=notes_list)
    x = n.add_parser("resolve", parents=[common])
    x.add_argument("ids", nargs="+")
    x.add_argument("--status", default="addressed", choices=("addressed", "rejected", "open"))
    x.set_defaults(fn=notes_resolve)

    h = grp("handoff", "session handoff (main thread)")
    h.add_parser("show", parents=[common]).set_defaults(fn=handoff_show)
    x = h.add_parser("set", parents=[common])
    for k in ("done", "doing", "next", "ask"):
        x.add_argument(f"--{k}", action="append", default=[])
    x.set_defaults(fn=handoff_set)

    lg = grp("log", "decisions and subagent activity")
    x = lg.add_parser("decision", parents=[common])
    x.add_argument("text")
    x.add_argument("--by", default="Owner")
    x.add_argument("--gate", default="")
    x.set_defaults(fn=log_decision)
    x = lg.add_parser("tail", parents=[common])
    x.add_argument("-n", type=int, default=10)
    x.set_defaults(fn=log_tail)
    x = lg.add_parser("tokens", parents=[common], help="token usage per agent, parsed from transcripts")
    x.add_argument("--since", default="", help="ISO timestamp prefix, e.g. 2026-11-24")
    x.set_defaults(fn=log_tokens)

    g = grp("gate", "phase gates: deterministic check, then owner approval")
    x = g.add_parser("check", parents=[common])
    x.add_argument("gate", nargs="?")
    x.set_defaults(fn=gate_check)
    x = g.add_parser("approve", parents=[common], help="main thread only, after the owner said yes")
    x.add_argument("gate")
    x.add_argument("--note", default="")
    x.add_argument("--stage", default="")
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=gate_approve)

    x = sub.add_parser("stage", parents=[common], help="set the current phase (P0..P7)")
    x.add_argument("stage")
    x.set_defaults(fn=stage_set)

