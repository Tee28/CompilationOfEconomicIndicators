"""`econ update`: fetch > compute > forecast > ledger append/score/health > publish, with step-level status.

--dry-run: nothing is fetched (plan only) and nothing is written to ledger/ or the real site dir. With an explicit
--out-dir the site JSON is still written (to <out-dir>/web/public/data) so the whole slice can be inspected.
A missing FRED key = fetch skipped + the affected sources marked degraded in health (never a crash).
A failed step marks the dependent steps skipped; exit 1 if any step failed, 2 on a license/size gate violation.
"""
from __future__ import annotations

from .. import composites, ledger, models, registry
from ..common import EconError, Paths, Result, redact, today, utcnow, write_json
from . import GateError, build

STEPS = ("fetch", "compute", "forecast", "ledger", "publish")


def run(asof, paths: Paths, dry_run: bool = False, write_site: bool | None = None, budget=None, source=None,
        ids=None, config_dir=None) -> dict:
    """Run the pipeline; returns {"steps": {name: {status, note}}, "code": int, ...}. Never raises on step errors."""
    from ..connectors import fetch_all

    asof = str(asof)[:10]
    steps: dict[str, dict] = {s: {"status": "pending", "note": ""} for s in STEPS}
    ctx: dict = {"outcomes": [], "comps": None, "runs": None, "manifest": None}
    code = 0

    def step(name, fn, needs=()):
        nonlocal code
        dead = [n for n in needs if steps[n]["status"] == "failed"]
        if dead:
            steps[name] = {"status": "skipped", "note": f"depends on failed {dead[0]}"}
            return
        try:
            note = fn() or ""
            if steps[name]["status"] == "pending":
                steps[name] = {"status": "ok", "note": note}
            else:
                steps[name]["note"] = note
        except GateError as e:
            steps[name] = {"status": "failed", "note": redact(str(e))[:200]}
            code = max(code, 2)
        except Exception as e:  # noqa: BLE001 - a step failure must not crash the orchestrator
            steps[name] = {"status": "failed", "note": redact(f"{type(e).__name__}: {e}")[:200]}
            code = max(code, 1)

    def do_fetch():
        specs = registry.load(config_dir)
        ctx["outcomes"] = fetch_all(specs, paths, asof, dry_run=dry_run, budget=budget, ids=ids, source=source)
        c = {}
        for o in ctx["outcomes"]:
            c[o.status] = c.get(o.status, 0) + 1
        if c.get("skipped") or c.get("failed"):
            steps["fetch"]["status"] = "degraded"
        return ", ".join(f"{k}={v}" for k, v in sorted(c.items()))

    def do_compute():
        ctx["comps"] = composites.compute(asof, paths, config_dir)
        return f"{len(ctx['comps'])} composites"

    def do_forecast():
        ctx["runs"] = models.forecast_all(asof, paths)
        return f"{sum(len(r.records) for r in ctx['runs'])} records"

    def do_ledger():
        recs = [r for run_ in ctx["runs"] for r in run_.records]
        added, skipped = ledger.append(recs, paths, dry_run=dry_run)
        scored = ledger.score(asof, paths, dry_run=dry_run)
        h = ledger.health(asof, paths, outcomes=ctx["outcomes"], config_dir=config_dir)
        skip = {o.id: o.note for o in ctx["outcomes"] if o.status == "skipped"}
        for iid, note in skip.items():
            e = h.sources.get(iid)
            if e is not None and e.status in ("ok", "late"):
                e.status, e.note = "degraded", f"fetch skipped: {note}"[:160]
        if not dry_run:
            write_json(paths.ledger / "health.json", h.model_dump())
        bad = sum(v.status != "ok" for v in h.sources.values())
        return f"+{len(added)} forecasts, {len(scored)} scored, health {len(h.sources) - bad}/{len(h.sources)} ok"

    def do_publish():
        write = (not dry_run) if write_site is None else write_site
        ctx["manifest"] = build(asof, paths, runs=ctx["runs"], comps=ctx["comps"], write=write, config_dir=config_dir)
        m = ctx["manifest"]
        return f"{len(m.files)} files ({sum(f.bytes for f in m.files) // 1024} KB){'' if write else ' not written'}"

    step("fetch", do_fetch)
    step("compute", do_compute)
    step("forecast", do_forecast, ("compute",))
    step("ledger", do_ledger, ("forecast",))
    step("publish", do_publish, ("compute", "forecast"))
    return {"asof": asof, "steps": steps, "code": code, "manifest": ctx["manifest"]}


def cmd_update(args) -> Result:
    asof = getattr(args, "asof", None) or today()
    paths = Paths.from_args(args)
    dry = bool(getattr(args, "dry_run", False))
    write_site = True if (dry and getattr(args, "out_dir", None)) else None
    ids = getattr(args, "id", None)
    if getattr(args, "budget", None) is not None and int(args.budget) < 0:
        raise EconError("--budget must be >= 0")
    res = run(asof, paths, dry, write_site, getattr(args, "budget", None), getattr(args, "source", None), ids)
    lines = [f"update asof {asof}{' (dry-run: no fetch, no ledger writes)' if dry else ''} -> "
             f"{paths.ledger} | {paths.site}"]
    for n, s in res["steps"].items():
        lines.append(f"  {n:<9} {s['status']:<9} {s['note']}")
    lines.append(f"done {utcnow()} exit {res['code']}")
    man = res["manifest"]
    return Result("\n".join(lines[:40]), code=res["code"],
                  data={"asof": asof, "steps": res["steps"], "manifest": man.model_dump() if man else None})
