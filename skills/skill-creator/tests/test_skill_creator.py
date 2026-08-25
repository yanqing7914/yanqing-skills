#!/usr/bin/env python3
"""Contract and regression tests for Skill Creator engineering tooling.

These tests intentionally exercise the public module/CLI boundaries rather than
copying implementation details into the assertions.  The fixtures model a
complete Skill tree so a passing selection gate proves that resources were
evaluated and staged together with ``SKILL.md``.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run Git for an isolated fixture repository."""
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr or result.stdout}")
    return result


def initialize_clean_git_repo(repo: Path) -> None:
    run_git(repo, "init", "--quiet")
    run_git(repo, "config", "user.email", "skill-creator-tests@example.invalid")
    run_git(repo, "config", "user.name", "Skill Creator Tests")
    run_git(repo, "add", "--all")
    run_git(repo, "commit", "--quiet", "-m", "fixture baseline")


def make_skill(root: Path, name: str, marker: str, complete_tree: bool = True) -> Path:
    """Create a deterministic, valid-enough Skill fixture for gate tests."""
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: A fixture skill used by deterministic evaluation tests.\n"
        "---\n\n"
        f"# {name}\n\nmarker: {marker}\n",
        encoding="utf-8",
    )
    if complete_tree:
        (skill / "scripts").mkdir()
        runner = skill / "scripts" / "runner.py"
        runner.write_text(f"#!/usr/bin/env python3\nVALUE = {marker!r}\n", encoding="utf-8")
        runner.chmod(0o755)
        (skill / "references").mkdir()
        (skill / "references" / "workflow.md").write_text(
            f"# Workflow\n\nFixture marker: {marker}\n", encoding="utf-8"
        )
        (skill / "assets").mkdir()
        (skill / "assets" / "template.txt").write_text(f"asset:{marker}\n", encoding="utf-8")
        (skill / "agents").mkdir()
        (skill / "agents" / "openai.yaml").write_text(
            "interface:\n"
            f"  display_name: \"{name}\"\n"
            "  short_description: \"Fixture Skill for gate tests\"\n"
            f"  default_prompt: \"Use ${name} for fixture validation.\"\n",
            encoding="utf-8",
        )
    return skill


def add_engineering_contract(skill: Path) -> None:
    """Reuse the checked-in contract to isolate Git failures from contract failures."""
    tests_dir = skill / "tests"
    tests_dir.mkdir()
    shutil.copy2(ROOT / "tests" / "skill_contract.json", tests_dir / "skill_contract.json")


def make_cases(path: Path, count: int = 12) -> None:
    rows = [{"id": f"case-{index:02d}", "prompt": f"fixture prompt {index}"} for index in range(count)]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def make_manifest(tmp_path: Path, splitter):
    source = tmp_path / "cases.jsonl"
    make_cases(source)
    eval_dir = tmp_path / "evals"
    manifest = splitter.create_splits(
        source,
        eval_dir,
        seed=19,
        train_ratio=0.5,
        selection_ratio=0.25,
        evaluator_name="fixture-evaluator",
        evaluator_version="2026-08-19",
    )
    return source, eval_dir, manifest, eval_dir / "manifest.json"


def result_artifact(
    path: Path,
    manifest_path: Path,
    manifest: dict,
    skill_fingerprint: str,
    split: str,
    scores: dict[str, float],
    *,
    manifest_override: str | None = None,
    evaluator_override: dict | None = None,
    fingerprint_override: str | None = None,
    evidence: str | None = "fixture-evidence",
) -> Path:
    """Write a result artifact using the versioned provenance contract."""
    rows = []
    for case_id, score in scores.items():
        row = {"id": case_id, "score": score}
        if evidence is not None:
            row["evidence"] = evidence
        rows.append(row)
    write_json(
        path,
        {
            "schema_version": 1,
            "split": split,
            "manifest_sha256": manifest_override or sha256(manifest_path),
            "skill_fingerprint": fingerprint_override or skill_fingerprint,
            "evaluator": evaluator_override or manifest["evaluator"],
            "results": rows,
        },
    )
    return path


def run_gate(gate, args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = gate.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def run_validator(validator, args: list[str]) -> tuple[int, str, str]:
    """Invoke the validator CLI while preserving argparse's exit boundary."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = validator.main(args)
        except SystemExit as exc:
            code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()


class SkillCreatorTests(unittest.TestCase):
    def test_validator_accepts_minimal_skill_without_external_yaml(self):
        validator = load("quick_validate_minimal", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A useful demo skill\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            valid, message = validator.validate_skill(skill)
            self.assertTrue(valid, message)

    def test_fallback_frontmatter_accepts_documented_collections(self):
        validator = load("fallback_frontmatter_collections", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: demo\n"
                "description: A useful demo skill\n"
                "allowed-tools: [\"git\", \"rg\"]\n"
                "metadata:\n"
                "  requires:\n"
                "    bins:\n"
                "      - demo-cli\n"
                "---\n\n# Demo\n",
                encoding="utf-8",
            )
            validator.yaml = None
            valid, message = validator.validate_skill(skill)
            self.assertTrue(valid, message)

    def test_fallback_frontmatter_accepts_flow_mapping_and_yaml_quoted_apostrophes(self):
        validator = load("fallback_frontmatter_flow_values", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: demo\n"
                "description: 'A useful demo skill with ''quoted'' text'\n"
                "metadata: {tools: [{url: https://example.com, type: mcp}], mode: safe}\n"
                "---\n\n# Demo\n",
                encoding="utf-8",
            )
            validator.yaml = None
            valid, message = validator.validate_skill(skill)
            self.assertTrue(valid, message)

    def test_init_and_metadata_generation(self):
        initializer = load("init_skill", SCRIPTS / "init_skill.py")
        validator = load("init_metadata_validator", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = initializer.init_skill("demo-skill", tmp, ["scripts"], False, [])
            self.assertIsNotNone(result)
            skill = Path(result)
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertTrue((skill / "agents/openai.yaml").is_file())
            self.assertTrue((skill / "scripts").is_dir())
            metadata = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn("default_prompt:", metadata)
            self.assertIn("$demo-skill", metadata)
            self.assertIn("TODO", (skill / "SKILL.md").read_text(encoding="utf-8"))
            valid, message = validator.validate_skill(skill)
            self.assertFalse(valid)
            self.assertRegex(message.lower(), r"placeholder|invalid yaml")

    def test_metadata_generation_preserves_existing_optional_fields(self):
        generator = load("metadata_preservation", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            agents = skill / "agents"
            agents.mkdir()
            metadata_path = agents / "openai.yaml"
            metadata_path.write_text(
                "interface:\n"
                "  display_name: \"Existing Demo\"\n"
                "  short_description: \"Existing demo Skill metadata\"\n"
                "  default_prompt: \"Use $demo-skill for the existing workflow.\"\n"
                "  icon_small: \"./assets/small.svg\"\n"
                "  icon_large: \"./assets/large.png\"\n",
                encoding="utf-8",
            )
            result = generator.write_openai_yaml(skill, "demo-skill", ["short_description=Updated demo Skill metadata"])
            self.assertTrue(result)
            metadata = metadata_path.read_text(encoding="utf-8")
            self.assertIn('icon_small: "./assets/small.svg"', metadata)
            self.assertIn('icon_large: "./assets/large.png"', metadata)
            self.assertIn('default_prompt: "Use $demo-skill for the existing workflow."', metadata)
            self.assertIn('short_description: "Updated demo Skill metadata"', metadata)
            metadata_path.chmod(0o754)
            self.assertTrue(generator.write_openai_yaml(skill, "demo-skill", ["short_description=Updated demo Skill metadata"]))
            self.assertEqual(metadata_path.stat().st_mode & 0o777, 0o754)

    def test_metadata_generation_rejects_symlinked_targets(self):
        generator = load("metadata_symlink_safety", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            outside = root / "outside.yaml"
            outside.write_text("outside\n", encoding="utf-8")
            agents = skill / "agents"
            agents.mkdir()
            (agents / "openai.yaml").symlink_to(outside)
            self.assertIsNone(
                generator.write_openai_yaml(skill, "demo-skill", [])
            )
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

            (agents / "openai.yaml").unlink()
            shutil.rmtree(agents)
            outside_agents = root / "outside-agents"
            outside_agents.mkdir()
            agents.symlink_to(outside_agents, target_is_directory=True)
            self.assertIsNone(
                generator.write_openai_yaml(skill, "demo-skill", [])
            )
            self.assertFalse((outside_agents / "openai.yaml").exists())

    def test_metadata_generation_updates_only_top_level_interface(self):
        generator = load("metadata_interface_boundary", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            agents = skill / "agents"
            agents.mkdir()
            metadata_path = agents / "openai.yaml"
            metadata_path.write_text(
                "dependencies:\n"
                "  interface:\n"
                "    mode: \"opaque\"\n"
                "interface: # top level\n"
                "  display_name: \"Existing Demo\"\n"
                "  short_description: \"Existing demo Skill metadata\"\n"
                "  default_prompt: \"Use $demo-skill for the existing workflow.\"\n"
                "policy:\n"
                "  allow: true\n",
                encoding="utf-8",
            )
            self.assertTrue(generator.write_openai_yaml(skill, "demo-skill", ["short_description=Updated demo Skill metadata"]))
            metadata = metadata_path.read_text(encoding="utf-8")
            self.assertIn("dependencies:\n  interface:\n    mode: \"opaque\"", metadata)
            self.assertIn("short_description: \"Updated demo Skill metadata\"", metadata)
            self.assertEqual(metadata.count("interface:"), 2)

    def test_metadata_generation_rejects_non_mapping_interface_in_fallback(self):
        generator = load("metadata_invalid_interface", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            agents = skill / "agents"
            agents.mkdir()
            metadata = agents / "openai.yaml"
            metadata.write_text("interface: null\n", encoding="utf-8")
            previous_yaml = sys.modules.get("yaml", None)
            sys.modules["yaml"] = None
            try:
                self.assertIsNone(generator.write_openai_yaml(skill, "demo-skill", []))
            finally:
                if previous_yaml is None:
                    sys.modules.pop("yaml", None)
                else:
                    sys.modules["yaml"] = previous_yaml

    def test_metadata_generation_fallback_strips_frontmatter_comments(self):
        generator = load("metadata_frontmatter_comment", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill # routing name\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            previous_yaml = sys.modules.get("yaml")
            sys.modules["yaml"] = None
            try:
                self.assertEqual(generator.read_frontmatter_name(skill), "demo-skill")
            finally:
                if previous_yaml is None:
                    sys.modules.pop("yaml", None)
                else:
                    sys.modules["yaml"] = previous_yaml

    def test_fallback_metadata_supports_documented_extra_sections(self):
        validator = load("fallback_extended_metadata_validator", SCRIPTS / "quick_validate.py")
        generator = load("fallback_extended_metadata_generator", SCRIPTS / "generate_openai_yaml.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            agents = skill / "agents"
            agents.mkdir()
            metadata_path = agents / "openai.yaml"
            original_yaml = (
                "interface:\n"
                "  display_name: \"Demo Skill\"\n"
                "  short_description: \"A complete demo Skill metadata\"\n"
                "  default_prompt: \"Use $demo-skill for this workflow.\"\n"
                "dependencies:\n"
                "  tools:\n"
                "    - type: \"mcp\"\n"
                "      value: \"example\"\n"
                "policy:\n"
                "  allow_implicit_invocation: true\n"
            )
            metadata_path.write_text(original_yaml, encoding="utf-8")
            validator.yaml = None
            missing_yaml = object()
            previous_yaml_module = sys.modules.get("yaml", missing_yaml)
            sys.modules["yaml"] = None
            try:
                valid, message = validator.validate_skill(skill)
                self.assertTrue(valid, message)
                self.assertTrue(
                    generator.write_openai_yaml(
                        skill, "demo-skill", ["short_description=Updated demo Skill metadata"]
                    )
                )
            finally:
                if previous_yaml_module is missing_yaml:
                    sys.modules.pop("yaml", None)
                else:
                    sys.modules["yaml"] = previous_yaml_module
            rewritten = metadata_path.read_text(encoding="utf-8")
            self.assertIn("dependencies:", rewritten)
            self.assertIn("policy:", rewritten)
            self.assertIn("value: \"example\"", rewritten)

    def test_fallback_metadata_accepts_inline_comments_and_rejects_non_mapping_interface(self):
        validator = load("fallback_metadata_comments", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A complete demo Skill.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            agents = skill / "agents"
            agents.mkdir()
            metadata = agents / "openai.yaml"
            metadata.write_text(
                "interface: # top-level comment\n"
                "    display_name: \"Demo Skill\" # title\n"
                "    short_description: \"A complete demo Skill metadata\" # desc\n"
                "    default_prompt: \"Use $demo-skill.\" # prompt\n",
                encoding="utf-8",
            )
            validator.yaml = None
            valid, message = validator.validate_skill(skill)
            self.assertTrue(valid, message)
            metadata.write_text("interface: null\n", encoding="utf-8")
            valid, message = validator.validate_skill(skill)
            self.assertFalse(valid)
            self.assertIn("interface must be", message)

    def test_init_evaluation_scaffold_is_honest(self):
        initializer = load("init_skill_evals", SCRIPTS / "init_skill.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = initializer.init_skill("eval-skill", tmp, [], False, [], True)
            self.assertIsNotNone(result)
            eval_dir = Path(result) / "evals"
            self.assertTrue((eval_dir / "EVALUATION.md").is_file())
            self.assertFalse((eval_dir / "manifest.json").exists())

    def test_initializer_rejects_path_traversal_name(self):
        initializer = load("init_skill_path_safety", SCRIPTS / "init_skill.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = initializer.init_skill("../outside", tmp, [], False, [])
            self.assertIsNone(result)
            self.assertFalse((Path(tmp).parent / "outside").exists())

    def test_initializer_rejects_path_traversal_resource(self):
        initializer = load("init_resource_safety", SCRIPTS / "init_skill.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = initializer.init_skill("safe-skill", tmp, ["../outside"], False, [])
            self.assertIsNone(result)
            self.assertFalse((Path(tmp).parent / "outside").exists())

    def test_generated_skill_can_be_completed_then_validated(self):
        initializer = load("init_skill_generated", SCRIPTS / "init_skill.py")
        validator = load("quick_validate_generated", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = initializer.init_skill("demo-skill", tmp, ["scripts", "references"], False, [])
            self.assertIsNotNone(result)
            skill = Path(result)
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A completed demo skill for validation.\n---\n\n"
                "# Demo Skill\n\nFollow the documented workflow.\n",
                encoding="utf-8",
            )
            valid, message = validator.validate_skill(skill)
            self.assertTrue(valid, message)

    def test_validator_rejects_broken_local_reference(self):
        validator = load("quick_validate_refs", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A useful demo skill\n---\n\n"
                "Read [missing](references/missing.md).\n",
                encoding="utf-8",
            )
            valid, message = validator.validate_skill(skill)
            self.assertFalse(valid)
            self.assertIn("Broken local reference", message)

    def test_validator_rejects_broken_reference_inside_reference_resource(self):
        validator = load("quick_validate_reference_links", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            references = skill / "references"
            references.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A useful demo skill\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (references / "workflow.md").write_text(
                "# Workflow\n\nSee [missing](missing.md).\n", encoding="utf-8"
            )
            valid, message = validator.validate_skill(skill)
            self.assertFalse(valid)
            self.assertIn("Broken local reference", message)

    def test_skill_contract_is_strict_and_engineering_requires_git_provenance(self):
        validator = load("quick_validate_contract", SCRIPTS / "quick_validate.py")
        contract_path = ROOT / "tests" / "skill_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract.get("schema_version"), 1)
        sections = contract["sections"]
        self.assertEqual(set(sections), {"routing", "behavior", "completion"})
        all_ids = []
        for section_name, cases in sections.items():
            self.assertTrue(cases, section_name)
            for case in cases:
                all_ids.append(case["id"])
                self.assertTrue(case.get("evidence"), f"missing evidence in {section_name}/{case['id']}")
                if section_name == "routing":
                    self.assertTrue(case.get("prompt"))
                    self.assertTrue(case.get("expected_action"))
                elif section_name == "behavior":
                    self.assertTrue(case.get("scenario"))
                    self.assertTrue(case.get("assertions"))
                else:
                    self.assertTrue(case.get("artifact"))
                    self.assertTrue(case.get("assertions"))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        valid, message = validator.validate_skill(ROOT, require_contract=True)
        self.assertTrue(valid, message)
        # Keep the no-Git assertion isolated from wherever this Skill directory
        # is checked out; a parent repository must not change this regression.
        with tempfile.TemporaryDirectory() as tmp:
            unversioned = make_skill(Path(tmp), "unversioned-demo", "clean")
            (unversioned / "tests").mkdir()
            shutil.copy2(contract_path, unversioned / "tests" / "skill_contract.json")
            git_report = validator.inspect_git_versioning(unversioned)
            self.assertEqual(git_report["status"], "not_versioned")
            self.assertEqual(git_report["source_provenance"], "unavailable")
            self.assertIn("provenance unavailable", git_report["message"].lower())
            valid, message = validator.validate_engineering_contract(unversioned)
            self.assertFalse(valid)
            self.assertIn("provenance unavailable", message.lower())

    def test_validator_cli_keeps_static_git_and_engineering_semantics_separate(self):
        validator = load("quick_validate_cli_boundaries", SCRIPTS / "quick_validate.py")

        code, stdout, stderr = run_validator(validator, [str(ROOT)])
        self.assertEqual(code, 0, stderr or stdout)
        self.assertIn("No optional evaluation corpus", stdout)
        self.assertEqual(stderr, "")

        code, stdout, stderr = run_validator(validator, [str(ROOT), "--require-contract"])
        self.assertEqual(code, 0, stderr or stdout)
        self.assertIn("No optional evaluation corpus", stdout)

        # Use a deliberately unversioned fixture for provenance semantics so
        # this test remains stable if the source tree is later placed in Git.
        with tempfile.TemporaryDirectory() as tmp:
            unversioned = make_skill(Path(tmp), "cli-unversioned", "clean")
            (unversioned / "tests").mkdir()
            shutil.copy2(ROOT / "tests" / "skill_contract.json", unversioned / "tests" / "skill_contract.json")
            code, stdout, stderr = run_validator(validator, [str(unversioned), "--git", "--json"])
            self.assertEqual(code, 1)
            report = json.loads(stdout)
            self.assertEqual(report["status"], "not_versioned")
            self.assertEqual(report["source_provenance"], "unavailable")
            self.assertIsNone(report["head"])
            self.assertEqual(stderr, "")

            code, stdout, stderr = run_validator(validator, [str(unversioned), "--engineering"])
            self.assertEqual(code, 1)
            self.assertIn("provenance unavailable", stdout.lower())
            self.assertEqual(stderr, "")

        code, stdout, stderr = run_validator(validator, [str(ROOT), "--git", "--engineering"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("cannot be combined", stderr)

    def test_git_inspection_accepts_clean_parent_repository(self):
        validator = load("quick_validate_git_parent", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repository"
            skill = make_skill(repo / "skills", "parent-skill", "clean")
            add_engineering_contract(skill)
            initialize_clean_git_repo(repo)
            report = validator.inspect_git_versioning(skill)
            self.assertEqual(report["status"], "versioned_clean")
            self.assertEqual(report["scope"], "parent")
            self.assertRegex(report["head"], r"^[0-9a-f]{40}$")
            self.assertTrue(any(path.endswith("SKILL.md") for path in report["tracked_files"]))
            self.assertEqual(report["dirty_files"], [])

    def test_git_inspection_rejects_untracked_and_ignored_material(self):
        validator = load("quick_validate_git_dirty", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repository"
            repo.mkdir()
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            initialize_clean_git_repo(repo)
            skill = make_skill(repo / "skills", "untracked-skill", "untracked")
            add_engineering_contract(skill)
            report = validator.inspect_git_versioning(skill)
            self.assertEqual(report["status"], "versioned_dirty")
            self.assertTrue(any(path.endswith("SKILL.md") for path in report["untracked_files"]))

            (repo / ".gitignore").write_text(
                "skills/untracked-skill/assets/runtime-output.txt\n", encoding="utf-8"
            )
            run_git(repo, "add", ".gitignore")
            run_git(repo, "commit", "--quiet", "-m", "add ignore rule")
            ignored = skill / "assets" / "runtime-output.txt"
            ignored.write_text("hidden material\n", encoding="utf-8")
            report = validator.inspect_git_versioning(skill)
            self.assertEqual(report["status"], "versioned_dirty")
            self.assertTrue(any(path.endswith("runtime-output.txt") for path in report["ignored_files"]))
            self.assertTrue(any(path.endswith("runtime-output.txt") for path in report["dirty_files"]))

    def test_git_inspection_rejects_staged_only_and_uncommitted_changes(self):
        validator = load("quick_validate_git_staged", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_skill(Path(tmp), "dirty-skill", "baseline")
            add_engineering_contract(skill)
            initialize_clean_git_repo(skill)
            skill_md = skill / "SKILL.md"
            baseline = skill_md.read_text(encoding="utf-8")
            skill_md.write_text(baseline + "staged\n", encoding="utf-8")
            run_git(skill, "add", "SKILL.md")
            skill_md.write_text(baseline, encoding="utf-8")
            report = validator.inspect_git_versioning(skill)
            self.assertEqual(report["status"], "versioned_dirty")
            self.assertIn("SKILL.md", report["staged_files"])
            self.assertIn("SKILL.md", report["dirty_files"])

    def test_git_inspection_fails_closed_when_unavailable_or_invalid(self):
        validator = load("quick_validate_git_runner", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_skill(Path(tmp), "git-runner", "clean")
            calls = []

            def unavailable(command):
                calls.append(command)
                raise FileNotFoundError("git unavailable")

            report = validator.inspect_git_versioning(skill, git_runner=unavailable)
            self.assertTrue(calls)
            self.assertEqual(report["status"], "git_unavailable")
            self.assertEqual(report["dirty_files"], [])

            def broken(command):
                return subprocess.CompletedProcess(command, 128, "", "fatal: synthetic git failure")

            report = validator.inspect_git_versioning(skill, git_runner=broken)
            self.assertEqual(report["status"], "invalid")
            self.assertIn("synthetic git failure", report["message"])

    def test_git_inspection_rejects_symlinked_material(self):
        validator = load("quick_validate_git_symlink", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_skill(Path(tmp), "symlink-skill", "bad")
            (skill / "references" / "linked.md").symlink_to(skill / "SKILL.md")
            report = validator.inspect_git_versioning(skill)
            self.assertEqual(report["status"], "invalid")
            self.assertIn("symlink", report["message"].lower())

    def test_contract_validator_rejects_missing_routing_evidence(self):
        validator = load("quick_validate_contract_negative", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_skill(Path(tmp), "contract-demo", "ok", complete_tree=True)
            contract_dir = skill / "tests"
            contract_dir.mkdir()
            contract = {
                "schema_version": 1,
                "sections": {
                    "routing": [
                        {"id": "p1", "kind": "positive", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "p2", "kind": "positive", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "p3", "kind": "positive", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "np1", "kind": "nonstandard_positive", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "np2", "kind": "nonstandard_positive", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "n1", "kind": "negative", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "n2", "kind": "negative", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "a1", "kind": "adjacent", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                        {"id": "a2", "kind": "adjacent", "prompt": "x", "expected_action": "y", "evidence": ["x"]},
                    ],
                    "behavior": [
                        {"id": "success", "kind": "success", "scenario": "x", "assertions": ["x"], "evidence": ["x"]},
                        {"id": "invalid", "kind": "invalid_input", "scenario": "x", "assertions": ["x"], "evidence": ["x"]},
                        {"id": "tool", "kind": "tool_or_permission_failure", "scenario": "x", "assertions": ["x"], "evidence": ["x"]},
                        {"id": "idem", "kind": "idempotence", "scenario": "x", "assertions": ["x"], "evidence": ["x"]},
                    ],
                    "completion": [
                        {"id": "done", "artifact": "x", "assertions": ["x"], "evidence": []}
                    ],
                },
            }
            write_json(contract_dir / "skill_contract.json", contract)
            valid, message = validator.validate_engineering_contract(skill)
            self.assertFalse(valid)
            self.assertIn("evidence", message.lower())

    def test_split_manifest_has_three_disjoint_splits_and_alias(self):
        splitter = load("split_skill_cases", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, eval_dir, manifest, manifest_path = make_manifest(tmp_path, splitter)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(set(manifest["splits"]), {"train", "selection", "holdout"})
            self.assertEqual(manifest["splits"]["holdout"], [
                json.loads(line)["id"] for line in (eval_dir / "holdout.jsonl").read_text().splitlines()
            ])
            self.assertEqual(
                (eval_dir / "holdout.jsonl").read_bytes(), (eval_dir / "test.jsonl").read_bytes()
            )
            all_ids = [case_id for ids in manifest["splits"].values() for case_id in ids]
            self.assertEqual(len(all_ids), len(set(all_ids)))
            self.assertEqual(sha256(manifest_path), sha256(manifest_path))

    def test_split_manifest_resolves_relative_source_for_reload(self):
        splitter = load("split_skill_cases_relative_source", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_relative_source", SCRIPTS / "skill_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            make_cases(source)
            eval_dir = root / "evals"
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                manifest = splitter.create_splits(Path("cases.jsonl"), eval_dir)
            finally:
                os.chdir(previous_cwd)
            self.assertTrue(Path(manifest["source"]).is_absolute())
            self.assertEqual(gate.load_manifest(eval_dir / "manifest.json")["source_sha256"], manifest["source_sha256"])

    def test_splitter_rejects_duplicate_source_ids(self):
        splitter = load("split_skill_cases_duplicate", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "duplicate.jsonl"
            source.write_text('{"id":"same"}\n{"id":"same"}\n{"id":"other"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate case id"):
                splitter.create_splits(source, Path(tmp) / "evals")

    def test_splitter_rejects_source_inside_output_directory(self):
        splitter = load("split_skill_cases_source_collision", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evals"
            output.mkdir()
            source = output / "train.jsonl"
            make_cases(source)
            with self.assertRaisesRegex(ValueError, "outside output_dir"):
                splitter.create_splits(source, output)

    def test_manifest_rejects_symlinked_split_file(self):
        splitter = load("split_skill_cases_manifest_symlink", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_manifest_symlink", SCRIPTS / "skill_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            _, eval_dir, _, manifest_path = make_manifest(Path(tmp), splitter)
            real_split = eval_dir / "train.jsonl"
            moved = eval_dir / "train-real.jsonl"
            real_split.rename(moved)
            real_split.symlink_to(moved)
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                gate.load_manifest(manifest_path)

    def test_manifest_requires_complete_source_id_coverage(self):
        splitter = load("split_skill_cases_source_coverage", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_source_coverage", SCRIPTS / "skill_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            _, eval_dir, _, manifest_path = make_manifest(Path(tmp), splitter)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            removed = manifest["splits"]["train"].pop()
            train_path = eval_dir / "train.jsonl"
            rows = [json.loads(line) for line in train_path.read_text().splitlines() if line.strip()]
            rows = [row for row in rows if row["id"] != removed]
            train_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            manifest["split_files"]["train"]["sha256"] = sha256(train_path)
            manifest["split_files"]["train"]["id_sha256"] = gate.ids_sha256(manifest["splits"]["train"])
            manifest["split_files"]["train"]["count"] = len(manifest["splits"]["train"])
            manifest["counts"]["train"] = len(manifest["splits"]["train"])
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "cover source corpus exactly"):
                gate.load_manifest(manifest_path)

    def test_manifest_rejects_split_payload_mutation_with_same_ids(self):
        """Changing a prompt/fixture must fail even when split hashes are rewritten."""
        splitter = load("split_skill_cases_payload_integrity", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_payload_integrity", SCRIPTS / "skill_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            _, eval_dir, _, manifest_path = make_manifest(Path(tmp), splitter)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            split_path = eval_dir / "selection.jsonl"
            rows = [json.loads(line) for line in split_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            rows[0]["prompt"] = "tampered prompt"
            split_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            manifest["split_files"]["selection"]["sha256"] = sha256(split_path)
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "payload does not match source corpus"):
                gate.load_manifest(manifest_path)

    def test_splitter_rejects_preexisting_output_symlink(self):
        splitter = load("split_skill_cases_output_symlink", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            make_cases(source)
            output = root / "evals"
            output.mkdir()
            outside = root / "outside.jsonl"
            outside.write_text("safe\n", encoding="utf-8")
            (output / "train.jsonl").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                splitter.create_splits(source, output)

    def test_splitter_rejects_symlinked_output_ancestor(self):
        splitter = load("split_skill_cases_output_ancestor", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            make_cases(source)
            outside = root / "outside"
            outside.mkdir()
            linked_parent = root / "linked"
            linked_parent.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink component"):
                splitter.create_splits(source, linked_parent / "nested" / "evals")

    def test_engineering_prompt_requires_exact_skill_token(self):
        validator = load("quick_validate_prompt_boundary", SCRIPTS / "quick_validate.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_skill(root, "foo", "clean")
            add_engineering_contract(skill)
            (skill / "agents" / "openai.yaml").write_text(
                "interface:\n"
                "  display_name: \"Foo\"\n"
                "  short_description: \"A fixture Skill for prompt checks\"\n"
                "  default_prompt: \"Use $foo-bar for this workflow.\"\n",
                encoding="utf-8",
            )
            initialize_clean_git_repo(root)
            valid, message = validator.validate_engineering_contract(skill)
            self.assertFalse(valid)
            self.assertIn("default_prompt", message)

    def test_gate_manifest_rejects_cross_split_leakage(self):
        splitter = load("split_skill_cases_leak", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_manifest", SCRIPTS / "skill_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            _, _, manifest, manifest_path = make_manifest(Path(tmp), splitter)
            leaked = json.loads(manifest_path.read_text(encoding="utf-8"))
            leaked["splits"]["selection"][0] = leaked["splits"]["train"][0]
            write_json(manifest_path, leaked)
            with self.assertRaisesRegex(ValueError, "leaks across splits"):
                gate.load_manifest(manifest_path)

    def _gate_fixture(self, tmp: str):
        tmp_path = Path(tmp)
        splitter = load("split_skill_cases_gate", SCRIPTS / "split_skill_cases.py")
        gate = load("skill_gate_gate", SCRIPTS / "skill_gate.py")
        _, eval_dir, manifest, manifest_path = make_manifest(tmp_path, splitter)
        current = make_skill(tmp_path, "current-skill", "current")
        candidate = make_skill(tmp_path, "candidate-skill", "candidate")
        for skill in (current, candidate):
            tests_dir = skill / "tests"
            tests_dir.mkdir()
            shutil.copy2(ROOT / "tests" / "skill_contract.json", tests_dir / "skill_contract.json")
        # The selection gate deliberately requires source Git provenance for
        # both sides; commit the complete fixture tree in its temp repository.
        initialize_clean_git_repo(tmp_path)
        current_fp = gate.skill_tree_fingerprint(current)["sha256"]
        candidate_fp = gate.skill_tree_fingerprint(candidate)["sha256"]
        selection_ids = manifest["splits"]["selection"]
        current_scores = {case_id: 0.0 for case_id in selection_ids}
        candidate_scores = {case_id: 1.0 for case_id in selection_ids}
        current_results = result_artifact(
            eval_dir / "current-selection.json",
            manifest_path,
            manifest,
            current_fp,
            "selection",
            current_scores,
        )
        candidate_results = result_artifact(
            eval_dir / "candidate-selection.json",
            manifest_path,
            manifest,
            candidate_fp,
            "selection",
            candidate_scores,
        )
        return gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results

    def test_gate_accepts_strict_selection_improvement_and_stages_full_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            (
                gate,
                manifest,
                manifest_path,
                eval_dir,
                current,
                candidate,
                current_results,
                candidate_results,
            ) = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(
                gate,
                [
                    "--manifest", str(manifest_path),
                    "--current-results", str(current_results),
                    "--candidate-results", str(candidate_results),
                    "--current-skill", str(current),
                    "--candidate-skill", str(candidate),
                    "--state-dir", str(state_dir),
                    "--json",
                ],
            )
            self.assertEqual(code, 0, stderr or stdout)
            report = json.loads(stdout)
            self.assertEqual(report["action"], "accept")
            staged = Path(report["staged_candidate"])
            best = Path(report["best_skill"])
            for relative in (
                "SKILL.md",
                "scripts/runner.py",
                "references/workflow.md",
                "assets/template.txt",
                "agents/openai.yaml",
            ):
                self.assertTrue((staged / relative).is_file(), relative)
                self.assertTrue((best / relative).is_file(), relative)
            self.assertEqual(gate.skill_tree_fingerprint(staged), gate.skill_tree_fingerprint(candidate))
            self.assertEqual(gate.skill_tree_fingerprint(best), gate.skill_tree_fingerprint(candidate))
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8").splitlines()[-1], "marker: current")
            self.assertEqual(report["manifest_sha256"], sha256(manifest_path))
            self.assertEqual(report["evaluator"], manifest["evaluator"])

    def test_gate_rejects_symlinked_state_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()
            outside = Path(tmp) / "outside-runs"
            outside.mkdir()
            (state_dir / "runs").symlink_to(outside, target_is_directory=True)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
            ])
            self.assertEqual(code, 2)
            self.assertIn("symlink", stderr.lower())
            self.assertEqual(list(outside.iterdir()), [])

    def test_splitter_rejects_symlinked_source(self):
        splitter = load("split_skill_cases_source_symlink", SCRIPTS / "split_skill_cases.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_source = root / "real-cases.jsonl"
            make_cases(real_source)
            linked_source = root / "cases.jsonl"
            linked_source.symlink_to(real_source)
            with self.assertRaisesRegex(ValueError, "source corpus must not be a symlink"):
                splitter.create_splits(linked_source, root / "evals")

    def test_gate_rejects_same_score_and_default_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            # Equal scores are not a strict improvement.
            equal_scores = {case_id: 0.0 for case_id in manifest["splits"]["selection"]}
            result_artifact(candidate_results, manifest_path, manifest, gate.skill_tree_fingerprint(candidate)["sha256"], "selection", equal_scores)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
            ])
            self.assertEqual(code, 1, stderr)
            self.assertFalse(state_dir.exists())

            # A mean improvement cannot hide a per-case regression by default.
            current_scores = {case_id: 0.5 for case_id in manifest["splits"]["selection"]}
            candidate_scores = {case_id: 1.0 for case_id in manifest["splits"]["selection"]}
            first_id = next(iter(candidate_scores))
            candidate_scores[first_id] = 0.0
            result_artifact(current_results, manifest_path, manifest, gate.skill_tree_fingerprint(current)["sha256"], "selection", current_scores)
            result_artifact(candidate_results, manifest_path, manifest, gate.skill_tree_fingerprint(candidate)["sha256"], "selection", candidate_scores)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
            ])
            self.assertEqual(code, 1, stderr)
            self.assertFalse(state_dir.exists())

    def test_gate_rejects_nonfinite_and_id_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            data = json.loads(candidate_results.read_text(encoding="utf-8"))
            data["results"][0]["score"] = float("nan")
            write_json(candidate_results, data)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
            ])
            self.assertEqual(code, 2)
            self.assertIn("non-finite", stderr)

            data["results"][0]["score"] = 1.0
            data["results"][0]["id"] = "not-in-manifest"
            write_json(candidate_results, data)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
            ])
            self.assertEqual(code, 2)
            self.assertIn("IDs do not match", stderr)

    def test_gate_rejects_manifest_evaluator_fingerprint_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            cases = [
                ("manifest hash", {"manifest_override": "0" * 64}, "manifest fingerprint"),
                ("evaluator", {"evaluator_override": {"name": "wrong", "version": "0"}}, "evaluator provenance"),
                ("fingerprint", {"fingerprint_override": "f" * 64}, "fingerprint"),
                ("evidence", {"evidence": None}, "evidence"),
            ]
            for label, overrides, expected in cases:
                with self.subTest(label=label):
                    result_artifact(
                        candidate_results,
                        manifest_path,
                        manifest,
                        gate.skill_tree_fingerprint(candidate)["sha256"],
                        "selection",
                        {case_id: 1.0 for case_id in manifest["splits"]["selection"]},
                        **overrides,
                    )
                    code, _, stderr = run_gate(gate, [
                        "--manifest", str(manifest_path), "--current-results", str(current_results),
                        "--candidate-results", str(candidate_results), "--current-skill", str(current),
                        "--candidate-skill", str(candidate), "--state-dir", str(state_dir),
                    ])
                    self.assertEqual(code, 2, stderr)
                    self.assertIn(expected, stderr.lower())

    def test_gate_rejects_candidate_tampered_after_results_were_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            (candidate / "references" / "workflow.md").write_text("tampered\n", encoding="utf-8")
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(Path(tmp) / "state"),
            ])
            self.assertEqual(code, 2)
            self.assertIn("fingerprint", stderr.lower())

    def test_record_holdout_requires_accepted_run_and_is_one_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            holdout_ids = manifest["splits"]["holdout"]
            holdout_results = eval_dir / "candidate-holdout.json"
            candidate_fp = gate.skill_tree_fingerprint(candidate)["sha256"]
            result_artifact(
                holdout_results,
                manifest_path,
                manifest,
                candidate_fp,
                "holdout",
                {case_id: 1.0 for case_id in holdout_ids},
            )
            with self.assertRaisesRegex(ValueError, "accepted staged run"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=candidate,
                    result_path=holdout_results,
                    state_dir=state_dir,
                )

            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            staged = Path(gate_report["staged_candidate"])
            best_before = gate.skill_tree_fingerprint(Path(gate_report["best_skill"]))

            # Holdout must use the accepted candidate fingerprint and manifest hash.
            report = gate.record_holdout(
                manifest_path=manifest_path,
                candidate_skill=staged,
                result_path=holdout_results,
                state_dir=state_dir,
                run_dir=Path(gate_report["run_dir"]),
            )
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["purpose"], "release_evidence_only")
            self.assertEqual(report["manifest_sha256"], sha256(manifest_path))
            self.assertEqual(report["candidate_fingerprint"], gate.skill_tree_fingerprint(staged)["sha256"])
            self.assertTrue((Path(gate_report["run_dir"]) / "holdout_report.json").is_file())
            self.assertEqual(best_before, gate.skill_tree_fingerprint(Path(gate_report["best_skill"])))
            with self.assertRaisesRegex(ValueError, "already recorded"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=holdout_results,
                    state_dir=state_dir,
                    run_dir=Path(gate_report["run_dir"]),
                )

    def test_holdout_rejects_overflowing_aggregate_score(self):
        """Finite per-case scores must not serialize an overflowing mean as Infinity."""
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            staged = Path(gate_report["staged_candidate"])
            holdout_results = eval_dir / "overflow-holdout.json"
            result_artifact(
                holdout_results,
                manifest_path,
                manifest,
                gate.skill_tree_fingerprint(staged)["sha256"],
                "holdout",
                {case_id: 1e308 for case_id in manifest["splits"]["holdout"]},
            )
            with self.assertRaisesRegex(ValueError, "non-finite"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=holdout_results,
                    state_dir=state_dir,
                    run_dir=Path(gate_report["run_dir"]),
                )

    def test_holdout_rejects_wrong_split_and_staged_candidate_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            staged = Path(gate_report["staged_candidate"])
            staged_fp = gate.skill_tree_fingerprint(staged)["sha256"]
            wrong_split = eval_dir / "wrong-holdout.json"
            result_artifact(
                wrong_split,
                manifest_path,
                manifest,
                staged_fp,
                "selection",
                {case_id: 1.0 for case_id in manifest["splits"]["selection"]},
            )
            with self.assertRaisesRegex(ValueError, "expected split='holdout'"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=wrong_split,
                    state_dir=state_dir,
                    run_dir=Path(gate_report["run_dir"]),
                )

            holdout = eval_dir / "holdout.json"
            result_artifact(
                holdout,
                manifest_path,
                manifest,
                staged_fp,
                "holdout",
                {case_id: 1.0 for case_id in manifest["splits"]["holdout"]},
            )
            (staged / "SKILL.md").write_text((staged / "SKILL.md").read_text() + "tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=holdout,
                    state_dir=state_dir,
                    run_dir=Path(gate_report["run_dir"]),
                )

    def test_holdout_rejects_selection_report_without_git_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            run_dir = Path(gate_report["run_dir"])
            gate_report.pop("current_git_provenance", None)
            write_json(run_dir / "gate_report.json", gate_report)
            staged = Path(gate_report["staged_candidate"])
            holdout_results = eval_dir / "candidate-holdout.json"
            result_artifact(
                holdout_results,
                manifest_path,
                manifest,
                gate.skill_tree_fingerprint(staged)["sha256"],
                "holdout",
                {case_id: 1.0 for case_id in manifest["splits"]["holdout"]},
            )
            with self.assertRaisesRegex(ValueError, "current_git_provenance"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=holdout_results,
                    state_dir=state_dir,
                    run_dir=run_dir,
                )

    def test_holdout_rejects_tampered_selection_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            run_dir = Path(gate_report["run_dir"])
            gate_report["candidate_score"] = -999.0
            write_json(run_dir / "gate_report.json", gate_report)
            staged = Path(gate_report["staged_candidate"])
            holdout_results = eval_dir / "candidate-holdout.json"
            result_artifact(
                holdout_results,
                manifest_path,
                manifest,
                gate.skill_tree_fingerprint(staged)["sha256"],
                "holdout",
                {case_id: 1.0 for case_id in manifest["splits"]["holdout"]},
            )
            with self.assertRaisesRegex(ValueError, "candidate_score"):
                gate.record_holdout(
                    manifest_path=manifest_path,
                    candidate_skill=staged,
                    result_path=holdout_results,
                    state_dir=state_dir,
                    run_dir=run_dir,
                )

    def test_holdout_rejects_tampered_git_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            run_dir = Path(gate_report["run_dir"])
            gate_report["candidate_git_provenance"]["head"] = "f" * 40
            gate_report["git_provenance"] = gate_report["candidate_git_provenance"]
            write_json(run_dir / "gate_report.json", gate_report)
            staged = Path(gate_report["staged_candidate"])
            holdout_results = eval_dir / "candidate-holdout.json"
            result_artifact(
                holdout_results, manifest_path, manifest, gate.skill_tree_fingerprint(staged)["sha256"],
                "holdout", {case_id: 1.0 for case_id in manifest["splits"]["holdout"]},
            )
            with self.assertRaisesRegex(ValueError, "Git provenance changed"):
                gate.record_holdout(
                    manifest_path=manifest_path, candidate_skill=staged, result_path=holdout_results,
                    state_dir=state_dir, run_dir=run_dir,
                )

    def test_gate_rejects_nested_symlink_state_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_root = Path(tmp) / "state-root"
            outside = Path(tmp) / "outside"
            outside.mkdir()
            state_root.mkdir()
            (state_root / "link").symlink_to(outside, target_is_directory=True)
            code, _, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_root / "link" / "nested"),
            ])
            self.assertEqual(code, 2)
            self.assertIn("symlink", stderr.lower())
            self.assertFalse((outside / "nested").exists())

    def test_holdout_does_not_mutate_active_and_adopt_keeps_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, manifest, manifest_path, eval_dir, current, candidate, current_results, candidate_results = self._gate_fixture(tmp)
            state_dir = Path(tmp) / "state"
            active_before = gate.skill_tree_fingerprint(current)
            active_text_before = (current / "SKILL.md").read_text(encoding="utf-8")

            code, stdout, stderr = run_gate(gate, [
                "--manifest", str(manifest_path), "--current-results", str(current_results),
                "--candidate-results", str(candidate_results), "--current-skill", str(current),
                "--candidate-skill", str(candidate), "--state-dir", str(state_dir), "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            gate_report = json.loads(stdout)
            staged = Path(gate_report["staged_candidate"])
            holdout_results = eval_dir / "candidate-holdout.json"
            result_artifact(
                holdout_results,
                manifest_path,
                manifest,
                gate.skill_tree_fingerprint(staged)["sha256"],
                "holdout",
                {case_id: 1.0 for case_id in manifest["splits"]["holdout"]},
            )

            gate.record_holdout(
                manifest_path=manifest_path,
                candidate_skill=staged,
                result_path=holdout_results,
                state_dir=state_dir,
                run_dir=Path(gate_report["run_dir"]),
            )
            self.assertEqual(gate.skill_tree_fingerprint(current), active_before)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), active_text_before)

            backup = Path(tmp) / "backup"
            dry_report = gate.adopt_staged_candidate(
                state_dir=state_dir,
                run_dir=Path(gate_report["run_dir"]),
                target_skill=current,
                backup_dir=backup,
                dry_run=True,
            )
            self.assertEqual(dry_report["action"], "would_adopt")
            self.assertFalse(backup.exists())
            self.assertEqual(gate.skill_tree_fingerprint(current), active_before)

            adopt_report = gate.adopt_staged_candidate(
                state_dir=state_dir,
                run_dir=Path(gate_report["run_dir"]),
                target_skill=current,
                backup_dir=backup,
            )
            self.assertEqual(adopt_report["action"], "adopted")
            self.assertTrue(backup.is_dir())
            self.assertEqual(gate.skill_tree_fingerprint(backup), active_before)
            self.assertEqual(gate.skill_tree_fingerprint(current), gate.skill_tree_fingerprint(staged))


if __name__ == "__main__":
    unittest.main(verbosity=2)
