#!/usr/bin/env python3
"""Validate Skill structure, contracts, optional evals, and Git provenance."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

try:
    import yaml
except ModuleNotFoundError:  # Keep structural validation usable in minimal runtimes.
    yaml = None


MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_LINES = 500
REQUIRED_CONTRACT_SECTIONS = {"routing", "behavior", "completion"}
FORBIDDEN_PLACEHOLDER_PATTERN = re.compile(
    r"\[\s*(?:TODO|TBD|FIXME|REPLACE ME|PLACEHOLDER)[^\]]*\]", re.IGNORECASE
)
EXCLUDED_DIRS = {"__pycache__", ".git", ".skill-evals"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _empty_git_report(status, message):
    return {
        "status": status,
        "source_provenance": "available" if status == "versioned_clean" else "unavailable",
        "repository_root": None,
        "scope": None,
        "head": None,
        "tracked_files": [],
        "untracked_files": [],
        "ignored_files": [],
        "dirty_files": [],
        "staged_files": [],
        "missing_files": [],
        "message": message,
    }


def _default_git_runner(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _git_error(result, action):
    detail = (result.stderr or result.stdout or "unknown Git error").strip()
    return _empty_git_report("invalid", f"Git inspection failed while {action}: {detail}")


def _is_material_relative_path(relative):
    relative = PurePosixPath(relative)
    return not any(part in EXCLUDED_DIRS for part in relative.parts) and relative.suffix not in EXCLUDED_SUFFIXES


def _material_worktree_files(skill_path):
    files = set()
    for path in skill_path.rglob("*"):
        relative = path.relative_to(skill_path)
        if not _is_material_relative_path(relative.as_posix()):
            continue
        if path.is_file():
            files.add(relative.as_posix())
    return files


def inspect_git_versioning(skill_path, git_runner=None):
    """Report whether the complete material Skill tree is committed and clean.

    A missing repository or missing HEAD is reported explicitly.  No commit hash
    is invented, and unrelated changes elsewhere in a parent repository are not
    included in the Skill-scoped result.
    """
    raw_skill_path = Path(skill_path)
    if raw_skill_path.is_symlink() or not raw_skill_path.is_dir():
        return _empty_git_report("invalid", "Git inspection requires a real Skill directory")
    skill_path = raw_skill_path.resolve()
    for path in skill_path.rglob("*"):
        relative = path.relative_to(skill_path)
        if _is_material_relative_path(relative.as_posix()) and path.is_symlink():
            return _empty_git_report("invalid", f"Git inspection refuses symlinked Skill content: {relative}")

    runner = git_runner or _default_git_runner

    def run(*args):
        return runner(["git", *map(str, args)])

    try:
        repository = run("-C", skill_path, "rev-parse", "--show-toplevel")
    except FileNotFoundError as exc:
        return _empty_git_report("git_unavailable", f"Git executable is unavailable: {exc}")
    except OSError as exc:
        return _empty_git_report("invalid", f"Git inspection could not start: {exc}")
    if repository.returncode:
        detail = (repository.stderr or repository.stdout or "").strip()
        if "not a git repository" in detail.lower():
            return _empty_git_report(
                "not_versioned",
                "Source Git provenance unavailable: Skill is not contained in a Git worktree",
            )
        return _git_error(repository, "discovering the repository")

    repository_root = Path(repository.stdout.strip()).resolve()
    try:
        skill_repo_path = skill_path.relative_to(repository_root)
    except ValueError:
        return _empty_git_report("invalid", "Git reported a repository that does not contain the Skill")
    scope = "skill" if skill_path == repository_root else "parent"
    working_files = _material_worktree_files(skill_path)

    try:
        head_result = run("-C", repository_root, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    except FileNotFoundError as exc:
        return _empty_git_report("git_unavailable", f"Git executable is unavailable: {exc}")
    except OSError as exc:
        return _empty_git_report("invalid", f"Git inspection could not verify HEAD: {exc}")
    if head_result.returncode not in (0, 1):
        return _git_error(head_result, "verifying HEAD")
    head = head_result.stdout.strip() if head_result.returncode == 0 else None

    report = {
        "status": "versioned_dirty",
        "source_provenance": "unavailable",
        "repository_root": str(repository_root),
        "scope": scope,
        "head": head,
        "tracked_files": [],
        "untracked_files": [],
        "ignored_files": [],
        "dirty_files": [],
        "staged_files": [],
        "missing_files": [],
        "message": "",
    }

    head_files = set()
    if head is not None:
        try:
            tree_result = run("-C", repository_root, "ls-tree", "-r", "-z", "--name-only", head)
        except FileNotFoundError as exc:
            return _empty_git_report("git_unavailable", f"Git executable is unavailable: {exc}")
        except OSError as exc:
            return _empty_git_report("invalid", f"Git inspection could not read HEAD: {exc}")
        if tree_result.returncode:
            return _git_error(tree_result, "reading the committed tree")
        prefix = "" if skill_repo_path == Path(".") else skill_repo_path.as_posix().rstrip("/") + "/"
        for repo_relative in tree_result.stdout.split("\0"):
            if not repo_relative:
                continue
            if prefix:
                if not repo_relative.startswith(prefix):
                    continue
                relative = repo_relative[len(prefix):]
            else:
                relative = repo_relative
            if relative and _is_material_relative_path(relative):
                head_files.add(PurePosixPath(relative).as_posix())
        report["tracked_files"] = sorted(head_files)

    def repo_relative(relative):
        return (skill_repo_path / Path(relative)).as_posix()

    def run_checked(action, *args):
        try:
            return run(*args)
        except FileNotFoundError as exc:
            raise RuntimeError(f"git_unavailable\0Git executable is unavailable: {exc}") from exc
        except OSError as exc:
            raise RuntimeError(f"invalid\0Git inspection could not run while {action}: {exc}") from exc

    try:
        for relative in sorted(working_files - head_files):
            target = repo_relative(relative)
            indexed = run_checked(
                "checking the index", "-C", repository_root, "ls-files", "--error-unmatch", "--", target
            )
            if indexed.returncode == 0:
                report["staged_files"].append(relative)
            elif indexed.returncode == 1:
                ignored = run_checked(
                    "checking ignore rules", "-C", repository_root, "check-ignore", "--quiet", "--no-index", "--", target
                )
                if ignored.returncode == 0:
                    report["ignored_files"].append(relative)
                elif ignored.returncode == 1:
                    report["untracked_files"].append(relative)
                else:
                    return _git_error(ignored, f"checking ignore rules for {relative}")
            else:
                return _git_error(indexed, f"checking index coverage for {relative}")
            report["dirty_files"].append(relative)

        for relative in sorted(head_files - working_files):
            report["missing_files"].append(relative)
            report["dirty_files"].append(relative)

        for relative in sorted(head_files & working_files):
            worktree_changed = run_checked(
                "checking working-tree content", "-C", repository_root, "diff", "--quiet", "--", repo_relative(relative)
            )
            index_changed = run_checked(
                "checking staged content", "-C", repository_root, "diff", "--cached", "--quiet", head, "--", repo_relative(relative)
            )
            if worktree_changed.returncode not in (0, 1):
                return _git_error(worktree_changed, f"checking working-tree content for {relative}")
            if index_changed.returncode not in (0, 1):
                return _git_error(index_changed, f"checking staged content for {relative}")
            if index_changed.returncode == 1:
                report["staged_files"].append(relative)
            if worktree_changed.returncode == 1 or index_changed.returncode == 1:
                report["dirty_files"].append(relative)
    except RuntimeError as exc:
        status, message = str(exc).split("\0", 1)
        return _empty_git_report(status, message)

    report["dirty_files"] = sorted(set(report["dirty_files"]))
    if head is None:
        report["message"] = "Source Git provenance unavailable: worktree has no committed HEAD"
    elif report["dirty_files"]:
        categories = []
        for field, label in (
            ("staged_files", "staged but uncommitted"),
            ("untracked_files", "untracked"),
            ("ignored_files", "ignored"),
            ("missing_files", "missing"),
        ):
            if report[field]:
                categories.append(f"{len(report[field])} {label}")
        changed_count = len(report["dirty_files"]) - sum(
            len(report[field]) for field in ("staged_files", "untracked_files", "ignored_files", "missing_files")
        )
        if changed_count:
            categories.append(f"{changed_count} modified")
        report["message"] = "Git versioning is dirty: " + ", ".join(categories)
    elif head_files != working_files:
        report["status"] = "invalid"
        report["message"] = "Git inspection could not prove complete Skill-tree coverage"
    else:
        report["status"] = "versioned_clean"
        report["source_provenance"] = "available"
        report["message"] = f"Git versioning is clean at {head[:12]} ({scope} repository)"
    return report


def _parse_simple_frontmatter(text):
    """Parse the safe YAML subset used by Skill frontmatter without PyYAML.

    The fallback intentionally omits anchors, tags, and multiline scalars, but
    supports nested mappings and flow/block lists used by real Skills (for
    example ``metadata.requires.bins`` and ``allowed-tools``).
    """

    def strip_comment(value):
        quote = None
        depth = 0
        index = 0
        while index < len(value):
            char = value[index]
            if quote:
                if quote == "'" and char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                if char == quote:
                    quote = None
                index += 1
                continue
            if char in "'\"":
                quote = char
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
                if depth < 0:
                    raise ValueError("fallback parser found an unmatched closing collection marker")
            elif char == "#" and depth == 0 and (index == 0 or value[index - 1].isspace()):
                return value[:index].rstrip()
            index += 1
        if quote or depth:
            raise ValueError("fallback parser found an unclosed quote or collection")
        return value.strip()

    def split_top_level(value, separator=",", maxsplit=None):
        parts = []
        start = 0
        quote = None
        depth = 0
        index = 0
        while index < len(value):
            char = value[index]
            if quote:
                if quote == "'" and char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "'\"":
                quote = char
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
                if depth < 0:
                    raise ValueError("fallback parser found an unmatched collection marker")
            elif char == separator and depth == 0 and (maxsplit is None or len(parts) < maxsplit):
                parts.append(value[start:index].strip())
                start = index + 1
            index += 1
        if quote or depth:
            raise ValueError("fallback parser found an unclosed quote or collection")
        parts.append(value[start:].strip())
        return parts

    def parse_value(raw):
        value = strip_comment(raw.strip())
        if not value:
            raise ValueError("fallback parser requires a scalar or nested value")
        if value[0] in "'\"":
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("fallback parser found an unclosed quoted scalar")
            if value[0] == "'":
                return value[1:-1].replace("''", "'")
            # JSON string parsing safely handles the common YAML double-quoted
            # escapes without evaluating arbitrary Python expressions.
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"fallback parser found an invalid quoted scalar: {exc.msg}") from exc
        if value.startswith("[") or value.startswith("{"):
            closing = "]" if value[0] == "[" else "}"
            if not value.endswith(closing):
                raise ValueError("fallback parser found an unclosed collection")
            inner = value[1:-1].strip()
            if not inner:
                return [] if closing == "]" else {}
            entries = [entry for entry in split_top_level(inner) if entry]
            if closing == "]":
                return [parse_value(entry) for entry in entries]
            result = {}
            for entry in entries:
                key_value = split_top_level(entry, ":", maxsplit=1)
                if len(key_value) != 2:
                    raise ValueError("fallback parser requires key/value pairs in inline mappings")
                key = key_value[0].strip().strip("'\"")
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key):
                    raise ValueError("fallback parser accepts simple mapping keys")
                result[key] = parse_value(key_value[1])
            return result
        if value.startswith(("- ", "? ", "|", ">", "&", "*", "!")):
            raise ValueError("fallback parser does not accept YAML tags or unsupported block values")
        if value in {"true", "True", "TRUE"}:
            return True
        if value in {"false", "False", "FALSE"}:
            return False
        if value in {"null", "Null", "NULL", "~"}:
            return None
        return value

    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise ValueError(f"fallback parser found tab indentation at line {line_number}")
        indentation = len(line) - len(line.lstrip(" "))
        records.append((indentation, line.strip(), line_number))

    def next_indent(index):
        return records[index][0] if index < len(records) else None

    def parse_block(index, indentation):
        if index >= len(records) or records[index][0] != indentation:
            raise ValueError("fallback parser found an invalid indentation level")
        is_list = records[index][1] == "-" or records[index][1].startswith("- ")
        result = [] if is_list else {}
        while index < len(records):
            current_indent, content, line_number = records[index]
            if current_indent < indentation:
                break
            if current_indent != indentation:
                raise ValueError(f"fallback parser found unsupported indentation at line {line_number}")
            item_is_list = content == "-" or content.startswith("- ")
            if item_is_list != is_list:
                raise ValueError(f"fallback parser found mixed mapping/list values at line {line_number}")
            if is_list:
                payload = content[1:].strip()
                index += 1
                if not payload:
                    child = next_indent(index)
                    if child is None or child <= indentation:
                        value = None
                    else:
                        value, index = parse_block(index, child)
                elif ":" in payload and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", payload.split(":", 1)[0].strip()):
                    key, raw = payload.split(":", 1)
                    item = {}
                    raw = strip_comment(raw.strip())
                    if raw:
                        item[key.strip()] = parse_value(raw)
                    else:
                        child = next_indent(index)
                        if child is None or child <= indentation:
                            item[key.strip()] = {}
                        else:
                            item[key.strip()], index = parse_block(index, child)
                    child = next_indent(index)
                    if child is not None and child > indentation:
                        extra, index = parse_block(index, child)
                        if not isinstance(extra, dict):
                            raise ValueError(f"fallback parser expected mapping continuation at line {line_number}")
                        item.update(extra)
                    value = item
                else:
                    value = parse_value(payload)
                result.append(value)
            else:
                if ":" not in content:
                    raise ValueError(f"fallback parser accepts mapping fields at line {line_number}")
                key, raw = content.split(":", 1)
                key = key.strip()
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key):
                    raise ValueError(f"fallback parser accepts simple mapping keys at line {line_number}")
                index += 1
                # A mapping may have an inline comment after the colon. Treat
                # ``interface: # note`` like an empty value so its child block
                # is parsed instead of being sent to scalar parsing.
                raw = strip_comment(raw.strip())
                if raw:
                    result[key] = parse_value(raw)
                else:
                    child = next_indent(index)
                    if child is None or child <= indentation:
                        result[key] = {}
                    else:
                        result[key], index = parse_block(index, child)
        return result, index

    if not records:
        return {}
    result, consumed = parse_block(0, records[0][0])
    if consumed != len(records):
        raise ValueError("fallback parser could not consume all frontmatter")
    return result


def _load_yaml_or_scalars(path):
    text = Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return _parse_simple_frontmatter(text)


def _load_openai_metadata(path):
    """Read interface metadata while tolerating documented extra sections."""
    text = Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    # Use the same safe subset as frontmatter so comments, arbitrary child
    # indentation, and documented dependencies/policy sections behave the same
    # when PyYAML is unavailable.
    return _parse_simple_frontmatter(text)


def _safe_local_reference(skill_path, target):
    target = target.split("#", 1)[0].strip()
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    relative = PurePosixPath(target)
    if relative.is_absolute() or ".." in relative.parts:
        return f"Unsafe local reference in SKILL.md: {target}"
    candidate = skill_path.joinpath(*relative.parts)
    if candidate.is_symlink() or not candidate.exists():
        return f"Broken local reference in SKILL.md: {target}"
    return None


def _validate_markdown_links(skill_path):
    """Validate relative links from every Markdown resource, not only SKILL.md."""
    for markdown in sorted(skill_path.rglob("*.md")):
        relative_source = markdown.relative_to(skill_path)
        if any(part in EXCLUDED_DIRS for part in relative_source.parts):
            continue
        try:
            content = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return False, f"Cannot read Markdown resource {relative_source}: {exc}"
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content):
            target = target.split("#", 1)[0].strip()
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            relative = PurePosixPath(target)
            if relative.is_absolute() or ".." in relative.parts:
                return False, f"Unsafe local reference in {relative_source}: {target}"
            candidate = markdown.parent.joinpath(*relative.parts)
            if candidate.is_symlink() or not candidate.exists():
                return False, f"Broken local reference in {relative_source}: {target}"
    return True, "Markdown references are valid"


def _validate_skill_tree(skill_path):
    for path in skill_path.rglob("*"):
        relative = path.relative_to(skill_path)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            return False, f"Skill must not contain symlinks: {relative}"
    return True, "Skill tree is safe"


def _validate_contract(skill_path):
    contract_path = skill_path / "tests" / "skill_contract.json"
    if not contract_path.exists():
        return True, "No optional engineering contract"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Invalid tests/skill_contract.json: {exc}"
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        return False, "tests/skill_contract.json must be an object with schema_version 1"
    sections = contract.get("sections")
    if not isinstance(sections, dict) or set(sections) != REQUIRED_CONTRACT_SECTIONS:
        return False, "tests/skill_contract.json sections must be routing, behavior, and completion"
    seen_ids = set()
    for name, cases in sections.items():
        if not isinstance(cases, list) or not cases:
            return False, f"tests/skill_contract.json {name} must contain at least one case"
        for index, case in enumerate(cases):
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"].strip():
                return False, f"tests/skill_contract.json {name}[{index}] needs a non-empty id"
            if case["id"] in seen_ids:
                return False, f"tests/skill_contract.json has duplicate case id {case['id']!r}"
            seen_ids.add(case["id"])
            evidence = case.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(
                isinstance(item, str) and item.strip() for item in evidence
            ):
                return False, f"tests/skill_contract.json {name}[{index}] needs non-empty evidence"
            if name == "routing":
                if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
                    return False, f"tests/skill_contract.json routing[{index}] needs a prompt"
                if not isinstance(case.get("expected_action"), str) or not case["expected_action"].strip():
                    return False, f"tests/skill_contract.json routing[{index}] needs expected_action"
            elif name == "behavior":
                if not isinstance(case.get("scenario"), str) or not case["scenario"].strip():
                    return False, f"tests/skill_contract.json behavior[{index}] needs a scenario"
                if not isinstance(case.get("assertions"), list) or not case["assertions"]:
                    return False, f"tests/skill_contract.json behavior[{index}] needs assertions"
            else:
                if not isinstance(case.get("artifact"), str) or not case["artifact"].strip():
                    return False, f"tests/skill_contract.json completion[{index}] needs an artifact"
                if not isinstance(case.get("assertions"), list) or not case["assertions"]:
                    return False, f"tests/skill_contract.json completion[{index}] needs assertions"
    routing = sections["routing"]
    required_kinds = {"positive": 3, "nonstandard_positive": 2, "negative": 2, "adjacent": 2}
    counts = {kind: 0 for kind in required_kinds}
    for case in routing:
        if isinstance(case, dict) and case.get("kind") in counts:
            counts[case["kind"]] += 1
    missing = [f"{kind}>={minimum}" for kind, minimum in required_kinds.items() if counts[kind] < minimum]
    if missing:
        return False, "routing contract needs " + ", ".join(missing)
    behavior_kinds = {case.get("kind") for case in sections["behavior"] if isinstance(case, dict)}
    required_behaviors = {"success", "invalid_input", "tool_or_permission_failure", "idempotence"}
    if not required_behaviors.issubset(behavior_kinds):
        return False, "behavior contract needs success, invalid_input, tool_or_permission_failure, and idempotence cases"
    return True, "Engineering contract is valid"


def _validate_metadata(skill_path):
    metadata_path = skill_path / "agents" / "openai.yaml"
    if not metadata_path.exists():
        return True, "No optional UI metadata"
    if metadata_path.is_symlink():
        return False, "agents/openai.yaml must not be a symlink"
    try:
        metadata = _load_openai_metadata(metadata_path)
    except Exception as exc:
        return False, f"Invalid agents/openai.yaml: {exc}"
    if not isinstance(metadata, dict):
        return False, "agents/openai.yaml must contain a YAML dictionary"
    if "interface" not in metadata:
        return False, "agents/openai.yaml must contain an interface mapping"
    interface = metadata.get("interface")
    if not isinstance(interface, dict):
        return False, "agents/openai.yaml interface must be a YAML dictionary"
    for field in ("display_name", "short_description", "default_prompt"):
        if field in interface and not isinstance(interface[field], str):
            return False, f"agents/openai.yaml {field} must be a string"
    for field in ("icon_small", "icon_large"):
        target = interface.get(field)
        if target is None:
            continue
        if not isinstance(target, str):
            return False, f"agents/openai.yaml {field} must be a string"
        relative = PurePosixPath(target)
        if relative.is_absolute() or ".." in relative.parts:
            return False, f"agents/openai.yaml {field} must stay inside the Skill"
        asset = skill_path.joinpath(*relative.parts)
        if asset.is_symlink() or not asset.is_file():
            return False, f"agents/openai.yaml {field} points to a missing asset: {target}"
    return True, "UI metadata is valid"


def _validate_evals(skill_path):
    evals_dir = skill_path / "evals"
    if not evals_dir.exists():
        return True, "No optional evaluation corpus"
    if not evals_dir.is_dir() or evals_dir.is_symlink():
        return False, "evals must be a real directory"
    manifest_path = evals_dir / "manifest.json"
    if not manifest_path.exists():
        return True, "Evaluation scaffold is inactive; no quality conclusion is available"
    if manifest_path.is_symlink():
        return False, "evals/manifest.json must not be a symlink"
    try:
        spec = importlib.util.spec_from_file_location("skill_gate_validation", Path(__file__).with_name("skill_gate.py"))
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        manifest = gate.load_manifest(manifest_path)
    except (ImportError, OSError, ValueError) as exc:
        return False, f"Invalid eval manifest: {exc}"
    for split in ("train", "selection", "holdout"):
        split_path = evals_dir / f"{split}.jsonl"
        if not split_path.is_file():
            return False, f"Evaluation manifest requires {split_path.relative_to(skill_path)}"
        if split_path.is_symlink():
            return False, f"{split_path.relative_to(skill_path)} must not be a symlink"
        try:
            ids = []
            for line_number, line in enumerate(split_path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                    return False, f"{split_path.relative_to(skill_path)}:{line_number} needs an object with string id"
                ids.append(record["id"])
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Cannot read {split_path.relative_to(skill_path)}: {exc}"
        if ids != manifest["splits"][split]:
            return False, f"{split_path.relative_to(skill_path)} IDs do not match evals/manifest.json"
    return True, "Evaluation corpus is valid"


def _read_frontmatter(content):
    content = content.lstrip("\ufeff").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid frontmatter format")
    try:
        frontmatter = yaml.safe_load(match.group(1)) if yaml is not None else _parse_simple_frontmatter(match.group(1))
    except (ValueError, yaml.YAMLError if yaml is not None else ValueError) as exc:
        raise ValueError(f"Invalid YAML in frontmatter: {exc}") from exc
    return content, match, frontmatter


def validate_skill(skill_path, require_contract=False):
    """Validate static structure; optionally require the engineering contract."""
    raw_skill_path = Path(skill_path)
    if raw_skill_path.is_symlink() or not raw_skill_path.is_dir():
        return False, "Skill path must be a real directory"
    skill_path = raw_skill_path.resolve()
    valid, message = _validate_skill_tree(skill_path)
    if not valid:
        return valid, message
    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        return False, "SKILL.md not found"
    try:
        raw_content = skill_md.read_text(encoding="utf-8")
        content, match, frontmatter = _read_frontmatter(raw_content)
    except (OSError, UnicodeError, ValueError) as exc:
        return False, str(exc) if isinstance(exc, ValueError) else f"Cannot read SKILL.md: {exc}"
    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary"
    allowed_properties = {"name", "description", "license", "allowed-tools", "metadata"}
    unexpected_keys = set(frontmatter) - allowed_properties
    if unexpected_keys:
        return False, "Unexpected key(s) in SKILL.md frontmatter: " + ", ".join(sorted(unexpected_keys))
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not name.strip():
        return False, "Missing or invalid 'name' in frontmatter"
    name = name.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return False, f"Name '{name}' should be hyphen-case"
    if skill_path.name != name:
        return False, f"Skill directory name '{skill_path.name}' must match frontmatter name '{name}'"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, f"Name is too long ({len(name)} characters). Maximum is {MAX_SKILL_NAME_LENGTH}"
    if not isinstance(description, str) or not description.strip():
        return False, "Missing or invalid 'description' in frontmatter"
    description = description.strip()
    if "<" in description or ">" in description or len(description) > 1024:
        return False, "Description contains unsupported characters or exceeds 1024 characters"
    body = content[match.end():]
    if not body.strip():
        return False, "SKILL.md body must not be empty"
    body_for_count = body[1:] if body.startswith("\n") else body
    if len(body_for_count.splitlines()) > MAX_SKILL_LINES:
        return False, f"SKILL.md body exceeds {MAX_SKILL_LINES} lines; split conditional detail into references/"
    if FORBIDDEN_PLACEHOLDER_PATTERN.search(body):
        return False, "SKILL.md still contains a placeholder such as TODO, TBD, FIXME, or PLACEHOLDER"
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
        issue = _safe_local_reference(skill_path, target)
        if issue:
            return False, issue
    valid, message = _validate_markdown_links(skill_path)
    if not valid:
        return valid, message
    valid, message = _validate_metadata(skill_path)
    if not valid:
        return valid, message
    valid, message = _validate_contract(skill_path)
    if not valid:
        return valid, message
    if require_contract and not (skill_path / "tests" / "skill_contract.json").is_file():
        return False, "--require-contract needs tests/skill_contract.json"
    return _validate_evals(skill_path)


def validate_engineering_contract(skill_path):
    """Apply publish-grade validation, including source Git provenance."""
    raw_skill_path = Path(skill_path)
    if raw_skill_path.is_symlink():
        return False, "Skill path must be a real directory"
    valid, message = validate_skill(raw_skill_path, require_contract=True)
    if not valid:
        return valid, message
    skill_path = raw_skill_path.resolve()
    metadata_path = skill_path / "agents" / "openai.yaml"
    if not metadata_path.is_file():
        return False, "Engineering publish gate requires agents/openai.yaml"
    try:
        metadata = _load_openai_metadata(metadata_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return False, f"Invalid agents/openai.yaml: {exc}"
    interface = metadata.get("interface", {}) if isinstance(metadata, dict) else {}
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            return False, f"Engineering publish gate requires agents/openai.yaml interface.{field}"
    if not 25 <= len(interface["short_description"]) <= 64:
        return False, "agents/openai.yaml interface.short_description must be 25-64 characters"
    try:
        content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        _, _, frontmatter = _read_frontmatter(content)
    except (OSError, UnicodeError, ValueError) as exc:
        return False, str(exc)
    skill_name = frontmatter.get("name") if isinstance(frontmatter, dict) else None
    if not isinstance(skill_name, str) or not re.search(
        rf"\${re.escape(skill_name)}(?![a-z0-9-])", interface["default_prompt"], re.IGNORECASE
    ):
        return False, "agents/openai.yaml default_prompt must explicitly mention the Skill"
    git_report = inspect_git_versioning(skill_path)
    if git_report["status"] != "versioned_clean":
        return False, f"Engineering publish gate requires source Git provenance: {git_report['message']}"
    return True, "Engineering contract is valid"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a Codex Skill at the supplied <skill-dir> path")
    parser.add_argument("skill_directory", help="Path to the Skill directory being validated")
    parser.add_argument(
        "--require-contract", action="store_true", help="Require tests/skill_contract.json; does not imply --engineering"
    )
    parser.add_argument(
        "--engineering", action="store_true", help="Require publish-grade metadata, contract, tests, and clean Git provenance"
    )
    parser.add_argument("--git", action="store_true", help="Inspect source Git provenance for the supplied Skill path")
    parser.add_argument("--json", action="store_true", help="Emit Git inspection JSON; valid only with --git")
    args = parser.parse_args(argv)
    if args.git:
        if args.engineering or args.require_contract:
            parser.error("--git cannot be combined with --engineering or --require-contract")
        report = inspect_git_versioning(args.skill_directory)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["message"])
        return 0 if report["status"] == "versioned_clean" else 1
    if args.json:
        parser.error("--json requires --git")
    valid, message = (
        validate_engineering_contract(args.skill_directory)
        if args.engineering
        else validate_skill(args.skill_directory, args.require_contract)
    )
    print(message)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
