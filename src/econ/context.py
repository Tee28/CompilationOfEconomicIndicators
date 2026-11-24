"""`econ context <role> <target>`: a minimal context pack (<= 40 lines) so an agent starts a task without exploring.

target: a task id (T012), a repo path or path prefix (src/econ/work.py, rulebook/), a market (us-equities),
or "-" for the role's general view. The pack lists: the task, owned paths, open tasks/notes, matching CODEMAP
lines, path rules that will load, memory file size and KB hits. It never inlines file contents.
"""
from __future__ import annotations

import fnmatch
import re

from .common import ROOT, Result, clip, read_json
from .work import load_tasks, open_notes

MAX_LINES = 40


def _owners() -> dict:
    return (read_json(ROOT / "config" / "hooks.json", {}) or {}).get("owners") or {}


def _rule_globs() -> dict[str, list[str]]:
    out = {}
    for r in sorted((ROOT / ".claude" / "rules").glob("*.md")):
        m = re.match(r"^---\r?\n(.*?)\r?\n---", r.read_text(encoding="utf-8"), re.S)
        if m:
            out[r.stem] = re.findall(r"^\s*-\s*[\"']?([^\"'\n]+)[\"']?\s*$", m.group(1), re.M)
    return out


def _glob_match(path: str, pat: str) -> bool:
    return fnmatch.fnmatch(path, pat.replace("**/", "*").replace("/**", "/*")) or path.startswith(pat.split("*")[0]
                                                                                                    or "\0")


def build(role: str, target: str) -> list[str]:
    out = [f"[CONTEXT] role {role} · target {target}"]
    tasks = load_tasks()
    path_hint = target
    m = re.match(r"^T\d{3,}$", target)
    if m:
        t = next((x for x in tasks if x["id"] == target), None)
        if t:
            out.append(f"Task {t['id']} [{t.get('status')}] {clip(t.get('title'), 100)}")
            if t.get("inputs"):
                out.append(f"  inputs: {', '.join(t['inputs'])}")
            if t.get("outputs"):
                out.append(f"  outputs: {', '.join(t['outputs'])}")
                path_hint = t["outputs"][0]
            if t.get("note"):
                out.append(f"  note: {clip(t['note'], 120)}")
        else:
            out.append(f"Task {target}: not found")
    owned = _owners().get(role)
    if owned:
        out.append("You own: " + ", ".join(owned[:12]) + (" …" if len(owned) > 12 else ""))
    elif role not in ("main", "-"):
        out.append("You own: (no Write/Edit restrictions configured)")
    mine = [t for t in tasks if t.get("owner") == role and t.get("status") not in ("done", "dropped")]
    if mine:
        out.append("Your open tasks: " + "; ".join(f"{t['id']} [{t['status']}] {clip(t['title'], 40)}" for t in mine[:4]))
    notes = open_notes(path_hint if path_hint not in ("-", "") else "")
    if notes:
        out.append(f"Open notes ({len(notes)}):")
        out += [f"  {n['id']} {n['target']} ({n['author']}): {clip(n['note'], 90)}" for n in notes[:4]]
    if path_hint and path_hint != "-" and ("/" in path_hint or "." in path_hint):
        cm = ROOT / "docs" / "CODEMAP.md"
        if cm.exists():
            hits = [ln for ln in cm.read_text(encoding="utf-8").splitlines() if ln.startswith("- `")
                    and path_hint.split("*")[0] in ln]
            if hits:
                out.append("CODEMAP:")
                out += [f"  {clip(h[2:], 150)}" for h in hits[:8]]
        rules = [name for name, globs in _rule_globs().items() if any(_glob_match(path_hint, g) for g in globs)]
        if rules:
            out.append("Path rules that load when you touch it: " + ", ".join(rules))
    mem = ROOT / ".claude" / "agent-memory" / role / "MEMORY.md"
    if mem.exists():
        out.append(f"Memory: {mem.relative_to(ROOT).as_posix()} ({len(mem.read_text(encoding='utf-8').splitlines())} lines)")
    title = next((x["title"] for x in tasks if x["id"] == target), "") if m else target
    kw = re.sub(r"[/_.\-]+", " ", "" if title == "-" else title)
    if kw.strip() and (ROOT / "knowledge").exists():
        try:
            from .kb import search

            hits = search(kw, 3)
            if hits:
                out.append("KB: " + "; ".join(f"{h['path']} ({h['status']})" for h in hits))
        except Exception:
            pass
    out.append("Report back with: STATUS | WROTE | NOTES <=3 | NEXT | ASK (<= 8 lines).")
    return out[:MAX_LINES]


def run(args) -> Result:
    lines = build(args.role, args.target or "-")
    return Result("\n".join(lines), {"lines": lines})
