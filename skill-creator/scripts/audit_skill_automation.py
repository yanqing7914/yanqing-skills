#!/usr/bin/env python3
"""Audit whether a Codex Skill has evidence for safe automation.

This is an evidence audit, not a quality score.  It never executes a Skill's
scripts unless ``--run-tests`` is explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import quick_validate  # noqa: E402

try:
    import skill_gate  # noqa: E402
except ImportError:  # pragma: no cover - only relevant for unusual embedding
    skill_gate = None


def _check(check_id: str, status: str, message: str, evidence=None) -> dict:
    item = {"id": check_id, "status": status, "message": message}
    if evidence:
        item["evidence"] = evidence
    return item


def _discover_entrypoints(skill_path: Path) -> list[str]:
    scripts = skill_path / "scripts"
    if not scripts.is_dir() or scripts.is_symlink():
        return []
    entries = []
    for path in sorted(scripts.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix in {".py", ".sh", ".bash", ".js", ".mjs"} or os.access(path, os.X_OK):
            entries.append(path.relative_to(skill_path).as_posix())
    return entries


def _load_contract(skill_path: Path):
    contract_path = skill_path / "tests" / "skill_contract.json"
    if not contract_path.is_file() or contract_path.is_symlink():
        return None, None
    try:
        return json.loads(contract_path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _contract_case(contract: dict, kind: str) -> bool:
    sections = contract.get("sections") if isinstance(contract, dict) else None
    behavior = sections.get("behavior") if isinstance(sections, dict) else None
    if not isinstance(behavior, list):
        return False
    return any(isinstance(case, dict) and case.get("kind") == kind for case in behavior)


def _evaluation_status(skill_path: Path) -> tuple[str, str, object | None]:
    """Report optional SkillOpt evidence without treating absence as failure."""
    eval_root = skill_path / "evals"
    if not eval_root.is_dir() or eval_root.is_symlink():
        return "not-applicable", "No optional evaluation corpus is enabled", None
    manifest = eval_root / "manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        return "fail", "evals/ exists but manifest.json is missing", None
    try:
        if skill_gate is None:
            return "fail", "SkillOpt gate module is unavailable", None
        loaded = skill_gate.load_manifest(manifest)
        trust = loaded.get("evaluator_trust") if isinstance(loaded, dict) else None
        if trust != "trusted":
            return "fail", "Evaluation corpus is present but evaluator trust is not 'trusted'; no quality conclusion is available", loaded
        return "pass", "Immutable train/selection/holdout manifest is valid", loaded
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as exc:
        return "fail", f"Evaluation manifest is not usable: {exc}", None


def audit_skill(skill_path: Path, run_tests: bool = False) -> dict:
    skill_path = skill_path.expanduser()
    checks = []
    if skill_path.is_symlink() or not skill_path.is_dir():
        return {
            "schema_version": 1,
            "skill": str(skill_path),
            "verdict": "not-ready",
            "checks": [_check("skill-directory", "fail", "Skill path must be a real directory")],
        }
    skill_path = skill_path.resolve()

    entries = _discover_entrypoints(skill_path)
    if entries:
        checks.append(_check("deterministic-entrypoints", "pass", "Reusable script entrypoints found", entries))
    else:
        checks.append(_check("deterministic-entrypoints", "fail", "No safe script entrypoint found under scripts/"))

    contract, contract_error = _load_contract(skill_path)
    if contract_error:
        checks.append(_check("contract", "fail", f"Cannot read skill contract: {contract_error}"))
    elif contract is None:
        checks.append(_check("contract", "fail", "tests/skill_contract.json is missing"))
    else:
        valid, message = quick_validate._validate_contract(skill_path)
        checks.append(_check("contract", "pass" if valid else "fail", message))

    test_files = sorted(
        path.relative_to(skill_path).as_posix()
        for path in (skill_path / "tests").rglob("test_*.py")
        if path.is_file() and not path.is_symlink()
    ) if (skill_path / "tests").is_dir() else []
    if test_files:
        checks.append(_check("automated-tests", "pass", "Discoverable automated tests found", test_files))
    else:
        checks.append(_check("automated-tests", "fail", "No tests/test_*.py files found"))

    command = None
    try:
        command = quick_validate._verification_command(skill_path, contract)
        checks.append(_check("test-command", "pass", "A bounded test command is available", command))
    except (OSError, ValueError) as exc:
        checks.append(_check("test-command", "fail", str(exc)))

    git_before_tests = None
    if run_tests and command is not None:
        git_before_tests = quick_validate.inspect_git_versioning(skill_path)
        try:
            quick_validate._run_verification_tests(skill_path, contract)
            git_after_tests = quick_validate.inspect_git_versioning(skill_path)
            if git_before_tests.get("status") == "versioned_clean" and git_after_tests.get("status") != "versioned_clean":
                checks.append(_check("test-execution", "fail", "Tests changed the Skill tree or Git provenance became unavailable", git_after_tests))
            else:
                checks.append(_check("test-execution", "pass", "Declared/default test command passed"))
        except ValueError as exc:
            checks.append(_check("test-execution", "fail", str(exc)))
    else:
        checks.append(_check("test-execution", "not-run", "Use --run-tests to execute the bounded test command"))

    eval_status, eval_message, eval_evidence = _evaluation_status(skill_path)
    checks.append(_check("skillopt-evidence", eval_status, eval_message, eval_evidence))

    if isinstance(contract, dict) and _contract_case(contract, "idempotence"):
        checks.append(_check("idempotence", "pass", "Contract declares repeated-run behavior"))
    else:
        checks.append(_check("idempotence", "fail", "Contract lacks an idempotence behavior case"))
    if isinstance(contract, dict) and _contract_case(contract, "tool_or_permission_failure"):
        checks.append(_check("failure-handling", "pass", "Contract declares tool/permission failure behavior"))
    else:
        checks.append(_check("failure-handling", "fail", "Contract lacks tool/permission failure behavior"))

    git = quick_validate.inspect_git_versioning(skill_path)
    git_status = "pass" if git.get("status") == "versioned_clean" else "fail"
    checks.append(_check("git-provenance", git_status, git.get("message", "Git provenance unavailable"), git))

    required = {"deterministic-entrypoints", "contract", "automated-tests", "test-command", "idempotence", "failure-handling", "git-provenance"}
    passed = {item["id"] for item in checks if item["status"] == "pass"}
    failed = {item["id"] for item in checks if item["status"] == "fail"}
    executed = "test-execution" in {item["id"] for item in checks if item["status"] == "pass"}
    if required <= passed and run_tests and executed:
        verdict = "ready"
    elif failed:
        verdict = "partial" if passed else "not-ready"
    else:
        verdict = "partial"
    return {
        "schema_version": 1,
        "skill": str(skill_path),
        "verdict": verdict,
        "execution_requested": run_tests,
        "checks": checks,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit whether a Codex Skill is ready for safe automation")
    parser.add_argument("skill_directory", help="Path to the Skill directory")
    parser.add_argument("--run-tests", action="store_true", help="Execute the bounded declared/default tests")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args(argv)
    try:
        report = audit_skill(Path(args.skill_directory), args.run_tests)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[{report['verdict'].upper()}] {report['skill']}")
        for item in report["checks"]:
            print(f"- {item['id']}: {item['status']} - {item['message']}")
    return 0 if report["verdict"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
