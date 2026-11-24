"""P0 probe of Claude Code behaviour on this machine (hooks, agent_type, nested spawning, skills, tokens).

Flow (driven by the /econ-probe skill in a fresh session):
  probe enable  -> flag + nonce + a 64KB file for the Read-deny test; hooks start dumping payloads
  (Claude reads the big file, runs probe-manager which spawns probe-worker, the skill's `!` line runs `probe mark`)
  probe report  -> PASS/FAIL per check, with the fallback to use when a check fails
  probe disable -> stop dumping
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
from pathlib import Path

from .common import STATE, Result, now, read_json

PROBE = STATE / "probe"


def enable(args) -> Result:
    if PROBE.exists():
        shutil.rmtree(PROBE, ignore_errors=True)
    (PROBE / "payloads").mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_hex(3)
    (PROBE / "enabled").write_text(nonce, encoding="utf-8")
    (PROBE / "big.txt").write_text(("probe line for the token guard test\n" * 1800), encoding="utf-8")
    if getattr(args, "mark", None):  # skill `!` lines may run concurrently: a separate mark line races the rmtree
        _write_mark(args.mark)
    return Result(f"probe enabled · nonce {nonce} · big file .econ/probe/big.txt (64KB)", {"nonce": nonce})


def disable(args) -> Result:
    (PROBE / "enabled").unlink(missing_ok=True)
    return Result("probe disabled (dumps kept in .econ/probe/)")


def mark(args) -> Result:
    _write_mark(args.name)
    return Result(f"probe mark '{args.name}' recorded")


def _write_mark(name: str):
    d = PROBE / "marks"
    d.mkdir(parents=True, exist_ok=True)
    info = {"ts": now(), "python": sys.executable, "cwd": os.getcwd(),
            "shell": {k: os.environ.get(k) for k in ("SHELL", "MSYSTEM", "ComSpec", "PSModulePath") if os.environ.get(k)}}
    info["shell"] = {k: (v[:60] if isinstance(v, str) else v) for k, v in info["shell"].items()}
    (d / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def transcript_tokens(path: str) -> dict:
    """Sum usage in a transcript JSONL, keeping the last usage per message id (ids repeat while streaming)."""
    tot = {"in": 0, "out": 0, "cache_r": 0, "cache_w": 0, "messages": 0}
    p = Path(os.path.expanduser(path or ""))
    if not path or not p.is_file():
        return tot
    last: dict = {}
    with p.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else None
            if msg and isinstance(msg.get("usage"), dict):
                last[msg.get("id") or f"_{i}"] = msg["usage"]
    for u in last.values():
        tot["in"] += int(u.get("input_tokens") or 0)
        tot["out"] += int(u.get("output_tokens") or 0)
        tot["cache_r"] += int(u.get("cache_read_input_tokens") or 0)
        tot["cache_w"] += int(u.get("cache_creation_input_tokens") or 0)
    tot["messages"] = len(last)
    return tot


def transcript_replies(path: str) -> str:
    """All text an agent sent back: assistant text blocks plus any tool_use `input.message`
    (the final report may arrive via a hand-back tool call instead of plain text)."""
    p = Path(os.path.expanduser(path or ""))
    if not path or not p.is_file():
        return ""
    out = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else None
            if not msg or msg.get("role") != "assistant" or not isinstance(msg.get("content"), list):
                continue
            for b in msg["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    out.append(str(b.get("text") or ""))
                elif b.get("type") == "tool_use" and isinstance(b.get("input"), dict):
                    out.append(str(b["input"].get("message") or ""))
    return "\n".join(out)


def _payloads() -> list[dict]:
    out = []
    for f in sorted((PROBE / "payloads").glob("*.json")):
        d = read_json(f)
        if isinstance(d, dict):
            out.append(d)
    return out


def report(args) -> Result:
    nonce = (PROBE / "enabled").read_text(encoding="utf-8").strip() if (PROBE / "enabled").exists() else ""
    pls = _payloads()
    marks = {f.stem: read_json(f, {}) for f in (PROBE / "marks").glob("*.json")} if (PROBE / "marks").exists() else {}

    def ev(name):
        return [p for p in pls if p.get("_event") == name]

    def agent_of(p):
        return (p.get("data") or {}).get("agent_type") or ""

    pre = ev("pre-read") + ev("pre-write")
    stops = ev("subagent-stop")
    checks = []

    def add(name, status, detail, fallback=""):
        checks.append({"check": name, "status": status, "detail": detail, "fallback": fallback if status != "PASS" else ""})

    add("hooks fire", "PASS" if pls else "FAIL", f"{len(pls)} payload(s): " + ", ".join(sorted({p['_event'] for p in pls})),
        "Hooks not loaded: start a NEW session after editing .claude/settings.json; check /hooks.")
    py = next((p for p in pls), {})
    add("hook python", "PASS" if py.get("_version") else "SKIP",
        f"{py.get('_python', '?')} {py.get('_version', '')} stdout={py.get('_stdout_encoding', '')}",
        "Hooks must stay stdlib-only (system python may lack packages).")
    main_pre = [p for p in pre if not agent_of(p)]
    add("main thread has no agent_type", "PASS" if main_pre else "SKIP",
        f"{len(main_pre)} main-thread PreToolUse payload(s); agent_type key present: "
        f"{any(p.get('_has_agent_type_key') for p in main_pre)}",
        "Read a file from the main thread while the probe is enabled.")
    sub_pre = sorted({agent_of(p) for p in pre if agent_of(p)})
    add("subagent tool calls carry agent_type", "PASS" if sub_pre else "FAIL", ", ".join(sub_pre) or "none seen",
        "Ownership guard cannot work by hook: enforce ownership in prompts + post-hoc `git diff` review.")
    add("token guard denies big Read", "PASS" if "read-deny" in marks else "FAIL",
        json.dumps(marks.get("read-deny", {}), ensure_ascii=False)[:120],
        "Check the PreToolUse Read hook matcher and config/hooks.json token_guard.")
    add("ownership guard denies foreign write", "PASS" if "write-deny" in marks else "FAIL",
        json.dumps(marks.get("write-deny", {}), ensure_ascii=False)[:120],
        "Check the PreToolUse Write|Edit hook and config/hooks.json owners (needs probe-worker: new session).")
    add("spawn guard denies unlisted spawn", "PASS" if "spawn-deny" in marks else "FAIL",
        json.dumps(marks.get("spawn-deny", {}), ensure_ascii=False)[:120],
        "Check the PreToolUse Agent|Task matcher and config/hooks.json spawn.")
    worker_stop = [p for p in stops if agent_of(p) == "probe-worker"]
    mgr_stop = [p for p in stops if agent_of(p) == "probe-manager"]
    mgr_msg = " ".join(str((p.get("data") or {}).get("last_assistant_message") or "") + " "
                       + transcript_replies((p.get("data") or {}).get("agent_transcript_path") or "")
                       for p in mgr_stop)
    if worker_stop and nonce and f"WORKER-OK-{nonce}" in mgr_msg:
        add("nested spawn + manager waits", "PASS", "probe-manager received probe-worker's token")
    elif worker_stop:
        add("nested spawn + manager waits", "WARN", "worker ran but manager did not report its token (no wait?)",
            "Managers return briefs; the main thread dispatches and collects (no nested waits).")
    else:
        add("nested spawn + manager waits", "FAIL", f"probe-manager stops: {len(mgr_stop)}, worker stops: 0",
            "No nesting: managers plan only and return briefs; the main thread dispatches specialists.")
    fields = {"agent_type", "agent_id", "agent_transcript_path"}
    have = fields & set().union(*[(p.get("data") or {}).keys() for p in stops]) if stops else set()
    add("SubagentStop fields", "PASS" if have == fields else ("FAIL" if stops else "SKIP"),
        f"present: {', '.join(sorted(have)) or 'none'}", "Log agent name only; skip token accounting.")
    tok = {"in": 0, "out": 0, "cache_r": 0, "cache_w": 0, "messages": 0}
    for p in stops:
        t = transcript_tokens((p.get("data") or {}).get("agent_transcript_path") or "")
        for k in tok:
            tok[k] += t[k]
    add("transcript token parse", "PASS" if tok["messages"] and (tok["in"] + tok["out"]) > 0 else
        ("FAIL" if stops else "SKIP"), json.dumps(tok),
        "Transcript format differs: inspect one transcript line and adapt transcript_tokens().")
    sk = marks.get("skill-bang")
    add("skill `!` command runs", "PASS" if sk else "FAIL",
        (json.dumps(sk.get("shell", {}), ensure_ascii=False)[:120] if sk else "no mark"),
        "Allow `Bash(python econ.py *)` and use `shell: bash`; else move the step into the skill body.")
    env = next((p.get("_env") for p in pls if p.get("_env")), {}) or {}
    add("env seen by hooks", "INFO", json.dumps(env, ensure_ascii=False)[:160])

    width = max(len(c["check"]) for c in checks)
    lines = [f"{c['status']:<5} {c['check']:<{width}}  {c['detail']}" + (f"\n      -> fallback: {c['fallback']}"
                                                                        if c["fallback"] else "") for c in checks]
    fails = sum(c["status"] == "FAIL" for c in checks)
    lines.append(f"nonce {nonce or '-'} · {len(pls)} payloads · {fails} FAIL · dumps in .econ/probe/")
    return Result("\n".join(lines), {"nonce": nonce, "checks": checks}, 2 if fails else 0)
