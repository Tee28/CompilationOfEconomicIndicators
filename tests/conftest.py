"""Test isolation: every test that needs a repo gets a temporary ECON_ROOT with a copy of config/."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "econ.py"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "config", tmp_path / "config")
    (tmp_path / "work").mkdir()
    return tmp_path


def run_hook(root: Path, event: str, payload, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a hook exactly like Claude Code does: launcher + event arg, JSON on stdin."""
    env = dict(os.environ, ECON_ROOT=str(root), PYTHONUTF8="1", **(extra_env or {}))
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(LAUNCHER), "hook", event], input=stdin, capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=60)


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, ECON_ROOT=str(root), PYTHONUTF8="1", ECON_NO_VENV="1")
    return subprocess.run([sys.executable, str(LAUNCHER), *args], capture_output=True, text=True, encoding="utf-8",
                          env=env, timeout=120)


def synth_frame(specs: dict, ids, start="2005-01-01", end="2026-11-20", seed=7):
    """Synthetic random-walk levels (positive) for registry indicators, one backfill vintage."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    rows = []
    for i, iid in enumerate(sorted(ids)):
        sp = specs[iid]
        d = pd.date_range(start, end, freq={"D": "B", "W": "W-SAT", "M": "MS", "Q": "QS"}[sp.freq])
        v = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, len(d)))) + i
        rows.append(pd.DataFrame({"source": sp.source, "series_id": sp.series, "date": d, "value": v,
                                  "fetched_at": "2026-11-21T00:00:00Z"}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="session")
def synth_store(tmp_path_factory):
    """Store with every registry indicator (2005-2026, synthetic): models + ledger tests."""
    from econ import registry, store
    from econ.common import Paths

    specs = registry.load()
    p = Paths(data=tmp_path_factory.mktemp("synth_store"))
    store.append(synth_frame(specs, specs), p)
    return p
