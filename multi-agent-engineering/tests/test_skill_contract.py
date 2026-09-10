#!/usr/bin/env python3
"""Regression tests for multi-agent-engineering contracts and local checks."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = SKILL_DIR / "tests" / "skill_contract.json"
CHECK_SCRIPT = SKILL_DIR / "scripts" / "check_skill.py"
CREATOR_VALIDATE = Path(
    "/Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py"
)


class SkillContractTests(unittest.TestCase):
    def test_contract_exists_and_schema_is_valid(self):
        self.assertTrue(CONTRACT_PATH.is_file())
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["skill"], "multi-agent-engineering")
        sections = contract["sections"]
        self.assertEqual(set(sections), {"routing", "behavior", "completion"})
        kinds = [case["kind"] for case in sections["routing"]]
        self.assertGreaterEqual(kinds.count("positive"), 3)
        self.assertGreaterEqual(kinds.count("nonstandard_positive"), 2)
        self.assertGreaterEqual(kinds.count("negative"), 2)
        self.assertGreaterEqual(kinds.count("adjacent"), 2)
        behavior_kinds = {case["kind"] for case in sections["behavior"]}
        self.assertTrue(
            {"success", "invalid_input", "tool_or_permission_failure", "idempotence"}.issubset(
                behavior_kinds
            )
        )
        for case in sections["completion"]:
            self.assertTrue(case["artifact"].strip())
            self.assertTrue(case["assertions"])

    def test_negative_and_adjacent_boundaries_are_in_contract(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        routing = {case["id"]: case for case in contract["sections"]["routing"]}
        self.assertIn("ordinary-function-no-agents", routing)
        self.assertEqual(routing["ordinary-function-no-agents"]["kind"], "negative")
        self.assertIn("skill-creator-engineering-request", routing)
        self.assertEqual(routing["skill-creator-engineering-request"]["kind"], "adjacent")
        description = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not use for ordinary single-session coding", description)
        self.assertIn("skill-creator", description)

    def test_check_skill_cli_requires_directory_and_is_idempotent(self):
        missing = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT)],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        first = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), str(SKILL_DIR)],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        second = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), str(SKILL_DIR)],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("OK", first.stdout)
        self.assertEqual(first.stdout, second.stdout)

    def test_check_skill_rejects_broken_tree(self):
        with tempfile.TemporaryDirectory(prefix="mae-skill-") as tmp:
            bogus = Path(tmp) / "not-a-skill"
            bogus.mkdir()
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(bogus)],
                cwd=SKILL_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL", result.stdout)

    def test_markdown_links_resolve(self):
        result = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), str(SKILL_DIR)],
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_creator_require_contract_is_not_engineering(self):
        if not CREATOR_VALIDATE.is_file():
            self.skipTest("skill-creator quick_validate.py is not available")
        contract = subprocess.run(
            [sys.executable, str(CREATOR_VALIDATE), str(SKILL_DIR), "--require-contract"],
            capture_output=True,
            text=True,
            check=False,
        )
        engineering = subprocess.run(
            [sys.executable, str(CREATOR_VALIDATE), str(SKILL_DIR), "--engineering"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(contract.returncode, 0, contract.stdout + contract.stderr)
        self.assertNotEqual(engineering.returncode, 0)
        self.assertRegex(
            (engineering.stdout + engineering.stderr).lower(),
            r"provenance|untracked|git versioning is dirty",
        )


if __name__ == "__main__":
    unittest.main()
