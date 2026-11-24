"""`python econ.py <command>` - deterministic CLI shared by humans, agents, hooks and CI.

Output contract: default <= 40 lines of IDs/paths; `--json` for data; exit 0 ok / 1 error / 2 issues found;
`--soft` always exits 0 (for skills' `!` lines, so an issue never aborts the skill).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .common import EconError, Result


def _status(args) -> Result:
    from .status import brief

    return Result(brief())


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--soft", action="store_true", help="always exit 0 (use in skills)")

    p = argparse.ArgumentParser(prog="econ", description="Economic Outlook Lab CLI", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("doctor", parents=[common], help="environment health")
    sp.set_defaults(fn=lambda a: __import__("econ.doctor", fromlist=["run"]).run(a))

    sp = sub.add_parser("status", parents=[common], help="session brief (same as the SessionStart hook)")
    sp.add_argument("--full", action="store_true")
    sp.set_defaults(fn=_status)

    sp = sub.add_parser("src", parents=[common], help="source registry")
    ss = sp.add_subparsers(dest="sub", required=True)
    x = ss.add_parser("list", parents=[common])
    x.add_argument("--phase")
    x.set_defaults(fn=lambda a: __import__("econ.sources", fromlist=["cmd_list"]).cmd_list(a))
    x = ss.add_parser("check", parents=[common], help="probe each source (reachability, content type)")
    x.add_argument("--id", nargs="*")
    x.add_argument("--phase")
    x.add_argument("--write", action="store_true", help="also write docs/source-verification.md")
    x.set_defaults(fn=lambda a: __import__("econ.sources", fromlist=["cmd_check"]).cmd_check(a))

    sp = sub.add_parser("probe", parents=[common], help="P0 probe of Claude Code behaviour")
    ps = sp.add_subparsers(dest="sub", required=True)
    for name in ("enable", "disable", "report"):
        x = ps.add_parser(name, parents=[common])
        x.set_defaults(fn=lambda a, n=name: getattr(__import__("econ.probe", fromlist=[n]), n)(a))
    x = ps.add_parser("mark", parents=[common])
    x.add_argument("name")
    x.set_defaults(fn=lambda a: __import__("econ.probe", fromlist=["mark"]).mark(a))
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        res: Result = args.fn(args)
    except EconError as e:
        print(f"error: {e}")
        return 0 if args.soft else 1
    except Exception as e:  # one line for agents; full traceback only when debugging
        if os.environ.get("ECON_DEBUG") == "1":
            raise
        print(f"error: {type(e).__name__}: {e}")
        return 0 if args.soft else 1
    if args.json:
        print(json.dumps(res.data, ensure_ascii=False, indent=1, default=str))
    elif res.text:
        print(res.text)
    sys.stdout.flush()
    return 0 if args.soft else res.code
