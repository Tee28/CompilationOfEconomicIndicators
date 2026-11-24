#!/usr/bin/env python3
"""Economic Outlook Lab CLI launcher.

- `hook` subcommands run in-process with whatever Python started them (stdlib only, no venv
  re-exec = one process, fast) and ALWAYS exit 0 (fail-open): a broken hook never blocks Claude.
- Every other command re-runs itself inside ./.venv when it exists, so `python econ.py ...`
  works from any shell, and forces UTF-8 I/O (Windows consoles may default to cp932).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_HOOK = len(sys.argv) > 1 and sys.argv[1] == "hook"


def _venv_python():
    for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if p.exists():
            return p
    return None


def _in_venv():
    try:
        return Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
    except OSError:
        return False


def _utf8_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    sys.path.insert(0, str(ROOT / "src"))
    if IS_HOOK:
        try:
            _utf8_streams()
            from econ.hooks import main as hook_main
            hook_main(sys.argv[2:])
        except BaseException:
            pass
        sys.exit(0)

    vp = _venv_python()
    if vp and not _in_venv() and os.environ.get("ECON_NO_VENV") != "1":
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            rc = subprocess.run([str(vp), str(Path(__file__).resolve()), *sys.argv[1:]], env=env).returncode
        except Exception:
            rc = 1
        sys.exit(rc)

    _utf8_streams()
    from econ.cli import main as cli_main
    sys.exit(cli_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
