"""Shared helpers: paths, config, JSON/YAML I/O, locks, text, secrets redaction.

Import-time stdlib only: hooks import this module and must never pull in third-party packages.
YAML is imported lazily inside the functions that need it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(os.environ.get("ECON_ROOT") or Path(__file__).resolve().parents[2])
STATE = ROOT / ".econ"
CONFIG = ROOT / "config"
WORK = ROOT / "work"
DOCS = ROOT / "docs"
KNOWLEDGE = ROOT / "knowledge"
LEDGER = ROOT / "ledger"

SECRET_ENV = ("FRED_API_KEY", "EIA_API_KEY", "COINGECKO_API_KEY", "ESTAT_APP_ID", "DATA_REPO_TOKEN")
_SECRET_PARAM_RE = re.compile(r"(?i)\b(api_key|apikey|appid|key|token|x-cg-demo-api-key)=([^&\s\"']+)")


class EconError(Exception):
    """User-facing error: printed as one line without traceback, exit code 1."""


class Result:
    """Command result: `text` for humans/agents, `data` for --json, `code` exit status (2 = issues found)."""

    def __init__(self, text: str = "", data=None, code: int = 0):
        self.text, self.data, self.code = text, data, code


# ---------------------------------------------------------------- time / text
def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def utcnow() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def today() -> str:
    return dt.date.today().isoformat()


def clip(s, n: int = 80) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def est_tokens(text: str) -> int:
    """Rough token estimate: ~4 ASCII chars/token; non-ASCII (Vietnamese diacritics, CJK) costs more."""
    ascii_n = sum(1 for c in text if ord(c) < 128)
    return int(ascii_n / 4 + (len(text) - ascii_n) * 0.8) + 1


def redact(text) -> str:
    """Remove secrets from URLs/log lines: query params like api_key=..., and any known secret env value."""
    s = _SECRET_PARAM_RE.sub(lambda m: f"{m.group(1)}=***", str(text or ""))
    for name in SECRET_ENV:
        v = os.environ.get(name, "")
        if len(v) >= 6:
            s = s.replace(v, "***")
    return s


# ---------------------------------------------------------------- JSON / YAML
def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, data, indent: int | None = 1):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    os.replace(tmp, p)


def load_yaml(path, default=None):
    import yaml

    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data if data is not None else ({} if default is None else default)


def save_yaml(path, data):
    import yaml

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------- config / env
_CFG: dict = {}


def config(name: str = "econ") -> dict:
    if name not in _CFG:
        _CFG[name] = load_yaml(CONFIG / f"{name}.yaml")
    return _CFG[name]


def cfg(path: str, default=None, name: str = "econ"):
    cur = config(name)
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return default if cur is None else cur


def load_env():
    """Load ROOT/.env into os.environ (never overrides variables that are already set)."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


# ---------------------------------------------------------------- locks
@contextmanager
def lock(name: str, timeout: float = 20.0):
    """Cross-process lock file in .econ/locks (stale after 120s)."""
    d = STATE / "locks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (re.sub(r"[^\w.-]", "_", name) + ".lock")
    start = time.time()
    while True:
        try:
            fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - f.stat().st_mtime > 120:
                    f.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.time() - start > timeout:
                raise EconError(f"lock busy: {name} (another agent is writing; retry)") from None
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            f.unlink()
        except FileNotFoundError:
            pass


def rel(path) -> str:
    """Display path relative to the repo root when possible."""
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()
