import json
import subprocess
import sys

from conftest import REPO, run_hook


def _decision(out: str) -> str:
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else ""


def test_fail_open_on_garbage_and_unknown_event(root):
    for event, payload in (("pre-read", "not json {"), ("nope", {}), ("pre-write", "[1,2]")):
        r = run_hook(root, event, payload)
        assert r.returncode == 0 and r.stdout == ""


def test_hooks_import_stdlib_only():
    code = ("import sys; sys.path.insert(0, 'src'); import econ.hooks, econ.status; "
            "print([m for m in ('yaml', 'requests', 'pandas', 'numpy') if m in sys.modules])")
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
    assert r.stdout.strip() == "[]", r.stderr


def test_token_guard_big_file(root):
    big = root / "notes.txt"
    big.write_text("x" * 50_000, encoding="utf-8")
    assert _decision(run_hook(root, "pre-read", {"tool_input": {"file_path": str(big)}}).stdout) == "deny"
    sliced = run_hook(root, "pre-read", {"tool_input": {"file_path": str(big), "limit": 50}})
    assert sliced.stdout == ""


def test_token_guard_paths_and_allowlist(root):
    (root / "data").mkdir()
    pq = root / "data" / "fred.parquet"
    pq.write_bytes(b"PAR1")
    r = run_hook(root, "pre-read", {"tool_input": {"file_path": str(pq)}})
    assert _decision(r.stdout) == "deny" and "ind get" in r.stdout
    site = root / "web" / "public" / "data" / "overview.json"
    site.parent.mkdir(parents=True)
    site.write_text("{}", encoding="utf-8")
    assert _decision(run_hook(root, "pre-read", {"tool_input": {"file_path": str(site)}}).stdout) == "deny"
    assert run_hook(root, "pre-read", {"tool_input": {"file_path": str(site), "limit": 20}}).stdout == ""
    agent_md = root / ".claude" / "agents" / "big.md"
    agent_md.parent.mkdir(parents=True)
    agent_md.write_text("y" * 60_000, encoding="utf-8")
    assert run_hook(root, "pre-read", {"tool_input": {"file_path": str(agent_md)}}).stdout == ""


def test_ownership_guard(root):
    web = str(root / "web" / "src" / "App.tsx")
    sources = str(root / "config" / "sources.yaml")
    main = run_hook(root, "pre-write", {"tool_name": "Write", "tool_input": {"file_path": web}})
    assert main.stdout == ""  # main thread is never restricted
    deny = run_hook(root, "pre-write", {"agent_type": "data-engineer", "tool_name": "Edit",
                                        "tool_input": {"file_path": web}})
    assert _decision(deny.stdout) == "deny" and "notes add" in deny.stdout
    own = run_hook(root, "pre-write", {"agent_type": "data-engineer", "tool_name": "Edit",
                                       "tool_input": {"file_path": sources}})
    assert own.stdout == ""
    other = run_hook(root, "pre-write", {"agent_type": "general-purpose", "tool_name": "Write",
                                         "tool_input": {"file_path": web}})
    assert other.stdout == ""  # agents without an owners entry are unrestricted


def test_spawn_guard(root):
    ok = run_hook(root, "pre-write", {"agent_type": "research-lead", "tool_name": "Agent",
                                      "tool_input": {"subagent_type": "macro-strategist"}})
    assert ok.stdout == ""
    no = run_hook(root, "pre-write", {"agent_type": "markets-strategist", "tool_name": "Agent",
                                      "tool_input": {"subagent_type": "data-engineer"}})
    assert _decision(no.stdout) == "deny"


def test_post_edit_blocks_bad_config_json(root):
    bad = root / "config" / "broken.json"
    bad.write_text("{oops", encoding="utf-8")
    r = run_hook(root, "post-edit", {"tool_input": {"file_path": str(bad)}})
    assert json.loads(r.stdout)["decision"] == "block"


def test_subagent_stop_skips_internal_agents(root):
    run_hook(root, "subagent-stop", {"agent_type": "", "agent_id": "x1", "agent_transcript_path": "/t.jsonl"})
    assert not (root / "work" / "activity.log").exists()
    run_hook(root, "subagent-stop", {"agent_type": "data-engineer", "agent_id": "a1",
                                     "agent_transcript_path": "/t.jsonl"})
    line = (root / "work" / "activity.log").read_text(encoding="utf-8")
    assert "| data-engineer | a1 | /t.jsonl" in line


def test_session_start_brief_is_short(root):
    (root / "work" / "handoff.md").write_text("# Handoff\n## Next\n- port hooks\n- write CLAUDE.md\n", encoding="utf-8")
    r = run_hook(root, "session-start", {"source": "startup"})
    lines = r.stdout.strip().splitlines()
    assert lines[0].startswith("[ECON BRIEF]") and len(lines) <= 20
    assert any("port hooks" in ln for ln in lines)


def test_pre_compact_snapshot(root):
    (root / "work" / "tasks.json").write_text(json.dumps({"tasks": [
        {"id": "T001", "title": "connectors", "owner": "data-engineer", "status": "todo"}]}), encoding="utf-8")
    r = run_hook(root, "pre-compact", {"trigger": "auto"})
    assert 1 <= len(r.stdout.strip().splitlines()) <= 5 and "T001" in r.stdout
    assert (root / "work" / "compact-snapshot.md").exists()


def test_probe_dump_redacts_secrets(root):
    probe = root / ".econ" / "probe"
    probe.mkdir(parents=True)
    (probe / "enabled").write_text("abc123", encoding="utf-8")
    url = "https://api.example/obs?series=DGS10&api_key=SECRETKEY123"
    run_hook(root, "pre-read", {"tool_name": "Read", "tool_input": {"file_path": url}})
    dumps = list((probe / "payloads").glob("*.json"))
    assert dumps and "SECRETKEY123" not in dumps[0].read_text(encoding="utf-8")
