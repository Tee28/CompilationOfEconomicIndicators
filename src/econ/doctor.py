"""`econ doctor`: environment health (Python, venv, encoding, packages, FTS5, git, settings, keys, tools)."""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

from .common import ROOT, SECRET_ENV, Result, load_env, read_json

PACKAGES = ["yaml", "requests", "truststore", "pydantic", "numpy", "pandas", "pyarrow", "scipy", "statsmodels",
            "arch", "sklearn"]


def _ver(cmd: list[str]) -> str:
    exe = shutil.which(cmd[0])
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return ""


def run(args) -> Result:
    load_env()
    rows = []

    def add(status, name, detail):
        rows.append((status, name, detail))

    v = sys.version_info
    add("OK" if v >= (3, 12) else "FAIL", "python", f"{sys.version.split()[0]} at {sys.executable}")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    add("OK" if in_venv else "WARN", "venv", "active" if in_venv else "not active (create .venv: see README)")
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    add("OK" if "utf" in enc else "WARN", "stdout encoding", enc or "?")
    missing, versions = [], []
    for name in PACKAGES:
        try:
            m = importlib.import_module(name)
            versions.append(f"{name} {getattr(m, '__version__', '?')}")
        except Exception:
            missing.append(name)
    add("FAIL" if missing else "OK", "packages", ("missing: " + ", ".join(missing)) if missing else ", ".join(versions))
    try:
        sqlite3.connect(":memory:").execute("create virtual table t using fts5(x)")
        add("OK", "sqlite fts5", sqlite3.sqlite_version)
    except Exception as e:
        add("FAIL", "sqlite fts5", str(e))
    add("OK" if (ROOT / ".git").exists() else "WARN", "git repo", "yes" if (ROOT / ".git").exists() else "run git init")
    settings = read_json(ROOT / ".claude" / "settings.json", {}) or {}
    hooks = sorted((settings.get("hooks") or {}).keys())
    add("OK" if hooks else "WARN", "claude hooks", ", ".join(hooks) or "none configured yet")
    if "agent" in settings:
        add("WARN", "settings agent key", "present - it replaces Claude Code's default system prompt (plan v2 says no)")
    keys = {k: bool(os.environ.get(k)) for k in SECRET_ENV}
    add("OK" if keys.get("FRED_API_KEY") else "WARN", "api keys (.env)",
        " ".join(f"{k}={'set' if ok else '-'}" for k, ok in keys.items()))
    for tool in (["node", "--version"], ["npm", "--version"], ["gh", "--version"], ["claude", "--version"]):
        ver = _ver(tool)
        add("OK" if ver else "WARN", tool[0], ver or "not found")
    width = max(len(r[1]) for r in rows)
    text = "\n".join(f"{s:<4} {n:<{width}}  {d}" for s, n, d in rows)
    fails = sum(r[0] == "FAIL" for r in rows)
    return Result(text, [dict(zip(("status", "check", "detail"), r, strict=True)) for r in rows], 2 if fails else 0)


def to_json(rows) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=1)
