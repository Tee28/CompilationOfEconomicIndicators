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


# Live-slice handlers live in other agents' modules (contract: docs/adr/0001-live-slice-contracts.md).
# Each is `fn(args) -> Result`; a missing module/function gives a clear one-line error (exit 1).
def _lazy(module: str, fn: str):
    def run(args) -> Result:
        import importlib

        try:
            mod = importlib.import_module(f"econ.{module}")
        except ModuleNotFoundError as e:
            if e.name and e.name.startswith("econ"):
                raise EconError(f"not implemented yet: econ.{module}.{fn} (module missing)") from None
            raise
        f = getattr(mod, fn, None)
        if f is None:
            raise EconError(f"not implemented yet: econ.{module}.{fn}")
        return f(args)

    return run


def _register_live(sub, common) -> None:
    def paths(x):
        x.add_argument("--data-dir", help="raw store (default data/ or $ECON_DATA_DIR)")
        x.add_argument("--ledger-dir", help="ledger dir (default ledger/)")
        x.add_argument("--out-dir", help="redirect ledger/ and web/public/data under this dir")

    def asof(x):
        x.add_argument("--asof", help="as-of date YYYY-MM-DD (default: today UTC)")

    sp = sub.add_parser("ind", parents=[common], help="indicator registry")
    s = sp.add_subparsers(dest="sub", required=True)
    x = s.add_parser("list", parents=[common])
    x.add_argument("--market")
    x.add_argument("--license", choices=["open", "attributed", "internal"])
    x.set_defaults(fn=_lazy("registry", "cmd_ind_list"))
    x = s.add_parser("get", parents=[common])
    x.add_argument("id")
    x.add_argument("--tail", type=int, default=5)
    paths(x), asof(x)
    x.set_defaults(fn=_lazy("registry", "cmd_ind_get"))

    sp = sub.add_parser("fetch", parents=[common], help="fetch raw series into the store")
    sp.add_argument("--id", nargs="*", help="indicator ids (default: all live-slice)")
    sp.add_argument("--budget", type=int, help="override per-run call budget per source")
    sp.add_argument("--source", help="only this source id (fred, oecd, worldbank_pinksheet)")
    sp.add_argument("--dry-run", action="store_true")
    paths(sp), asof(sp)
    sp.set_defaults(fn=_lazy("connectors", "cmd_fetch"))

    sp = sub.add_parser("compute", help="transforms + composites from the store", parents=[common])
    sp.add_argument("--dry-run", action="store_true")
    paths(sp), asof(sp)
    sp.set_defaults(fn=_lazy("composites", "cmd_compute"))

    sp = sub.add_parser("forecast", parents=[common], help="run models, emit ForecastRecords")
    sp.add_argument("--market", nargs="*")
    sp.add_argument("--dry-run", action="store_true")
    paths(sp), asof(sp)
    sp.set_defaults(fn=_lazy("models", "cmd_forecast"))

    sp = sub.add_parser("ledger", parents=[common], help="append-only forecast ledger (CI writes)")
    s = sp.add_subparsers(dest="sub", required=True)
    for name, h in (("append", "append forecasts for the as-of origin"), ("score", "score matured forecasts"),
                    ("verify", "fail on any rewrite of an old line"), ("health", "write ledger/health.json")):
        x = s.add_parser(name, parents=[common], help=h)
        if name in ("append", "score", "health"):
            x.add_argument("--dry-run", action="store_true")
        paths(x), asof(x)
        x.set_defaults(fn=_lazy("ledger", f"cmd_{name}"))

    sp = sub.add_parser("publish", parents=[common], help="build site JSON (license gate) + manifest")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--scan", action="store_true", help="license-scan the site JSON on disk only (CI gate)")
    paths(sp), asof(sp)
    sp.set_defaults(fn=_lazy("publish", "cmd_publish"))

    sp = sub.add_parser("update", parents=[common], help="orchestrator: fetch>compute>forecast>ledger>publish")
    sp.add_argument("--dry-run", action="store_true", help="no fetch, no ledger writes; site JSON only with --out-dir")
    sp.add_argument("--budget", type=int, help="override per-run call budget per source")
    sp.add_argument("--source", help="only fetch this source id")
    sp.add_argument("--id", nargs="*", help="only fetch these indicator ids")
    paths(sp), asof(sp)
    sp.set_defaults(fn=_lazy("publish.update", "cmd_update"))


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS: a subparser must not reset a flag given before the subcommand (`econ --json gate check`)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output")
    common.add_argument("--soft", action="store_true", default=argparse.SUPPRESS, help="always exit 0 (use in skills)")

    p = argparse.ArgumentParser(prog="econ", description="Economic Outlook Lab CLI", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("doctor", parents=[common], help="environment health")
    sp.set_defaults(fn=lambda a: __import__("econ.doctor", fromlist=["run"]).run(a))

    sp = sub.add_parser("status", parents=[common], help="session brief (same as the SessionStart hook)")
    sp.add_argument("--full", action="store_true")
    sp.set_defaults(fn=_status)

    from . import kb, work

    work.register(sub, common)
    _register_live(sub, common)
    kb.register(sub, common)

    sp = sub.add_parser("audit", parents=[common], help="token-hygiene budgets (CI runs this)")
    sp.set_defaults(fn=lambda a: __import__("econ.audit", fromlist=["run"]).run(a))

    sp = sub.add_parser("codemap", parents=[common], help="regenerate docs/CODEMAP.md")
    sp.add_argument("--check", action="store_true", help="exit 2 if stale (CI)")
    sp.set_defaults(fn=lambda a: __import__("econ.codemap", fromlist=["run"]).run(a))

    sp = sub.add_parser("context", parents=[common], help="minimal context pack for <role> <target>")
    sp.add_argument("role")
    sp.add_argument("target", nargs="?", default="-")
    sp.set_defaults(fn=lambda a: __import__("econ.context", fromlist=["run"]).run(a))

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
        if name == "enable":
            x.add_argument("--mark", help="also record this mark (proves a skill `!` line ran)")
        x.set_defaults(fn=lambda a, n=name: getattr(__import__("econ.probe", fromlist=[n]), n)(a))
    x = ps.add_parser("mark", parents=[common])
    x.add_argument("name")
    x.set_defaults(fn=lambda a: __import__("econ.probe", fromlist=["mark"]).mark(a))
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    args.json, args.soft = getattr(args, "json", False), getattr(args, "soft", False)
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
