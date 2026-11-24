"""Claude Code hooks. Stdlib only, fail-open (always exit 0), silent unless there is something to say.

Events (argv[0]):
  session-start : print the brief (<= 20 lines) that Claude Code adds to context
  pre-read      : token guard - deny off-limits paths and big text files read without offset/limit
  pre-write     : ownership guard - subagents may only Write/Edit files they own and spawn allowed agents
  post-edit     : validate edited config/rulebook files (JSON always, YAML when PyYAML is importable)
  subagent-stop : append (agent_type, agent_id, transcript) to work/activity.log; tokens are counted later
  pre-compact   : snapshot open work to work/compact-snapshot.md and print <= 5 lines for the summary
When .econ/probe/enabled exists, every event also dumps its payload for `python econ.py probe report`.
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
import traceback
from pathlib import Path

from .common import ROOT, STATE, WORK, clip, now, read_json, redact

HOOK_CFG = ROOT / "config" / "hooks.json"
PROBE = STATE / "probe"
SKIP_SIZE_CHECK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".ipynb"}
PROBE_ENV = ("CLAUDE_CODE_FORK_SUBAGENT", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", "PYTHONUTF8", "CLAUDE_PROJECT_DIR")


def _cfg() -> dict:
    return read_json(HOOK_CFG, {}) or {}


def _out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def _deny(reason: str):
    _out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def _rel(fp) -> str | None:
    try:
        return Path(fp).resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _match(rel: str, patterns) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns or [])


def _agent(data: dict) -> str:
    return str(data.get("agent_type") or "")


def _is_main(data: dict, c: dict) -> bool:
    return _agent(data) in set(c.get("main_agent_names", ["", "main"]))


# ---------------------------------------------------------------- probe support
def _probe_on() -> bool:
    return (PROBE / "enabled").exists()


def _probe_dump(event: str, data: dict):
    if not _probe_on():
        return
    d = PROBE / "payloads"
    d.mkdir(parents=True, exist_ok=True)
    agent = _agent(data) or "main"
    stem = f"{event}__{agent}__{data.get('tool_name') or ''}".replace("/", "_").replace("\\", "_")
    n = len(list(d.glob(stem + "__*.json")))
    if n >= 3:
        return
    slim = dict(data)
    ti = slim.get("tool_input")
    if isinstance(ti, dict):
        slim["tool_input"] = {k: (clip(v, 200) if isinstance(v, str) else v) for k, v in ti.items()}
    if isinstance(slim.get("last_assistant_message"), str):
        slim["last_assistant_message"] = clip(slim["last_assistant_message"], 400)
    payload = {"_event": event, "_ts": now(), "_python": sys.executable, "_version": sys.version.split()[0],
               "_stdout_encoding": getattr(sys.stdout, "encoding", ""), "_has_agent_type_key": "agent_type" in data,
               "_env": {k: os.environ.get(k) for k in PROBE_ENV}, "data": slim}
    (d / f"{stem}__{n + 1}.json").write_text(redact(json.dumps(payload, ensure_ascii=False, indent=1)),
                                             encoding="utf-8")


def _probe_mark(name: str, detail: dict):
    if not _probe_on():
        return
    d = PROBE / "marks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps({"ts": now(), **detail}, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- handlers
def session_start(data: dict):
    from .status import brief

    sys.stdout.write(brief()[:6000] + "\n")


def pre_read(data: dict):
    c = _cfg().get("token_guard", {})
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path")
    if not fp:
        return
    rel = _rel(fp)
    if rel and _match(rel, c.get("always_allow")):
        return
    sliced = bool(ti.get("limit") or ti.get("offset"))
    if rel:
        for pat, rule in (c.get("deny") or {}).items():
            if not fnmatch.fnmatch(rel, pat):
                continue
            rule = rule if isinstance(rule, dict) else {"hint": str(rule)}
            if rule.get("allow_slice") and sliced:
                return
            _deny(f"Token guard: {rel} is off-limits for a full Read. {rule.get('hint', '')}")
            _probe_mark("read-deny", {"path": rel, "agent": _agent(data) or "main", "why": "path"})
            return
    p = Path(fp)
    if not p.is_file() or p.suffix.lower() in SKIP_SIZE_CHECK:
        return
    size_kb = p.stat().st_size / 1024
    if size_kb > float(c.get("text_max_kb", 40)) and not sliced:
        _deny(f"Token guard: {p.name} is {size_kb:.0f}KB. Read a slice (offset/limit), or use the CLI first: "
              "`python econ.py status`, `context <role> <target>`, `ind get <ID>`, `digest <market>`, "
              "`kb search \"...\"`; for code see docs/CODEMAP.md.")
        _probe_mark("read-deny", {"path": rel or str(p), "agent": _agent(data) or "main", "why": "size",
                                  "kb": round(size_kb)})


def pre_write(data: dict):
    c = _cfg()
    if _is_main(data, c):
        return
    agent, tool = _agent(data), str(data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    if tool in ("Agent", "Task"):
        target = str(ti.get("subagent_type") or "general-purpose")
        allowed = (c.get("spawn") or {}).get(agent) or []
        if target not in allowed:
            _deny(f"Ownership guard: {agent} may not spawn '{target}' (allowed: {', '.join(allowed) or 'none'}). "
                  "Put the brief in your report and let your manager or the main thread dispatch it.")
            _probe_mark("spawn-deny", {"agent": agent, "target": target})
        return
    owners = c.get("owners") or {}
    if agent not in owners:
        return
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp:
        return
    rel = _rel(fp)
    if rel is None or not _match(rel, owners[agent]):
        _deny(f"Ownership guard: {agent} does not own {rel or fp}. Propose the change with "
              "`python econ.py notes add --target <path> --note \"...\"` or put it in your report.")
        _probe_mark("write-deny", {"agent": agent, "path": rel or str(fp)})


def post_edit(data: dict):
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path")
    if not fp:
        return
    p, rel = Path(fp), _rel(fp)
    if not rel or not p.is_file():
        return
    msgs = []
    if p.suffix == ".json" and (rel.startswith("config/") or rel.startswith(".claude/")):
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            msgs.append(f"{rel}: JSON error {clip(e, 160)}")
    elif p.suffix in (".yaml", ".yml") and rel.split("/")[0] in ("config", "rulebook", "content", "src"):
        try:
            import yaml
        except ImportError:
            return
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            msgs.append(f"{rel}: YAML error {clip(e, 200)}")
    if msgs:
        _out({"decision": "block", "reason": "Edit saved, but validation found problems - fix them:\n" + "\n".join(msgs)})


def subagent_stop(data: dict):
    c = _cfg()
    agent = _agent(data)
    if agent in set(c.get("main_agent_names", ["", "main"])):
        return  # Claude Code internal helper agents (prompt suggestions, /btw) - not ours
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "activity.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{now()} | {agent} | {data.get('agent_id') or ''} | {data.get('agent_transcript_path') or ''}\n")


def pre_compact(data: dict):
    from .status import compact_snapshot

    lines = compact_snapshot()
    sys.stdout.write("\n".join(lines[:5]) + "\n")


HANDLERS = {"session-start": session_start, "pre-read": pre_read, "pre-write": pre_write, "post-edit": post_edit,
            "subagent-stop": subagent_stop, "pre-compact": pre_compact}


def main(argv):
    event = argv[0] if argv else ""
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    except Exception:
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    fn = HANDLERS.get(event)
    if not fn:
        return
    try:
        _probe_dump(event, data)
    except Exception:
        pass
    try:
        fn(data)
    except Exception:
        try:
            STATE.mkdir(parents=True, exist_ok=True)
            with (STATE / "hook-errors.log").open("a", encoding="utf-8") as fh:
                fh.write(f"{now()} {event}\n{traceback.format_exc()}\n")
        except Exception:
            pass
