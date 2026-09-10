#!/usr/bin/env python3
"""Check this Skill's required files and Markdown links. Does not claim Git provenance."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

REQUIRED_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "tests/skill_contract.json",
    "tests/routing_cases.md",
    "templates/subagent-task.md",
    "rules/complexity-assessment.md",
    "rules/delegation-rules.md",
    "subagents/explorer.md",
    "subagents/implementer.md",
    "subagents/reviewer.md",
    "subagents/verifier.md",
)

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def check_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    if skill_dir.is_symlink() or not skill_dir.is_dir():
        return ["Skill path must be a real directory"]
    skill_dir = skill_dir.resolve()
    for relative in REQUIRED_FILES:
        path = skill_dir.joinpath(*PurePosixPath(relative).parts)
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing required file: {relative}")
    for markdown in sorted(skill_dir.rglob("*.md")):
        if any(part in {"__pycache__", ".git"} for part in markdown.relative_to(skill_dir).parts):
            continue
        try:
            content = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {markdown.relative_to(skill_dir)}: {exc}")
            continue
        source = markdown.relative_to(skill_dir).as_posix()
        for target in LINK_RE.findall(content):
            target = target.split("#", 1)[0].strip()
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            relative = PurePosixPath(target)
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"unsafe local reference in {source}: {target}")
                continue
            candidate = markdown.parent.joinpath(*relative.parts)
            if candidate.is_symlink() or not candidate.exists():
                errors.append(f"broken local reference in {source}: {target}")
    contract_path = skill_dir / "tests" / "skill_contract.json"
    if contract_path.is_file() and not contract_path.is_symlink():
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid tests/skill_contract.json: {exc}")
        else:
            if not isinstance(contract, dict) or contract.get("schema_version") != 1:
                errors.append("tests/skill_contract.json must be an object with schema_version 1")
            elif contract.get("skill") != "multi-agent-engineering":
                errors.append("tests/skill_contract.json skill must be multi-agent-engineering")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate multi-agent-engineering required files and links")
    parser.add_argument("skill_directory", help="Path to the Skill directory")
    args = parser.parse_args(argv)
    errors = check_skill(Path(args.skill_directory))
    if errors:
        print("FAIL")
        for item in errors:
            print(item)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
