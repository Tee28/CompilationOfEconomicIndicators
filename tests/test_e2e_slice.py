"""Offline e2e of the live slice (synthetic store) + lint of the GitHub workflows."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from econ.schemas import SITE_MODELS

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
ALLOWED_SECRETS = {"FRED_API_KEY", "GITHUB_TOKEN", "DATA_REPO_TOKEN"}
LEGACY_SECRETS = {"src-check.yml": {"EIA_API_KEY", "COINGECKO_API_KEY", "ESTAT_APP_ID"}}


def econ(*args, data, cwd=None):
    env = dict(os.environ, PYTHONUTF8="1", ECON_NO_VENV="1", ECON_DATA_DIR=str(data))
    env.pop("FRED_API_KEY", None)
    return subprocess.run([sys.executable, str(REPO / "econ.py"), *args], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=120, cwd=cwd)


# ------------------------------------------------------------------ e2e
@pytest.fixture(scope="module")
def dry_run_out(synth_store, tmp_path_factory):
    out = tmp_path_factory.mktemp("e2e")
    r = econ("update", "--dry-run", "--asof", "2026-11-20", "--out-dir", str(out), data=synth_store.data)
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def test_site_json_validates_against_schemas(dry_run_out):
    site = dry_run_out / "web" / "public" / "data"
    man = json.loads((site / "manifest.json").read_text(encoding="utf-8"))
    SITE_MODELS["manifest"].model_validate(man)
    assert man["files"]
    for f in man["files"]:
        kind = f["name"].split(".")[0].split("-")[0]
        data = json.loads((site / f["name"]).read_text(encoding="utf-8"))
        if kind in SITE_MODELS:
            SITE_MODELS[kind].model_validate(data)
        assert f["bytes"] == (site / f["name"]).stat().st_size


def test_dry_run_writes_no_ledger_and_scan_passes(dry_run_out, synth_store):
    led = dry_run_out / "ledger"
    assert not led.exists() or not any(led.rglob("*.jsonl"))
    r = econ("publish", "--scan", "--out-dir", str(dry_run_out), data=synth_store.data)
    assert r.returncode == 0, r.stdout


def test_ledger_dry_run_step_and_verify_on_empty(dry_run_out, synth_store):
    """The update dry-run exercised the ledger step without writing; verify passes on an empty ledger."""
    assert not any(dry_run_out.rglob("*.jsonl"))
    assert econ("ledger", "verify", "--out-dir", str(dry_run_out), data=synth_store.data).returncode == 0


# ------------------------------------------------------------------ workflow lint
def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_workflows_present_and_parse():
    names = {p.name for p in WORKFLOWS}
    assert {"update-data.yml", "deploy-site.yml", "ci.yml", "src-check.yml"} <= names
    for p in WORKFLOWS:
        wf = load(p)
        assert isinstance(wf.get("jobs"), dict) and wf["jobs"], p.name
        assert "permissions" in wf, f"{p.name}: top-level permissions required"
        assert "concurrency" in wf, f"{p.name}: concurrency required"
        for name, job in wf["jobs"].items():
            assert "timeout-minutes" in job, f"{p.name}:{name} needs timeout-minutes"


def test_actions_pinned_by_sha():
    for p in WORKFLOWS:
        for m in re.finditer(r"^\s*-?\s*uses:\s*(\S+)(.*)$", p.read_text(encoding="utf-8"), re.M):
            ref, rest = m.group(1), m.group(2)
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref), f"{p.name}: unpinned {ref}"
            assert re.search(r"#\s*v\d", rest), f"{p.name}: missing version comment for {ref}"


def test_only_allowed_secrets():
    for p in WORKFLOWS:
        used = set(re.findall(r"secrets\.([A-Z0-9_]+)", p.read_text(encoding="utf-8")))
        extra = used - ALLOWED_SECRETS - LEGACY_SECRETS.get(p.name, set())
        assert not extra, f"{p.name}: unexpected secrets {extra}"
    assert "DATA_REPO_TOKEN" not in (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_update_data_schedule_matches_config():
    cfg = yaml.safe_load((REPO / "config" / "econ.yaml").read_text(encoding="utf-8"))["schedule"]
    wf = load(REPO / ".github/workflows/update-data.yml")
    on = wf.get("on", wf.get(True))  # PyYAML parses bare `on` as True
    crons = {c["cron"] for c in on["schedule"]}
    assert crons == {cfg["us_close_utc"], cfg["asia_close_utc"]}
    assert "workflow_dispatch" in on
    assert wf["jobs"]["update"]["permissions"] == {"contents": "write"}


def test_deploy_and_ci_permissions():
    dep = load(REPO / ".github/workflows/deploy-site.yml")
    assert dep["permissions"] == {"contents": "read"}
    assert dep["jobs"]["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    ci = load(REPO / ".github/workflows/ci.yml")
    assert ci["permissions"] == {"contents": "read"}
    text = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for cmd in ("ruff check", "pytest", "econ.py audit", "codemap --check", "ledger verify", "publish --scan",
                "package-lock.json"):
        assert cmd in text, cmd
