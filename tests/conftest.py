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
