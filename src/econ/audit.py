"""Token-hygiene audit: size budgets of always-loaded files, agents, skills, rules, memories, handoff, KB cards.

Budgets live in config/econ.yaml `audit:`. Exit 2 when anything is over budget (CI runs this).
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import ROOT, WORK, Result, cfg, est_tokens

CLAUDE = ROOT / ".claude"


def frontmatter(path: Path) -> tuple[dict, str]:
    import yaml

    t = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", t, re.S)
    if not m:
        return {}, t
    try:
        return yaml.safe_load(m.group(1)) or {}, m.group(2)
    except yaml.YAMLError:
        return {"_error": "bad yaml"}, m.group(2)


def run(args) -> Result:
    def b(k, d):
        return int(cfg(f"audit.{k}", d))

    issues: list[str] = []
    always = 0
    cm = ROOT / "CLAUDE.md"
    if cm.exists():
        text = re.sub(r"<!--.*?-->", "", cm.read_text(encoding="utf-8"), flags=re.S)
        always += est_tokens(text)
        if len(text.splitlines()) > b("claude_md_lines", 120):
            issues.append(f"CLAUDE.md {len(text.splitlines())} lines > {b('claude_md_lines', 120)}")
    else:
        issues.append("CLAUDE.md missing")

    agents = sorted((CLAUDE / "agents").glob("*.md"))
    desc_tok = 0
    for a in agents:
        fm, body = frontmatter(a)
        if fm.get("_error"):
            issues.append(f"agent {a.stem}: frontmatter is not valid YAML")
            continue
        d = str(fm.get("description", ""))
        desc_tok += est_tokens(d) + 8
        if fm.get("name") != a.stem:
            issues.append(f"agent {a.stem}: name '{fm.get('name')}' != file name")
        if len(body.splitlines()) > b("agent_lines", 120):
            issues.append(f"agent {a.stem}: {len(body.splitlines())} lines > {b('agent_lines', 120)}")
        if len(d) > b("agent_desc_chars", 220):
            issues.append(f"agent {a.stem}: description {len(d)} chars > {b('agent_desc_chars', 220)}")
        if not fm.get("model"):
            issues.append(f"agent {a.stem}: no model (inherits the main model)")
        for s in fm.get("skills") or []:
            if not (CLAUDE / "skills" / s / "SKILL.md").exists():
                issues.append(f"agent {a.stem}: preloaded skill '{s}' does not exist")

    skills = sorted((CLAUDE / "skills").glob("*/SKILL.md"))
    sk_tok = 0
    for s in skills:
        fm, body = frontmatter(s)
        d = str(fm.get("description", "")) + str(fm.get("when_to_use", ""))
        wf = bool(fm.get("disable-model-invocation"))
        if fm.get("name") and fm["name"] != s.parent.name:
            issues.append(f"skill {s.parent.name}: name '{fm['name']}' != folder")
        if not wf and fm.get("user-invocable", True) is not False:
            sk_tok += est_tokens(d) + 6  # listed in the Skill tool every turn
        lim = b("workflow_skill_lines", 60) if wf else b("skill_lines", 150)
        if len(body.splitlines()) > lim:
            issues.append(f"skill {s.parent.name}: {len(body.splitlines())} lines > {lim}")
        if len(d) > b("skill_desc_chars", 300):
            issues.append(f"skill {s.parent.name}: description {len(d)} chars > {b('skill_desc_chars', 300)}")
        if wf and "|| true" in body:
            issues.append(f"skill {s.parent.name}: use `--soft` instead of `|| true`")
        if wf and re.search(r"!`python econ\.py (?!.*--soft)", body):
            issues.append(f"skill {s.parent.name}: `!` command without --soft")
        for ref in re.findall(r"references/[\w.-]+", body):
            if not (s.parent / ref).exists():
                issues.append(f"skill {s.parent.name}: missing {ref}")

    for r in sorted((CLAUDE / "rules").glob("*.md")):
        n = len(r.read_text(encoding="utf-8").splitlines())
        if n > b("rule_lines", 40):
            issues.append(f"rule {r.name}: {n} lines > {b('rule_lines', 40)}")
    for m in sorted((CLAUDE / "agent-memory").glob("*/MEMORY.md")):
        n = len(m.read_text(encoding="utf-8").splitlines())
        if n > b("memory_lines", 120):
            issues.append(f"memory {m.parent.name}: {n} lines > {b('memory_lines', 120)} (curate, or split the agent)")
    h = WORK / "handoff.md"
    if h.exists() and len(h.read_text(encoding="utf-8").splitlines()) > b("handoff_lines", 30):
        issues.append(f"work/handoff.md > {b('handoff_lines', 30)} lines")
    for f in (ROOT / "docs" / "CODEMAP.md", ROOT / "docs" / "ARCHITECTURE.md"):
        if f.exists() and len(f.read_text(encoding="utf-8").splitlines()) > 150:
            issues.append(f"docs/{f.name} > 150 lines")
    from .kb import lint

    issues += [f"kb: {x}" for x in lint()[:10]]
    from .status import brief

    nb = len(brief().splitlines())
    if nb > b("brief_lines", 20):
        issues.append(f"brief {nb} lines > {b('brief_lines', 20)}")

    always += desc_tok + sk_tok
    head = (f"audit: {len(agents)} agents, {len(skills)} skills · always-loaded ~{always} tokens "
            f"(CLAUDE.md + agent descriptions ~{desc_tok} + model-invocable skill descriptions ~{sk_tok})")
    return Result("\n".join([head] + (issues or ["all within budgets"])), {"issues": issues, "always_tokens": always},
                  code=2 if issues else 0)
