#!/usr/bin/env python3
"""Gate evaluated Skill candidates and stage immutable full-tree snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath


IGNORED_DIRS = {"__pycache__", ".git", ".skill-evals"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _reject_symlink_components(path, label):
    """Reject symlink path components without rejecting macOS /var and /tmp aliases."""
    raw = Path(path)
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current /= part
        if not current.is_symlink():
            continue
        resolved = current.resolve()
        # macOS commonly exposes /tmp and /var as symlinks into /private.
        if current in {Path("/tmp"), Path("/var")} and resolved == Path("/private") / current.name:
            continue
        raise ValueError(f"{label} must not contain a symlink component: {current}")


def ids_sha256(case_ids):
    """Hash an ordered ID list using the splitter's stable encoding."""
    payload = json.dumps(list(case_ids), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_case(case):
    """Return a stable representation for comparing split payloads to source."""
    return json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_hex(value, label):
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a SHA-256 hex digest") from exc
    return value


def load_manifest(path):
    raw_path = Path(path)
    _reject_symlink_components(raw_path, "manifest")
    if raw_path.is_symlink():
        raise ValueError(f"manifest must not be a symlink: {raw_path}")
    path = raw_path.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: manifest must be an object")
    if data.get("schema_version") != 1:
        raise ValueError(f"{path}: manifest schema_version must be 1")
    splits = data.get("splits")
    if not isinstance(splits, dict):
        raise ValueError(f"{path}: manifest needs a splits object")
    expected = {"train", "selection", "holdout"}
    if set(splits) != expected:
        raise ValueError(f"{path}: split keys must be {sorted(expected)}")
    split_files = data.get("split_files")
    if not isinstance(split_files, dict) or set(split_files) != expected:
        raise ValueError(f"{path}: split_files keys must be {sorted(expected)}")
    seen = set()
    split_records = {}
    for split, raw_ids in splits.items():
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError(f"{path}: split {split!r} must contain task IDs")
        ids = []
        for case_id in raw_ids:
            if not isinstance(case_id, str) or not case_id.strip():
                raise ValueError(f"{path}: split {split!r} contains an invalid ID")
            if case_id in ids:
                raise ValueError(f"{path}: duplicate ID {case_id!r} in {split}")
            if case_id in seen:
                raise ValueError(f"{path}: task ID {case_id!r} leaks across splits")
            ids.append(case_id)
            seen.add(case_id)
        descriptor = split_files.get(split)
        required_descriptor = {"path", "sha256", "id_sha256", "count"}
        if not isinstance(descriptor, dict) or set(descriptor) != required_descriptor:
            raise ValueError(f"{path}: split_files.{split} must contain path, sha256, id_sha256, and count")
        split_name = descriptor.get("path")
        if not isinstance(split_name, str) or Path(split_name).name != split_name or split_name != f"{split}.jsonl":
            raise ValueError(f"{path}: split_files.{split}.path must be {split}.jsonl")
        _sha256_hex(descriptor.get("sha256"), f"{path}: split_files.{split}.sha256")
        _sha256_hex(descriptor.get("id_sha256"), f"{path}: split_files.{split}.id_sha256")
        if isinstance(descriptor.get("count"), bool) or not isinstance(descriptor.get("count"), int):
            raise ValueError(f"{path}: split_files.{split}.count must be an integer")
        if descriptor["count"] != len(ids):
            raise ValueError(f"{path}: split_files.{split}.count does not match split IDs")
        if descriptor["id_sha256"] != ids_sha256(ids):
            raise ValueError(f"{path}: split_files.{split}.id_sha256 does not match split IDs")
        split_path = path.parent / split_name
        if split_path.is_symlink():
            raise ValueError(f"{path}: immutable split must not be a symlink: {split_name}")
        try:
            split_bytes = split_path.read_bytes()
            split_lines = split_bytes.decode("utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"{path}: cannot read immutable split {split_path}: {exc}") from exc
        if hashlib.sha256(split_bytes).hexdigest() != descriptor["sha256"]:
            raise ValueError(f"{path}: split {split!r} byte fingerprint does not match manifest")
        actual_ids = []
        actual_records = []
        for line_number, line in enumerate(split_lines, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{split_path}:{line_number}: invalid JSON: {exc.msg}") from exc
            case_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(case_id, str) or not case_id.strip():
                raise ValueError(f"{split_path}:{line_number}: each case needs a non-empty string id")
            actual_ids.append(case_id)
            actual_records.append(item)
        if actual_ids != ids:
            raise ValueError(f"{path}: split {split!r} contents do not match manifest IDs")
        split_records[split] = actual_records
    source = data.get("source")
    source_hash = data.get("source_sha256")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"{path}: manifest source must be a non-empty path")
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = path.parent / source_path
    if source_path.is_symlink():
        raise ValueError(f"{path}: source corpus must not be a symlink")
    source_path = source_path.resolve()
    _sha256_hex(source_hash, f"{path}: source_sha256")
    try:
        actual_source_hash = file_sha256(source_path)
    except OSError as exc:
        raise ValueError(f"{path}: cannot read source corpus {source_path}: {exc}") from exc
    if actual_source_hash != source_hash:
        raise ValueError(f"{path}: source corpus byte fingerprint does not match manifest")
    try:
        source_ids = []
        source_records = {}
        for line_number, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            item = json.loads(line)
            case_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(case_id, str) or not case_id.strip():
                raise ValueError(f"{source_path}:{line_number}: source case needs a non-empty string id")
            if case_id in source_ids:
                raise ValueError(f"{source_path}:{line_number}: duplicate source case id {case_id!r}")
            source_ids.append(case_id)
            source_records[case_id] = item
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot parse source corpus IDs: {exc}") from exc
    declared_ids = [case_id for split in ("train", "selection", "holdout") for case_id in splits[split]]
    if set(declared_ids) != set(source_ids) or len(declared_ids) != len(source_ids):
        missing = sorted(set(source_ids) - set(declared_ids))
        extra = sorted(set(declared_ids) - set(source_ids))
        raise ValueError(f"{path}: split IDs do not cover source corpus exactly; missing={missing}, extra={extra}")
    # IDs alone are not sufficient provenance: a caller could rewrite a split
    # prompt/fixture, update its byte and ID hashes, and still pass the gate.
    # Compare every split record with the immutable source record keyed by ID.
    for split, records in split_records.items():
        for record in records:
            case_id = record["id"]
            source_record = source_records.get(case_id)
            if source_record is None or _canonical_case(record) != _canonical_case(source_record):
                raise ValueError(
                    f"{path}: split {split!r} case payload does not match source corpus for ID {case_id!r}"
                )

    alias_path = path.parent / "test.jsonl"
    alias_hash = data.get("holdout_alias_sha256")
    if alias_hash is not None:
        _sha256_hex(alias_hash, f"{path}: holdout_alias_sha256")
        if not alias_path.is_file():
            raise ValueError(f"{path}: holdout_alias_sha256 requires test.jsonl")
    if alias_path.exists():
        if alias_path.is_symlink():
            raise ValueError(f"{path}: test.jsonl must not be a symlink")
        actual_alias_hash = file_sha256(alias_path)
        if actual_alias_hash != split_files["holdout"]["sha256"]:
            raise ValueError(f"{path}: test.jsonl must be byte-identical to holdout.jsonl")
        if alias_hash is not None and actual_alias_hash != alias_hash:
            raise ValueError(f"{path}: holdout_alias_sha256 does not match test.jsonl")
    counts = data.get("counts")
    expected_counts = {split: len(ids) for split, ids in splits.items()}
    if counts is not None and counts != expected_counts:
        raise ValueError(f"{path}: counts do not match split IDs")
    evaluator = data.get("evaluator")
    if not isinstance(evaluator, dict):
        raise ValueError(f"{path}: manifest needs an evaluator object")
    if not isinstance(evaluator.get("name"), str) or not evaluator["name"].strip():
        raise ValueError(f"{path}: evaluator.name must be non-empty")
    if not isinstance(evaluator.get("version"), str) or not evaluator["version"].strip():
        raise ValueError(f"{path}: evaluator.version must be non-empty")
    evaluator_files = data.get("evaluator_files")
    if evaluator_files is not None:
        if not isinstance(evaluator_files, dict):
            raise ValueError(f"{path}: evaluator_files must be an object")
        for filename, expected in evaluator_files.items():
            if not isinstance(filename, str) or not filename:
                raise ValueError(f"{path}: evaluator_files keys must be relative filenames")
            relative = PurePosixPath(filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"{path}: evaluator_files key must stay inside the manifest directory")
            target = path.parent / relative
            _reject_symlink_components(target, f"{path}: evaluator_files entry")
            if target.is_symlink():
                raise ValueError(f"{path}: evaluator_files entry must not be a symlink: {filename}")
            if not target.is_file():
                raise ValueError(f"{path}: evaluator_files entry is missing: {filename}")
            if isinstance(expected, str):
                _sha256_hex(expected, f"{path}: evaluator_files[{filename!r}]")
                if file_sha256(target) != expected:
                    raise ValueError(f"{path}: evaluator_files[{filename!r}] byte fingerprint does not match")
            elif isinstance(expected, int) and not isinstance(expected, bool):
                if expected < 1:
                    raise ValueError(f"{path}: evaluator_files[{filename!r}] count must be positive")
                line_count = sum(1 for line in target.read_text(encoding="utf-8").splitlines() if line.strip())
                if line_count != expected:
                    raise ValueError(f"{path}: evaluator_files[{filename!r}] count does not match")
            else:
                raise ValueError(f"{path}: evaluator_files[{filename!r}] must be a SHA-256 digest or line count")
    return data


def file_sha256(path):
    """Return the hash of an immutable evaluator manifest or result input."""
    path = Path(path)
    _reject_symlink_components(path, "immutable input")
    if path.is_symlink():
        raise ValueError(f"immutable input must not be a symlink: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_mean(values, label):
    """Calculate a finite aggregate, rejecting overflow instead of emitting Infinity."""
    values = list(values)
    if not values:
        raise ValueError(f"{label} score set must not be empty")
    try:
        total = math.fsum(values)
        mean = total / len(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} score aggregate is non-finite") from exc
    if not math.isfinite(mean):
        raise ValueError(f"{label} score aggregate is non-finite")
    return mean


def load_results(path, expected_split="selection", expected_ids=None, manifest_sha256=None):
    path = Path(path)
    _reject_symlink_components(path, "result artifact")
    if path.is_symlink():
        raise ValueError(f"result artifact must not be a symlink: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: result artifact must be an object")
    if data.get("schema_version") != 1:
        raise ValueError(f"{path}: result schema_version must be 1")
    if data.get("split") != expected_split:
        raise ValueError(f"{path}: expected split={expected_split!r}")
    if manifest_sha256 is not None and data.get("manifest_sha256") != manifest_sha256:
        raise ValueError(f"{path}: manifest fingerprint does not match the gate manifest")
    raw = data.get("results")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: results must be a non-empty list")
    results = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: results[{index}] must be an object")
        case_id = item.get("id")
        score = item.get("score")
        evidence = item.get("evidence")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{path}: results[{index}] has invalid id")
        if case_id in results:
            raise ValueError(f"{path}: duplicate result id {case_id!r}")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError(f"{path}: result {case_id!r} has non-finite numeric score")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"{path}: result {case_id!r} needs non-empty evidence")
        results[case_id] = float(score)
    if expected_ids is not None and set(results) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(results))
        extra = sorted(set(results) - set(expected_ids))
        raise ValueError(f"{path}: IDs do not match manifest; missing={missing}, extra={extra}")
    return data, results


def skill_tree_fingerprint(skill_dir):
    """Hash relative paths, modes, and bytes for a portable Skill snapshot."""
    raw_skill_dir = Path(skill_dir)
    _reject_symlink_components(raw_skill_dir, "Skill directory")
    if raw_skill_dir.is_symlink():
        raise ValueError(f"Skill snapshots cannot use a symlinked directory: {raw_skill_dir}")
    skill_dir = raw_skill_dir.resolve()
    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
        raise ValueError(f"invalid Skill directory: {skill_dir}")
    digest = hashlib.sha256()
    files = []
    for path in sorted(skill_dir.rglob("*")):
        relative = path.relative_to(skill_dir)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Skill snapshots cannot contain symlinks: {relative}")
        if not path.is_file() or path.suffix in IGNORED_SUFFIXES:
            continue
        files.append(relative.as_posix())
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(f"{path.stat().st_mode & 0o777:o}".encode("ascii") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {"sha256": digest.hexdigest(), "files": files}


def evaluate_gate(current_results, candidate_results, no_regression=True, min_delta=0.0):
    current_ids, candidate_ids = set(current_results), set(candidate_results)
    if current_ids != candidate_ids:
        missing = sorted(current_ids - candidate_ids)
        extra = sorted(candidate_ids - current_ids)
        raise ValueError(f"incomparable result IDs; missing={missing}, extra={extra}")
    if not isinstance(min_delta, (int, float)) or not math.isfinite(min_delta) or min_delta < 0:
        raise ValueError("min_delta must be a finite non-negative number")
    current_score = _finite_mean(current_results.values(), "current selection")
    candidate_score = _finite_mean(candidate_results.values(), "candidate selection")
    deltas = {case_id: candidate_results[case_id] - current_results[case_id] for case_id in sorted(current_ids)}
    regressions = [case_id for case_id, delta in deltas.items() if delta < 0]
    delta = candidate_score - current_score
    if not math.isfinite(delta):
        raise ValueError("aggregate selection delta is non-finite")
    improved = delta > min_delta
    accepted = improved and (not no_regression or not regressions)
    if accepted:
        reason = "strict selection improvement without prohibited regression"
    elif no_regression and regressions:
        reason = "candidate regressed on one or more selection cases"
    else:
        reason = "candidate did not exceed the required selection improvement"
    return {
        "action": "accept" if accepted else "reject",
        "current_score": current_score,
        "candidate_score": candidate_score,
        "delta": delta,
        "min_delta": float(min_delta),
        "no_regression": no_regression,
        "task_deltas": deltas,
        "regressed_case_ids": regressions,
        "task_count": len(current_ids),
        "reason": reason,
    }


def _assert_result_provenance(data, expected_fingerprint, evaluator, label):
    declared = data.get("skill_fingerprint")
    if declared != expected_fingerprint["sha256"]:
        raise ValueError(
            f"{label}: result fingerprint does not match evaluated Skill "
            f"({declared!r} != {expected_fingerprint['sha256']!r})"
        )
    actual_evaluator = data.get("evaluator")
    expected_evaluator = {"name": evaluator["name"], "version": evaluator["version"]}
    if actual_evaluator != expected_evaluator:
        raise ValueError(f"{label}: evaluator provenance does not match manifest")


def _write_json_atomic(path, value):
    """Write a report through a same-directory temporary file and replace."""
    path = Path(path)
    _reject_symlink_components(path, "report path")
    if path.is_symlink():
        raise ValueError(f"report path must not be a symlink: {path}")
    if path.parent.is_symlink():
        raise ValueError(f"report parent must not be a symlink: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _copy_skill_tree(source, destination):
    raw_source = Path(source)
    _reject_symlink_components(raw_source, "Skill source")
    if raw_source.is_symlink():
        raise ValueError(f"Skill snapshots cannot copy a symlinked directory: {raw_source}")
    source = raw_source.resolve()
    destination = Path(destination)
    _reject_symlink_components(destination, "snapshot destination")
    if destination.parent.is_symlink():
        raise ValueError(f"snapshot parent must not be a symlink: {destination.parent}")
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source and destination Skill paths must be disjoint")
    if destination.is_symlink():
        raise ValueError(f"destination must not be a symlink: {destination}")
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git", ".skill-evals"),
    )


def _copy_git_metadata(source, destination):
    """Preserve a standalone target repository's .git entry during adoption."""
    source_git = Path(source) / ".git"
    if not source_git.exists():
        return
    if source_git.is_symlink():
        raise ValueError("target Skill .git entry must not be a symlink")
    destination_git = Path(destination) / ".git"
    if destination_git.exists() or destination_git.is_symlink():
        raise ValueError("replacement Skill already contains a .git entry")
    if source_git.is_dir():
        shutil.copytree(source_git, destination_git, symlinks=True)
    else:
        shutil.copy2(source_git, destination_git)


def stage_candidate(candidate_skill, state_dir, report, dry_run=False):
    raw_candidate_skill = Path(candidate_skill)
    if raw_candidate_skill.is_symlink() or not raw_candidate_skill.is_dir():
        raise ValueError(f"candidate Skill directory does not exist: {candidate_skill}")
    candidate_skill = raw_candidate_skill.resolve()
    source_fingerprint = skill_tree_fingerprint(candidate_skill)
    if report.get("candidate_fingerprint") != source_fingerprint["sha256"]:
        raise ValueError("candidate Skill changed after selection results were scored")
    _validate_candidate_structure(candidate_skill, require_engineering=True)
    if skill_tree_fingerprint(candidate_skill)["sha256"] != source_fingerprint["sha256"]:
        raise ValueError("candidate Skill changed during engineering validation")
    raw_state_dir = Path(state_dir)
    _reject_symlink_components(raw_state_dir, "state_dir")
    if raw_state_dir.is_symlink():
        raise ValueError("state_dir must not be a symlink")
    state_dir = raw_state_dir.resolve()
    if state_dir.exists() and not state_dir.is_dir():
        raise ValueError("state_dir must be a directory")
    for child_name in ("runs", "best"):
        child = state_dir / child_name
        if child.is_symlink():
            raise ValueError(f"state_dir/{child_name} must not be a symlink")
        if child.exists() and not child.is_dir():
            raise ValueError(f"state_dir/{child_name} must be a directory")
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = state_dir / "runs" / timestamp
    candidate_dir = run_dir / "candidate"
    report["run_dir"] = str(run_dir)
    report["staged_candidate"] = str(candidate_dir)
    report["best_skill"] = str(state_dir / "best" / "skill")
    if dry_run:
        return report
    candidate_dir.parent.mkdir(parents=True, exist_ok=False)
    _copy_skill_tree(candidate_skill, candidate_dir)
    staged_fingerprint = skill_tree_fingerprint(candidate_dir)
    if staged_fingerprint["sha256"] != report["candidate_fingerprint"]:
        raise ValueError("staged candidate fingerprint changed during copy")
    _write_json_atomic(run_dir / "gate_report.json", report)
    best_root = state_dir / "best"
    best_report_path = best_root / "gate_report.json"
    if best_root.is_symlink() or best_report_path.is_symlink():
        raise ValueError("retained best snapshot must not be a symlink")
    previous_score = None
    previous_context = None
    if best_report_path.exists():
        try:
            previous_report = json.loads(best_report_path.read_text(encoding="utf-8"))
            previous_score = previous_report.get("candidate_score")
            previous_context = (
                previous_report.get("manifest_sha256"),
                previous_report.get("evaluator"),
                previous_report.get("selection_ids"),
            )
        except (OSError, json.JSONDecodeError):
            previous_score = None
    current_context = (report.get("manifest_sha256"), report.get("evaluator"), report.get("selection_ids"))
    if previous_context not in (None, current_context):
        report["best_updated"] = False
        report["best_update_reason"] = "not compared across a different manifest, evaluator, or selection split"
        _write_json_atomic(run_dir / "gate_report.json", report)
        return report
    if not isinstance(previous_score, (int, float)) or report["candidate_score"] > previous_score:
        replacement = state_dir / f".best-{timestamp}"
        replacement.mkdir(parents=True, exist_ok=False)
        _copy_skill_tree(candidate_skill, replacement / "skill")
        if skill_tree_fingerprint(replacement / "skill")["sha256"] != report["candidate_fingerprint"]:
            shutil.rmtree(replacement, ignore_errors=True)
            raise ValueError("best candidate fingerprint changed during copy")
        _write_json_atomic(replacement / "gate_report.json", report)
        previous = state_dir / f".previous-best-{timestamp}"
        if best_root.exists():
            os.replace(best_root, previous)
        try:
            os.replace(replacement, best_root)
        except OSError:
            if previous.exists():
                os.replace(previous, best_root)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        report["best_updated"] = True
        report["best_update_reason"] = "first candidate or strict improvement in the same evaluation context"
    else:
        report["best_updated"] = False
        report["best_update_reason"] = "candidate did not beat the retained best in the same evaluation context"
    _write_json_atomic(run_dir / "gate_report.json", report)
    return report


def _load_validator():
    validator_path = Path(__file__).with_name("quick_validate.py")
    spec = importlib.util.spec_from_file_location("skill_gate_validator", validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    return validator


def _git_status_from_path(validator, skill_path):
    """Return the compact source provenance embedded in a gate report."""
    _reject_symlink_components(skill_path, "Skill provenance path")
    report = validator.inspect_git_versioning(skill_path)
    return {
        "status": report.get("status"),
        "source_provenance": report.get("source_provenance", "unavailable"),
        "head": report.get("head"),
        "scope": report.get("scope"),
        "repository_root": report.get("repository_root"),
        "tracked_files": list(report.get("tracked_files", [])),
        "staged_files": list(report.get("staged_files", [])),
        "untracked_files": list(report.get("untracked_files", [])),
        "ignored_files": list(report.get("ignored_files", [])),
        "missing_files": list(report.get("missing_files", [])),
        "dirty_files": list(report.get("dirty_files", [])),
        "message": report.get("message", ""),
    }


def _verify_recorded_git_provenance(report):
    """Recompute source provenance before trusting a persisted gate report."""
    validator = _load_validator()
    for role, field in (("current", "current_git_provenance"), ("candidate", "candidate_git_provenance")):
        source = report.get(f"{role}_skill")
        recorded = report.get(field)
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"selection {role} Skill path provenance is missing")
        _reject_symlink_components(source, f"selection {role} Skill path")
        if not isinstance(recorded, dict):
            raise ValueError(f"selection {role} Git provenance is missing")
        actual = _git_status_from_path(validator, source)
        if actual != recorded:
            raise ValueError(f"selection {role} Git provenance changed after the gate report was written")


def _validate_candidate_structure(candidate_skill, require_engineering=False):
    """Reject malformed or unversioned bundles before they become snapshots."""
    validator = _load_validator()
    valid, message = validator.validate_skill(candidate_skill)
    if not valid:
        raise ValueError(f"candidate Skill failed structural validation: {message}")
    if require_engineering:
        valid, message = validator.validate_engineering_contract(candidate_skill)
        if not valid:
            raise ValueError(f"candidate Skill failed engineering validation: {message}")
    return validator


def _manifest_split_context(manifest):
    return {
        split: {
            "path": descriptor["path"],
            "sha256": descriptor["sha256"],
            "id_sha256": descriptor["id_sha256"],
            "count": descriptor["count"],
        }
        for split, descriptor in manifest["split_files"].items()
    }


def _result_artifact_record(path, data, expected_split, expected_ids, expected_fingerprint, manifest_hash, evaluator):
    """Reload and hash a result artifact for later tamper detection."""
    raw_artifact_path = Path(path)
    _reject_symlink_components(raw_artifact_path, "result artifact")
    if raw_artifact_path.is_symlink():
        raise ValueError(f"result artifact must not be a symlink: {raw_artifact_path}")
    artifact_path = raw_artifact_path.resolve()
    loaded, results = load_results(
        artifact_path,
        expected_split=expected_split,
        expected_ids=expected_ids,
        manifest_sha256=manifest_hash,
    )
    _assert_result_provenance(loaded, expected_fingerprint, evaluator, f"{artifact_path} results")
    return {
        "path": str(artifact_path),
        "sha256": file_sha256(artifact_path),
        "split": expected_split,
        "id_sha256": ids_sha256(expected_ids),
        "count": len(results),
        "skill_fingerprint": expected_fingerprint["sha256"],
        "evaluator": {"name": evaluator["name"], "version": evaluator["version"]},
    }


def _assert_result_artifact_record(record, manifest_hash, expected_split, expected_ids, expected_fingerprint, evaluator, label):
    if not isinstance(record, dict):
        raise ValueError(f"{label}: result artifact record must be an object")
    required = {"path", "sha256", "split", "id_sha256", "count", "skill_fingerprint", "evaluator"}
    if set(record) != required:
        raise ValueError(f"{label}: result artifact record schema is invalid")
    raw_path = Path(record["path"])
    _reject_symlink_components(raw_path, f"{label}: result artifact")
    if raw_path.is_symlink():
        raise ValueError(f"{label}: result artifact must not be a symlink")
    path = raw_path.resolve()
    _sha256_hex(record["sha256"], f"{label}: result artifact SHA-256")
    _sha256_hex(record["id_sha256"], f"{label}: result ID SHA-256")
    if not path.is_file() or file_sha256(path) != record["sha256"]:
        raise ValueError(f"{label}: result artifact bytes changed or artifact is missing")
    if record["split"] != expected_split or record["id_sha256"] != ids_sha256(expected_ids):
        raise ValueError(f"{label}: result split provenance does not match")
    if record["count"] != len(expected_ids) or record["skill_fingerprint"] != expected_fingerprint["sha256"]:
        raise ValueError(f"{label}: result fingerprint or count does not match")
    if record["evaluator"] != {"name": evaluator["name"], "version": evaluator["version"]}:
        raise ValueError(f"{label}: result evaluator does not match")
    data, _ = load_results(path, expected_split, expected_ids, manifest_hash)
    _assert_result_provenance(data, expected_fingerprint, evaluator, label)


def _validate_git_provenance(provenance, label):
    if not isinstance(provenance, dict) or provenance.get("status") != "versioned_clean":
        raise ValueError(f"{label}: source Git provenance is unavailable or dirty")
    if provenance.get("source_provenance") != "available":
        raise ValueError(f"{label}: source Git provenance is not marked available")
    head = provenance.get("head")
    if not isinstance(head, str) or len(head) != 40:
        raise ValueError(f"{label}: source Git provenance needs a committed HEAD")
    try:
        int(head, 16)
    except ValueError as exc:
        raise ValueError(f"{label}: source Git provenance HEAD is invalid") from exc
    if provenance.get("scope") not in {"skill", "parent"}:
        raise ValueError(f"{label}: source Git provenance scope is invalid")
    if provenance.get("dirty_files") or provenance.get("staged_files"):
        raise ValueError(f"{label}: source Git provenance contains dirty files")


def _validate_selection_report(report, manifest, manifest_hash, staged_fingerprint=None, manifest_path=None):
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("purpose") != "selection_gate":
        raise ValueError("selection gate report schema or purpose is invalid")
    if report.get("action") != "accept":
        raise ValueError("selection gate report is not an accepted run")
    if report.get("manifest_sha256") != manifest_hash or report.get("evaluator") != manifest["evaluator"]:
        raise ValueError("selection gate report manifest or evaluator does not match")
    if manifest_path is not None and report.get("manifest") != str(Path(manifest_path).resolve()):
        raise ValueError("selection gate report manifest path does not match")
    if report.get("selection_ids") != manifest["splits"]["selection"]:
        raise ValueError("selection gate report selection IDs do not match")
    if report.get("split_context") != _manifest_split_context(manifest):
        raise ValueError("selection gate report split context does not match")
    current_fingerprint = _sha256_hex(report.get("current_fingerprint"), "selection current Skill fingerprint")
    candidate_fingerprint = _sha256_hex(report.get("candidate_fingerprint"), "selection candidate Skill fingerprint")
    if staged_fingerprint is not None and candidate_fingerprint != staged_fingerprint:
        raise ValueError("selection gate report candidate fingerprint does not match staged Skill")
    if staged_fingerprint is not None:
        staged_path = report.get("staged_candidate")
        if not isinstance(staged_path, str) or not staged_path.strip():
            raise ValueError("selection gate report is missing staged_candidate")
    for field, label in (
        ("current_git_provenance", "selection current Skill"),
        ("candidate_git_provenance", "selection candidate Skill"),
    ):
        if field not in report:
            raise ValueError(f"selection gate report is missing {field}")
        _validate_git_provenance(report[field], label)
    if "git_provenance" in report and report["git_provenance"] != report["candidate_git_provenance"]:
        raise ValueError("selection gate report candidate Git provenance is inconsistent")
    _verify_recorded_git_provenance(report)
    artifacts = report.get("selection_result_artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"current", "candidate"}:
        raise ValueError("selection gate report needs current and candidate result artifacts")
    ids = manifest["splits"]["selection"]
    for role in ("current", "candidate"):
        top_level_path = report.get(f"{role}_results")
        artifact_path = artifacts[role].get("path") if isinstance(artifacts[role], dict) else None
        if not isinstance(top_level_path, str) or not isinstance(artifact_path, str):
            raise ValueError(f"selection {role} result path provenance is missing")
        if Path(top_level_path).resolve() != Path(artifact_path).resolve():
            raise ValueError(f"selection {role} result path provenance does not match")
    _assert_result_artifact_record(artifacts["current"], manifest_hash, "selection", ids, {"sha256": current_fingerprint}, manifest["evaluator"], "current selection result")
    _assert_result_artifact_record(artifacts["candidate"], manifest_hash, "selection", ids, {"sha256": candidate_fingerprint}, manifest["evaluator"], "candidate selection result")
    current_data, current_results = load_results(
        artifacts["current"]["path"], "selection", ids, manifest_hash
    )
    candidate_data, candidate_results = load_results(
        artifacts["candidate"]["path"], "selection", ids, manifest_hash
    )
    _assert_result_provenance(current_data, {"sha256": current_fingerprint}, manifest["evaluator"], "current selection result")
    _assert_result_provenance(candidate_data, {"sha256": candidate_fingerprint}, manifest["evaluator"], "candidate selection result")
    no_regression = report.get("no_regression")
    min_delta = report.get("min_delta")
    if not isinstance(no_regression, bool):
        raise ValueError("selection gate report no_regression must be boolean")
    if isinstance(min_delta, bool) or not isinstance(min_delta, (int, float)) or not math.isfinite(min_delta) or min_delta < 0:
        raise ValueError("selection gate report min_delta is invalid")
    expected_gate = evaluate_gate(current_results, candidate_results, no_regression, min_delta)
    for field in ("action", "task_count", "no_regression", "regressed_case_ids", "task_deltas"):
        if report.get(field) != expected_gate[field]:
            raise ValueError(f"selection gate report {field} does not match result artifacts")
    for field in ("current_score", "candidate_score", "delta", "min_delta"):
        actual = report.get(field)
        expected_value = expected_gate[field]
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isclose(float(actual), float(expected_value), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"selection gate report {field} does not match result artifacts")
    return current_fingerprint


def _validate_holdout_report(
    report,
    manifest,
    manifest_hash,
    candidate_fingerprint,
    manifest_path=None,
    gate_report_sha256=None,
):
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("purpose") != "release_evidence_only":
        raise ValueError("holdout report schema or purpose is invalid")
    if report.get("manifest_sha256") != manifest_hash or report.get("evaluator") != manifest["evaluator"]:
        raise ValueError("holdout evidence manifest or evaluator does not match")
    if manifest_path is not None and report.get("manifest") != str(Path(manifest_path).resolve()):
        raise ValueError("holdout evidence manifest path does not match")
    if report.get("split_context") != _manifest_split_context(manifest):
        raise ValueError("holdout evidence split context does not match")
    if report.get("candidate_fingerprint") != candidate_fingerprint:
        raise ValueError("holdout evidence does not match staged candidate")
    if gate_report_sha256 is not None and report.get("selection_report_sha256") != gate_report_sha256:
        raise ValueError("holdout evidence is not bound to the selection report")
    score = report.get("holdout_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("holdout evidence score must be numeric")
    if not math.isfinite(score) or report.get("task_count") != len(manifest["splits"]["holdout"]):
        raise ValueError("holdout evidence score or task count is invalid")
    artifact_record = report.get("result_artifact")
    _assert_result_artifact_record(
        artifact_record, manifest_hash, "holdout", manifest["splits"]["holdout"],
        {"sha256": candidate_fingerprint}, manifest["evaluator"], "holdout result"
    )
    _, artifact_results = load_results(
        artifact_record["path"], "holdout", manifest["splits"]["holdout"], manifest_hash
    )
    actual_score = _finite_mean(artifact_results.values(), "holdout")
    if not math.isclose(score, actual_score, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("holdout evidence score does not match the result artifact")


def _write_json_once(path, value):
    path = Path(path)
    _reject_symlink_components(path, "holdout report path")
    if path.is_symlink():
        raise ValueError(f"holdout report path must not be a symlink: {path}")
    if path.parent.is_symlink():
        raise ValueError(f"holdout report parent must not be a symlink: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("held-out evaluation is already recorded for this run") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def record_holdout(manifest_path, candidate_skill, result_path, state_dir, run_dir=None, dry_run=False):
    """Record one held-out release evaluation without influencing candidate choice."""
    manifest = load_manifest(manifest_path)
    manifest_hash = file_sha256(manifest_path)
    candidate_fingerprint = skill_tree_fingerprint(candidate_skill)
    result_data, results = load_results(
        result_path,
        expected_split="holdout",
        expected_ids=manifest["splits"]["holdout"],
        manifest_sha256=manifest_hash,
    )
    _assert_result_provenance(result_data, candidate_fingerprint, manifest["evaluator"], "holdout results")
    raw_state_dir = Path(state_dir)
    _reject_symlink_components(raw_state_dir, "state_dir")
    if raw_state_dir.is_symlink():
        raise ValueError("state_dir must not be a symlink")
    state_dir = raw_state_dir.resolve()
    runs_dir = state_dir / "runs"
    if runs_dir.is_symlink():
        raise ValueError("state_dir/runs must not be a symlink")
    if run_dir is None:
        matching_runs = []
        for report_path in (state_dir / "runs").glob("*/gate_report.json") if (state_dir / "runs").exists() else []:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if report.get("candidate_fingerprint") == candidate_fingerprint["sha256"] and report.get("action") == "accept":
                matching_runs.append(report_path.parent)
        if len(matching_runs) != 1:
            raise ValueError("holdout requires exactly one matching accepted staged run; pass --run-dir to disambiguate")
        run_dir = matching_runs[0]
    else:
        raw_run_dir = Path(run_dir)
        _reject_symlink_components(raw_run_dir, "run_dir")
        if raw_run_dir.is_symlink():
            raise ValueError("run_dir must not be a symlink")
        run_dir = raw_run_dir.resolve()
    if state_dir not in run_dir.parents:
        raise ValueError("holdout run must be inside state_dir")
    expected_candidate_dir = (run_dir / "candidate").resolve()
    if (run_dir / "candidate").is_symlink():
        raise ValueError("accepted staged candidate must not be a symlink")
    if Path(candidate_skill).resolve() != expected_candidate_dir:
        raise ValueError("holdout candidate must be the accepted run's staged candidate")
    gate_report_path = run_dir / "gate_report.json"
    if gate_report_path.is_symlink():
        raise ValueError("selection gate report must not be a symlink")
    if not gate_report_path.is_file():
        raise ValueError("holdout run is missing gate_report.json")
    try:
        gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read selection gate report: {exc}") from exc
    _validate_selection_report(
        gate_report, manifest, manifest_hash, candidate_fingerprint["sha256"], manifest_path
    )
    if Path(gate_report["staged_candidate"]).resolve() != expected_candidate_dir:
        raise ValueError("selection report staged_candidate does not match the accepted run")
    output_path = run_dir / "holdout_report.json"
    report = {
        "schema_version": 1,
        "purpose": "release_evidence_only",
        "manifest": str(Path(manifest_path).resolve()),
        "manifest_sha256": manifest_hash,
        "candidate_fingerprint": candidate_fingerprint["sha256"],
        "evaluator": manifest["evaluator"],
        "selection_report_sha256": file_sha256(gate_report_path),
        "holdout_score": _finite_mean(results.values(), "holdout"),
        "task_count": len(results),
        "split_context": _manifest_split_context(manifest),
        "result_artifact": _result_artifact_record(
            result_path,
            result_data,
            "holdout",
            manifest["splits"]["holdout"],
            candidate_fingerprint,
            manifest_hash,
            manifest["evaluator"],
        ),
    }
    if not dry_run:
        _write_json_once(output_path, report)
    return report


def adopt_staged_candidate(state_dir, run_dir, target_skill, backup_dir=None, dry_run=False):
    """Explicitly promote one release-evidenced snapshot, keeping a backup."""
    raw_state_dir = Path(state_dir)
    _reject_symlink_components(raw_state_dir, "state_dir")
    if raw_state_dir.is_symlink():
        raise ValueError("state_dir must not be a symlink")
    state_dir = raw_state_dir.resolve()
    raw_run_dir = Path(run_dir)
    _reject_symlink_components(raw_run_dir, "run_dir")
    if raw_run_dir.is_symlink():
        raise ValueError("run_dir must not be a symlink")
    run_dir = raw_run_dir.resolve()
    raw_target_skill = Path(target_skill)
    _reject_symlink_components(raw_target_skill, "target_skill")
    if raw_target_skill.is_symlink():
        raise ValueError("target_skill must be an existing real Skill directory")
    target_skill = raw_target_skill.resolve()
    if state_dir not in run_dir.parents:
        raise ValueError("run_dir must be inside state_dir")
    candidate_dir = run_dir / "candidate"
    gate_report_path = run_dir / "gate_report.json"
    holdout_report_path = run_dir / "holdout_report.json"
    if candidate_dir.is_symlink() or gate_report_path.is_symlink() or holdout_report_path.is_symlink():
        raise ValueError("adoption evidence and staged candidate must not be symlinks")
    if not candidate_dir.is_dir() or not gate_report_path.is_file() or not holdout_report_path.is_file():
        raise ValueError("adoption requires an accepted staged candidate and one recorded holdout report")
    try:
        gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
        holdout_report = json.loads(holdout_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read adoption evidence: {exc}") from exc
    staged_fingerprint = skill_tree_fingerprint(candidate_dir)["sha256"]
    manifest_value = gate_report.get("manifest")
    if not isinstance(manifest_value, str) or not manifest_value.strip():
        raise ValueError("accepted run is missing its evaluation manifest")
    manifest_path = Path(manifest_value).resolve()
    if not manifest_path.is_file():
        raise ValueError("accepted run is missing its evaluation manifest")
    manifest = load_manifest(manifest_path)
    manifest_hash = file_sha256(manifest_path)
    expected_current_fingerprint = _validate_selection_report(
        gate_report, manifest, manifest_hash, staged_fingerprint, manifest_path
    )
    if Path(gate_report["staged_candidate"]).resolve() != candidate_dir.resolve():
        raise ValueError("selection report staged_candidate does not match the accepted run")
    _validate_holdout_report(
        holdout_report,
        manifest,
        manifest_hash,
        staged_fingerprint,
        manifest_path,
        file_sha256(gate_report_path),
    )
    if target_skill.is_symlink() or not target_skill.is_dir() or not (target_skill / "SKILL.md").is_file():
        raise ValueError("target_skill must be an existing real Skill directory")
    recorded_target = gate_report.get("current_skill")
    if not isinstance(recorded_target, str) or target_skill != Path(recorded_target).resolve():
        raise ValueError("target_skill must be the active Skill evaluated by the accepted run")
    if skill_tree_fingerprint(target_skill)["sha256"] != expected_current_fingerprint:
        raise ValueError("target Skill changed after the accepted baseline evaluation")
    if backup_dir is None:
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_dir = state_dir / "backups" / timestamp
    raw_backup_dir = Path(backup_dir)
    _reject_symlink_components(raw_backup_dir, "backup_dir")
    if raw_backup_dir.is_symlink():
        raise ValueError("backup_dir must not be a symlink")
    backup_dir = raw_backup_dir.resolve()
    if backup_dir.exists() or backup_dir == target_skill or target_skill in backup_dir.parents:
        raise ValueError("backup_dir must be a new directory distinct from target_skill")
    replacement = target_skill.parent / f".{target_skill.name}.replacement-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}"
    if dry_run:
        return {"action": "would_adopt", "target_skill": str(target_skill), "backup_skill": str(backup_dir), "fingerprint": staged_fingerprint}
    _copy_skill_tree(candidate_dir, replacement)
    _copy_git_metadata(target_skill, replacement)
    if skill_tree_fingerprint(replacement)["sha256"] != staged_fingerprint:
        shutil.rmtree(replacement, ignore_errors=True)
        raise ValueError("replacement Skill fingerprint changed during adoption")
    # Re-check the active tree immediately before the directory swap so a
    # concurrent edit cannot replace a newer active Skill with stale evidence.
    if skill_tree_fingerprint(target_skill)["sha256"] != expected_current_fingerprint:
        shutil.rmtree(replacement, ignore_errors=True)
        raise ValueError("target Skill changed during adoption")
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(target_skill, backup_dir)
        os.replace(replacement, target_skill)
    except OSError:
        if backup_dir.exists() and not target_skill.exists():
            os.replace(backup_dir, target_skill)
        if replacement.exists():
            shutil.rmtree(replacement, ignore_errors=True)
        raise
    return {"action": "adopted", "target_skill": str(target_skill), "backup_skill": str(backup_dir), "fingerprint": staged_fingerprint}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Accept/reject a candidate Skill on a selection split")
    subparsers = parser.add_subparsers(dest="command")
    holdout_parser = subparsers.add_parser("holdout", help="Record one held-out release evaluation")
    holdout_parser.add_argument("--manifest", required=True)
    holdout_parser.add_argument("--candidate-skill", required=True)
    holdout_parser.add_argument("--results", required=True)
    holdout_parser.add_argument("--state-dir", required=True)
    holdout_parser.add_argument("--run-dir")
    holdout_parser.add_argument("--dry-run", action="store_true")
    holdout_parser.add_argument("--json", action="store_true")
    adopt_parser = subparsers.add_parser("adopt", help="Explicitly promote a release-evidenced staged candidate")
    adopt_parser.add_argument("--state-dir", required=True)
    adopt_parser.add_argument("--run-dir", required=True)
    adopt_parser.add_argument("--target-skill", required=True)
    adopt_parser.add_argument("--backup-dir")
    adopt_parser.add_argument("--dry-run", action="store_true")
    adopt_parser.add_argument("--json", action="store_true")
    parser.add_argument("--manifest", help="Evaluation manifest with immutable split IDs")
    parser.add_argument("--current-results", help="Selection results for the active Skill")
    parser.add_argument("--candidate-results", help="Selection results for the candidate Skill")
    parser.add_argument("--current-skill", help="Active Skill directory used for current results")
    parser.add_argument("--candidate-skill", help="Candidate Skill directory to stage if accepted")
    parser.add_argument("--state-dir", help="Directory for run history and best snapshots")
    parser.add_argument("--allow-regression", action="store_true", help="Allow per-case regressions if aggregate score improves")
    parser.add_argument("--min-delta", type=float, default=0.0, help="Required improvement above the current mean")
    parser.add_argument("--dry-run", action="store_true", help="Report decision without writing staging state")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    # Preserve the original no-subcommand gate CLI while offering holdout.
    args = parser.parse_args(raw_argv)
    try:
        if args.command == "holdout":
            report = record_holdout(
                args.manifest, args.candidate_skill, args.results, args.state_dir, args.run_dir, args.dry_run
            )
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"[RECORDED] holdout score: {report['holdout_score']:.4f}")
            return 0
        if args.command == "adopt":
            report = adopt_staged_candidate(
                args.state_dir, args.run_dir, args.target_skill, args.backup_dir, args.dry_run
            )
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"[{report['action'].upper()}] {report['target_skill']}")
            return 0
        missing = [name for name in ("manifest", "current_results", "candidate_results", "current_skill", "candidate_skill", "state_dir") if not getattr(args, name)]
        if missing:
            parser.error("selection gate requires: " + ", ".join("--" + name.replace("_", "-") for name in missing))
        manifest = load_manifest(args.manifest)
        selection_ids = manifest["splits"]["selection"]
        manifest_hash = file_sha256(args.manifest)
        current_data, current_results = load_results(
            args.current_results, expected_ids=selection_ids, manifest_sha256=manifest_hash
        )
        candidate_data, candidate_results = load_results(
            args.candidate_results, expected_ids=selection_ids, manifest_sha256=manifest_hash
        )
        current_fingerprint = skill_tree_fingerprint(args.current_skill)
        candidate_fingerprint = skill_tree_fingerprint(args.candidate_skill)
        _assert_result_provenance(current_data, current_fingerprint, manifest["evaluator"], "current results")
        _assert_result_provenance(candidate_data, candidate_fingerprint, manifest["evaluator"], "candidate results")
        validator = _load_validator()
        for label, skill_path in (("current", args.current_skill), ("candidate", args.candidate_skill)):
            valid, message = validator.validate_engineering_contract(skill_path)
            if not valid:
                raise ValueError(f"{label} Skill failed engineering validation: {message}")
        current_git = _git_status_from_path(validator, args.current_skill)
        candidate_git = _git_status_from_path(validator, args.candidate_skill)
        if current_git["status"] != "versioned_clean":
            raise ValueError(f"current Skill must be cleanly committed in Git: {current_git['message']}")
        if candidate_git["status"] != "versioned_clean":
            raise ValueError(f"candidate Skill must be cleanly committed in Git: {candidate_git['message']}")
        report = evaluate_gate(
            current_results,
            candidate_results,
            no_regression=not args.allow_regression,
            min_delta=args.min_delta,
        )
        report.update(
            {
                "schema_version": 1,
                "purpose": "selection_gate",
                "manifest": str(Path(args.manifest).resolve()),
                "manifest_sha256": manifest_hash,
                "current_results": str(Path(args.current_results).resolve()),
                "candidate_results": str(Path(args.candidate_results).resolve()),
                "current_skill": str(Path(args.current_skill).resolve()),
                "candidate_skill": str(Path(args.candidate_skill).resolve()),
                "current_fingerprint": current_fingerprint["sha256"],
                "candidate_fingerprint": candidate_fingerprint["sha256"],
                "evaluator": manifest["evaluator"],
                "selection_ids": selection_ids,
                "split_context": _manifest_split_context(manifest),
                "selection_result_artifacts": {
                    "current": _result_artifact_record(
                        args.current_results,
                        current_data,
                        "selection",
                        selection_ids,
                        current_fingerprint,
                        manifest_hash,
                        manifest["evaluator"],
                    ),
                    "candidate": _result_artifact_record(
                        args.candidate_results,
                        candidate_data,
                        "selection",
                        selection_ids,
                        candidate_fingerprint,
                        manifest_hash,
                        manifest["evaluator"],
                    ),
                },
                "current_git_provenance": current_git,
                "candidate_git_provenance": candidate_git,
                # Retain the historical single-field alias for consumers that
                # only display the candidate source provenance.
                "git_provenance": candidate_git,
            }
        )
        if report["action"] == "accept":
            report = stage_candidate(args.candidate_skill, args.state_dir, report, args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[{report['action'].upper()}] {report['reason']}")
        print(f"selection: {report['current_score']:.4f} -> {report['candidate_score']:.4f} ({report['delta']:+.4f})")
        if report["regressed_case_ids"]:
            print("regressed cases: " + ", ".join(report["regressed_case_ids"]))
        if report["action"] == "accept":
            print("staged candidate: " + report["staged_candidate"])
    return 0 if report["action"] == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
