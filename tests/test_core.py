import json

from conftest import run_cli
from econ.common import redact
from econ.http import fill, placeholders
from econ.probe import transcript_replies, transcript_tokens
from econ.sources import check_one, validate


def test_redact_query_params_and_env(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "abcdef123456")
    s = redact("GET https://x/y?series_id=A&api_key=abcdef123456&appId=zzz9 failed; key abcdef123456")
    assert "abcdef123456" not in s and "zzz9" not in s and "series_id=A" in s


def test_placeholders_and_fill():
    t = "https://x/?k={FRED_API_KEY}&q={OTHER}"
    assert placeholders(t) == ["FRED_API_KEY", "OTHER"]
    assert fill(t, {"FRED_API_KEY": "K"}) == "https://x/?k=K&q="


def test_validate_content_types():
    assert validate(200, b'{"a": 1}', "json") == (True, "")
    ok, note = validate(200, b"<!DOCTYPE html><html>captcha</html>", "json")
    assert not ok and "HTML instead of JSON" in note
    assert validate(200, b"date,value\n2026-01-01,1\n", "csv")[0]
    assert validate(200, b"<?xml version='1.0'?><a/>", "xml")[0]
    assert validate(200, b"\xd0\xcf\x11\xe0rest", "xls")[0]
    assert not validate(451, b"restricted location", "json")[0]


def test_check_one_skips_without_required_key():
    row = check_one("fred", {"probe": {"url": "https://x/?api_key={FRED_API_KEY}", "expect": "json"}}, env={})
    assert row["ok"] is None and "missing FRED_API_KEY" in row["note"]


def test_transcript_tokens_dedupes_streamed_ids(tmp_path):
    p = tmp_path / "t.jsonl"
    rows = [{"message": {"id": "m1", "usage": {"input_tokens": 5, "output_tokens": 1}}},
            {"message": {"id": "m1", "usage": {"input_tokens": 5, "output_tokens": 9}}},
            {"message": {"id": "m2", "usage": {"input_tokens": 3, "output_tokens": 2,
                                               "cache_read_input_tokens": 100}}},
            {"type": "user"}, "not json"]
    p.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows), encoding="utf-8")
    t = transcript_tokens(str(p))
    assert t == {"in": 8, "out": 11, "cache_r": 100, "cache_w": 0, "messages": 2}


def test_transcript_replies_reads_text_and_handback(tmp_path):
    p = tmp_path / "t.jsonl"
    rows = [{"message": {"role": "user", "content": [{"type": "text", "text": "PROMPT-ONLY"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}},
            {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "SubagentHandback",
                                                           "input": {"message": "MANAGER-OK x | worker: WORKER-OK-x"}}]}},
            "not json"]
    p.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows), encoding="utf-8")
    out = transcript_replies(str(p))
    assert "hello" in out and "WORKER-OK-x" in out and "PROMPT-ONLY" not in out
    assert transcript_replies("") == ""


def test_probe_report_detects_nested_wait(root):
    probe = root / ".econ" / "probe"
    (probe / "payloads").mkdir(parents=True)
    (probe / "marks").mkdir()
    (probe / "enabled").write_text("n0nce1", encoding="utf-8")
    for name, data in (("subagent-stop__probe-worker__", {"agent_type": "probe-worker", "agent_id": "w",
                                                          "agent_transcript_path": ""}),
                       ("subagent-stop__probe-manager__", {"agent_type": "probe-manager", "agent_id": "m",
                                                           "agent_transcript_path": "",
                                                           "last_assistant_message": "MANAGER-OK WORKER-OK-n0nce1"})):
        (probe / "payloads" / f"{name}__1.json").write_text(json.dumps({"_event": "subagent-stop", "data": data}),
                                                            encoding="utf-8")
    r = run_cli(root, "probe", "report", "--json")
    checks = {c["check"]: c["status"] for c in json.loads(r.stdout)["checks"]}
    assert checks["nested spawn + manager waits"] == "PASS"
    assert checks["SubagentStop fields"] == "PASS"


def test_cli_status_and_soft_exit(root):
    r = run_cli(root, "status")
    assert r.returncode == 0 and r.stdout.startswith("[ECON BRIEF]")
    bad = run_cli(root, "src", "check", "--id", "does-not-exist", "--soft")
    assert bad.returncode == 0 and "unknown source" in bad.stdout
