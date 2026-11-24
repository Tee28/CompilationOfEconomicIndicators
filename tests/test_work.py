"""Work ledger, gates, KB, context, audit and codemap - through the CLI like agents use them."""
import json

from conftest import REPO, run_cli


def _ok(r, code=0):
    assert r.returncode == code, r.stdout + r.stderr
    return r.stdout


def test_task_dag_and_ready_unblocking(root):
    assert "T001 added" in _ok(run_cli(root, "task", "add", "--title", "schema", "--owner", "platform-engineer"))
    _ok(run_cli(root, "task", "add", "--title", "ui", "--owner", "frontend-engineer", "--deps", "T001"))
    nxt = _ok(run_cli(root, "task", "next"))
    assert "T001" in nxt and "T002" not in nxt
    assert "unknown deps" in run_cli(root, "task", "add", "--title", "x", "--owner", "a", "--deps", "T999").stdout
    assert "now ready: T002" in _ok(run_cli(root, "task", "done", "T001"))
    assert "T001 [" not in _ok(run_cli(root, "task", "list"))
    assert "T001" in _ok(run_cli(root, "task", "list", "--all"))
    tasks = json.loads((root / "work" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert [t["status"] for t in tasks] == ["done", "todo"]


def test_brief_shows_ready_tasks(root):
    _ok(run_cli(root, "task", "add", "--title", "connector fred", "--owner", "data-engineer"))
    assert "ready T001" in _ok(run_cli(root, "status"))


def test_notes_roundtrip(root):
    _ok(run_cli(root, "notes", "add", "--target", "config/sources.yaml", "--note", "add EIA budget",
                "--author", "quant-researcher"))
    assert "N001" in _ok(run_cli(root, "notes", "list", "--target", "config/"))
    assert "1 note(s)" in _ok(run_cli(root, "notes", "resolve", "N001"))
    assert "no notes" in _ok(run_cli(root, "notes", "list"))


def test_handoff_and_decision(root):
    _ok(run_cli(root, "handoff", "set", "--done", "a", "--next", "b", "--next", "c", "--ask", "q?"))
    out = _ok(run_cli(root, "status"))
    assert "- b" in out and "? q?" in out
    _ok(run_cli(root, "log", "decision", "use FRED first", "--gate", "G1"))
    assert "| Owner | G1 | use FRED first" in (root / "work" / "decisions.md").read_text(encoding="utf-8")


def test_gate_check_and_approve(root):
    out = run_cli(root, "gate", "check", "G1")
    assert out.returncode == 2 and "missing" in out.stdout
    assert run_cli(root, "gate", "check", "G1", "--soft").returncode == 0
    assert "pre-checks fail" in run_cli(root, "gate", "approve", "G1").stdout
    _ok(run_cli(root, "gate", "approve", "G1", "--force", "--stage", "P3"))
    state = json.loads((root / "work" / "state.json").read_text(encoding="utf-8"))
    assert state["gates"]["G1"] == "approved" and state["stage"] == "P3"
    assert "G1 approved" in (root / "work" / "decisions.md").read_text(encoding="utf-8")


def test_global_json_flag_before_subcommand(root):
    data = json.loads(_ok(run_cli(root, "--json", "gate", "check", "G4"), 2))
    assert data["G4"]["status"] == "open"


def test_log_tokens_from_activity(root, tmp_path):
    tr = tmp_path / "agent.jsonl"
    tr.write_text(json.dumps({"message": {"id": "m1", "role": "assistant", "usage": {
        "input_tokens": 5, "output_tokens": 7, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 3}}}) + "\n",
        encoding="utf-8")
    (root / "work" / "activity.log").write_text(
        f"2026-11-24T10:00:00 | data-engineer | a1 | {tr}\n2026-11-24T10:01:00 | data-engineer | a2 | missing.jsonl\n",
        encoding="utf-8")
    out = _ok(run_cli(root, "log", "tokens"))
    assert "data-engineer | 2 | 5 | 7 | 0 | 3 | 1" in out


def test_kb_add_search_lint(root):
    out = _ok(run_cli(root, "kb", "add", "--title", "Sahm rule recession signal", "--domain", "macro",
                      "--source", "https://fred.stlouisfed.org/series/SAHMREALTIME | FRED | open", "--tags", "labour"))
    assert "knowledge/macro/sahm-rule-recession-signal.md" in out
    assert "Sahm" in _ok(run_cli(root, "kb", "search", "sahm"))
    assert "no card" in _ok(run_cli(root, "kb", "search", "zzzz"))
    assert _ok(run_cli(root, "kb", "lint")).strip() == "KB cards OK"
    (root / "knowledge" / "macro" / "bad.md").write_text("no frontmatter", encoding="utf-8")
    assert run_cli(root, "kb", "lint").returncode == 2


def test_context_pack_for_task(root):
    _ok(run_cli(root, "task", "add", "--title", "FRED connector", "--owner", "data-engineer",
                "--outputs", "src/econ/connectors/fred.py"))
    _ok(run_cli(root, "notes", "add", "--target", "src/econ/connectors/", "--note", "respect budget"))
    out = _ok(run_cli(root, "context", "data-engineer", "T001"))
    assert "Task T001" in out and "You own:" in out and "respect budget" in out
    assert len(out.splitlines()) <= 40


def test_repo_audit_and_codemap_are_clean():
    """The real repo must stay within its token budgets and have a fresh CODEMAP (CI runs the same)."""
    import subprocess
    import sys

    for args in (["audit"], ["codemap", "--check"]):
        r = subprocess.run([sys.executable, str(REPO / "econ.py"), *args], cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", env={**__import__("os").environ, "ECON_NO_VENV": "1", "PYTHONUTF8": "1"})
        assert r.returncode == 0, r.stdout
