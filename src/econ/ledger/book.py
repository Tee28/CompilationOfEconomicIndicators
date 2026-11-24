"""Append-only forecast ledger: <ledger>/forecasts/<yyyy-mm>.jsonl (+ chain.json hash chain) and health.json.

- append: one JSONL line per ForecastRecord, idempotent by id (origin|market|horizon|model); file = origin month.
- score: when the target obs h months after the anchor is known, append a second line with the same id and
  outcome fields set (never rewrite). Readers take the last line per id.
- verify: every line hash must match chain.json (sha256 chained over lines), no unchained/deleted lines, score
  lines must repeat the forecast fields unchanged. Exit 2 on any issue.
- health: per-indicator freshness + quality issues of the stored series -> Health (schemas) -> health.json.
Only CI writes the real ledger/; tests and local runs use --out-dir / --ledger-dir / --dry-run.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from ..common import Paths, Result, lock, read_json, today, utcnow, write_json
from ..schemas import ForecastRecord, Health, SourceHealth

FORECAST_FIELDS = ("id", "origin", "horizon", "market", "model_id", "p_up", "quantiles", "baseline_rw_p_up",
                   "baseline_clim_p_up", "features_hash", "data_asof", "created_at")


def _files(paths: Paths) -> list[Path]:
    d = paths.ledger / "forecasts"
    return sorted(d.glob("*.jsonl")) if d.exists() else []


def _rel(p: Path, paths: Paths) -> str:
    return p.relative_to(paths.ledger).as_posix()


def _lines(p: Path) -> list[str]:
    return p.read_bytes().decode("utf-8").splitlines() if p.exists() else []


def _chain_hash(prev: str, line: str) -> str:
    return hashlib.sha256((prev + line).encode("utf-8")).hexdigest()


def _chain(paths: Paths) -> dict:
    return read_json(paths.ledger / "chain.json", {"version": 1, "files": {}})


def read_all(paths: Paths) -> dict[str, ForecastRecord]:
    """id -> last record (forecast or its score line)."""
    out: dict[str, ForecastRecord] = {}
    for f in _files(paths):
        for ln in _lines(f):
            if ln.strip():
                r = ForecastRecord.model_validate_json(ln)
                out[r.id] = r
    return out


def _write_lines(by_file: dict[str, list[str]], paths: Paths) -> None:
    ch = _chain(paths)
    for rel, new in by_file.items():
        p = paths.ledger / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        ent = ch["files"].setdefault(rel, {"lines": 0, "head": "", "hashes": []})
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            for ln in new:
                fh.write(ln + "\n")
                ent["head"] = _chain_hash(ent["head"], ln)
                ent["hashes"].append(ent["head"])
                ent["lines"] += 1
    write_json(paths.ledger / "chain.json", ch)


def append(records: list[ForecastRecord], paths: Paths | None = None, dry_run: bool = False) -> tuple[list, list]:
    """Append new forecasts; returns (added ids, skipped ids). Same id twice = no-op (idempotent)."""
    paths = paths or Paths()
    with lock("ledger-" + hashlib.md5(str(paths.ledger.resolve()).encode()).hexdigest()[:8]):
        seen = set(read_all(paths))
        added, skipped, by_file = [], [], {}
        for r in records:
            if r.id in seen or r.scored_at is not None:
                skipped.append(r.id)
                continue
            seen.add(r.id)
            added.append(r.id)
            by_file.setdefault(f"forecasts/{r.origin[:7]}.jsonl", []).append(r.model_dump_json())
        if by_file and not dry_run:
            _write_lines(by_file, paths)
    return added, skipped


def score(asof, paths: Paths | None = None, dry_run: bool = False, config_dir=None) -> list[ForecastRecord]:
    """Append outcome lines for matured, unscored forecasts (target obs known at `asof`)."""
    from .. import registry
    from ..models import data

    paths = paths or Paths()
    asof = str(asof)[:10]
    specs = registry.load(config_dir)
    targets: dict = {}
    out, by_file = [], {}
    with lock("ledger-" + hashlib.md5(str(paths.ledger.resolve()).encode()).hexdigest()[:8]):
        for r in read_all(paths).values():
            if r.scored_at is not None or r.origin > asof:
                continue
            akey = next((k for k in r.data_asof if k.startswith("anchor:")), None)
            if akey is None:
                continue
            tid, h = akey.split(":", 1)[1], int(r.horizon.rstrip("m"))
            if tid not in specs:
                continue
            if (tid, h) not in targets:
                targets[(tid, h)] = data.target_for(specs[tid], h, asof, paths)
            y, _ = targets[(tid, h)].realized(pd.Timestamp(r.data_asof[akey]), asof)
            if y is None:
                continue
            up = float(y > 0)
            s = r.model_copy(update=dict(
                scored_at=f"{asof}T00:00:00Z", realized_return=round(y, 6), realized_up=bool(y > 0),
                brier=round((r.p_up - up) ** 2, 6), brier_rw=round((r.baseline_rw_p_up - up) ** 2, 6),
                brier_clim=round((r.baseline_clim_p_up - up) ** 2, 6)))
            out.append(s)
            by_file.setdefault(f"forecasts/{r.origin[:7]}.jsonl", []).append(s.model_dump_json())
        if by_file and not dry_run:
            _write_lines(by_file, paths)
    return out


def verify(paths: Paths | None = None) -> list[str]:
    """Issues (empty = ok): rewritten / truncated / deleted / unchained lines, invalid records, score lines that
    change forecast fields, duplicate forecasts or double scoring."""
    paths = paths or Paths()
    issues: list[str] = []
    ch = _chain(paths)["files"]
    first: dict[str, dict] = {}
    scored: set[str] = set()
    files = {_rel(f, paths): f for f in _files(paths)}
    for rel in sorted(set(ch) - set(files)):
        issues.append(f"{rel}: in chain but file deleted")
    for rel, f in files.items():
        lines, ent = _lines(f), ch.get(rel)
        if ent is None:
            issues.append(f"{rel}: not in chain.json (written outside the CLI)")
            continue
        h = ""
        for i, ln in enumerate(lines):
            h = _chain_hash(h, ln)
            if i < len(ent["hashes"]) and h != ent["hashes"][i]:
                issues.append(f"{rel}: line {i + 1} rewritten (hash mismatch)")
                break
        if len(lines) < ent["lines"]:
            issues.append(f"{rel}: truncated ({len(lines)} < {ent['lines']} chained lines)")
        elif len(lines) > ent["lines"]:
            issues.append(f"{rel}: {len(lines) - ent['lines']} unchained line(s) appended outside the CLI")
        if ent["hashes"] and ent["head"] != ent["hashes"][-1]:
            issues.append(f"{rel}: chain head inconsistent")
        for i, ln in enumerate(lines):
            try:
                r = ForecastRecord.model_validate_json(ln)
            except Exception:
                issues.append(f"{rel}: line {i + 1} is not a valid ForecastRecord")
                continue
            d = r.model_dump(include=set(FORECAST_FIELDS))
            if r.scored_at is None:
                if r.id in first:
                    issues.append(f"{rel}: duplicate forecast {r.id}")
                first[r.id] = d
            elif r.id not in first:
                issues.append(f"{rel}: score line before forecast {r.id}")
            elif first[r.id] != d:
                issues.append(f"{rel}: score line changes forecast fields of {r.id}")
            elif r.id in scored:
                issues.append(f"{rel}: {r.id} scored twice")
            else:
                scored.add(r.id)
    return issues


def health(asof, paths: Paths | None = None, outcomes=None, last_run: str | None = None, config_dir=None) -> Health:
    """Freshness + quality of every registry indicator as stored at `asof`; `outcomes` (fetch results) can mark
    failed fetches. fails = consecutive failed runs (from the previous health.json)."""
    from .. import registry, store
    from ..quality import check_frame, health_entry

    paths = paths or Paths()
    asof = str(asof)[:10]
    prev = (read_json(paths.ledger / "health.json", {}) or {}).get("sources", {})
    oc = {getattr(o, "id", None): o for o in (outcomes or [])}
    out = {}
    for iid, sp in sorted(registry.load(config_dir).items()):
        f = store.read_frame(sp.source, sp.series, asof, sp.lag_days, paths)
        o = oc.get(iid)
        if f.empty:
            e = {"ok": False, "last_obs": None, "lag_days": None, "note": "no stored data"}
            status = "failed"
        else:
            issues = check_frame(f[["date", "value"]], sp, asof)
            e = health_entry(issues, f["date"].iloc[-1], asof)
            codes = {i["code"] for i in issues}
            status = ("failed" if not e["ok"] else "late" if "stale" in codes else
                      "degraded" if issues else "ok")
        if o is not None and getattr(o, "status", "") == "failed":
            status, e["ok"] = "failed", False
            e["note"] = (e.get("note") or "") + ("; " if e.get("note") else "") + f"fetch failed: {o.note}"[:120]
        fails = int(prev.get(iid, {}).get("fails", 0)) + 1 if status == "failed" else 0
        out[iid] = SourceHealth(ok=bool(e["ok"]) and status != "failed", status=status, last_obs=e["last_obs"],
                                lag_days=e["lag_days"], fails=fails, note=(e.get("note") or "")[:160])
    return Health(asof=asof, last_run=last_run or utcnow(), sources=out)


# ---------------------------------------------------------------- CLI handlers
def _asof(args) -> str:
    return getattr(args, "asof", None) or today()


def cmd_append(args) -> Result:
    from .. import models

    paths, asof, dry = Paths.from_args(args), _asof(args), bool(getattr(args, "dry_run", False))
    runs = models.forecast_all(asof, paths)
    recs = [r for run in runs for r in run.records]
    added, skipped = append(recs, paths, dry_run=dry)
    lines = [f"ledger append asof {asof}: {len(added)} added, {len(skipped)} already present"
             f"{' (dry-run, nothing written)' if dry else ''} -> {paths.ledger}"]
    lines += [f"  + {i}" for i in added[:30]]
    return Result("\n".join(lines[:40]), data={"added": added, "skipped": skipped})


def cmd_score(args) -> Result:
    paths, asof, dry = Paths.from_args(args), _asof(args), bool(getattr(args, "dry_run", False))
    res = score(asof, paths, dry_run=dry)
    lines = [f"ledger score asof {asof}: {len(res)} matured{' (dry-run, nothing written)' if dry else ''}"]
    lines += [f"  {r.id} up={r.realized_up} brier {r.brier:.3f} rw {r.brier_rw:.3f} clim {r.brier_clim:.3f}"
              for r in res[:30]]
    return Result("\n".join(lines[:40]), data=[r.model_dump() for r in res])


def cmd_verify(args) -> Result:
    paths = Paths.from_args(args)
    issues = verify(paths)
    n = sum(len(_lines(f)) for f in _files(paths))
    head = f"ledger verify {paths.ledger}: {len(_files(paths))} files, {n} lines, {len(issues)} issue(s)"
    return Result("\n".join([head] + [f"  {i}" for i in issues[:38]]), data={"issues": issues},
                  code=2 if issues else 0)


def cmd_health(args) -> Result:
    paths, asof, dry = Paths.from_args(args), _asof(args), bool(getattr(args, "dry_run", False))
    h = health(asof, paths)
    if not dry:
        write_json(paths.ledger / "health.json", h.model_dump())
    bad = {k: v for k, v in h.sources.items() if v.status != "ok"}
    lines = [f"ledger health asof {asof}: {len(h.sources) - len(bad)}/{len(h.sources)} ok"
             f"{' (dry-run, nothing written)' if dry else ' -> ' + str(paths.ledger / 'health.json')}"]
    lines += [f"  {k:<10} {v.status:<8} last {v.last_obs or '-'} fails {v.fails} {v.note[:60]}"
              for k, v in list(bad.items())[:36]]
    return Result("\n".join(lines[:40]), data=h.model_dump())
