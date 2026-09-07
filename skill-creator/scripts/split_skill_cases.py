#!/usr/bin/env python3
"""Create deterministic train/selection/holdout JSONL splits for a Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shlex
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from pathlib import PurePosixPath


def _as_path(value, label):
    """Convert a caller-supplied path while keeping malformed types fail-closed."""
    try:
        return Path(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a filesystem path") from exc


def _finite_ratio(value, label):
    """Normalize a public ratio argument and reject bool/non-finite values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{label} must be a finite number")
    return normalized


_REJECTED_EVALUATOR_NAMES = {"manual", "unknown", "untrusted"}


def _parse_evaluator_command(value, label="evaluator_command"):
    """Normalize a shell-free evaluator command declaration."""
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f"{label} must be a non-empty command")
        try:
            command = shlex.split(value)
        except ValueError as exc:
            raise ValueError(f"{label} is not valid shell-free command syntax") from exc
    elif isinstance(value, (list, tuple)):
        command = list(value)
    else:
        raise ValueError(f"{label} must be a command string or list of tokens")
    if not command or any(not isinstance(token, str) or not token.strip() for token in command):
        raise ValueError(f"{label} must contain non-empty string tokens")
    if any(any(character in token for character in ";&|<>\n\r") for token in command):
        raise ValueError(f"{label} must not contain shell control characters")
    return command


def _normalize_evaluator_files(evaluator_files):
    """Validate relative evaluator file keys and SHA-256 values."""
    if not isinstance(evaluator_files, Mapping) or not evaluator_files:
        raise ValueError("evaluator_files must be a non-empty mapping of relative paths to SHA-256 hashes")
    normalized = {}
    for filename, digest in evaluator_files.items():
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("evaluator_files keys must be relative filenames")
        relative = PurePosixPath(filename)
        if relative.is_absolute() or ".." in relative.parts or any(part == "" for part in relative.parts):
            raise ValueError("evaluator_files keys must stay inside the output directory")
        canonical_name = relative.as_posix()
        if canonical_name in normalized:
            raise ValueError(f"evaluator_files contains duplicate path {canonical_name!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"evaluator_files[{filename!r}] must be a SHA-256 digest")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(f"evaluator_files[{filename!r}] must be a SHA-256 digest") from exc
        normalized[canonical_name] = digest
    return normalized


def _validate_evaluator_declaration(
    evaluator_name,
    evaluator_version,
    evaluator_command,
    evaluator_files,
    evaluator_trust,
):
    """Return canonical evaluator metadata; untrusted scaffolds stay explicit."""
    if not isinstance(evaluator_name, str) or not evaluator_name.strip():
        raise ValueError("evaluator_name must be a non-empty string")
    if not isinstance(evaluator_version, str) or not evaluator_version.strip():
        raise ValueError("evaluator_version must be a non-empty string")
    normalized_name = evaluator_name.strip()
    if evaluator_trust is not None and (
        not isinstance(evaluator_trust, str) or evaluator_trust not in {"trusted", "untrusted"}
    ):
        raise ValueError("evaluator_trust must be 'trusted' or 'untrusted'")
    if (evaluator_command is None) != (evaluator_files is None):
        raise ValueError("evaluator_command and evaluator_files must be declared together")
    if evaluator_command is None:
        # A generated default/manual or name-only manifest is an explicit
        # inactive scaffold and must not be mistaken for quality evidence.
        return None, None, "untrusted"
    command = _parse_evaluator_command(evaluator_command)
    files = _normalize_evaluator_files(evaluator_files)
    if normalized_name.lower() in _REJECTED_EVALUATOR_NAMES:
        return command, files, "untrusted"
    if evaluator_trust == "untrusted":
        return command, files, "untrusted"
    # Supplying a command plus immutable file hashes is the opt-in signal for
    # an independently reproducible evaluator. The gate still verifies this
    # declaration and requires an explicit trusted state in the manifest.
    referenced = set()
    for token in command:
        token_name = PurePosixPath(token).as_posix().removeprefix("./")
        if token_name in files:
            referenced.add(token_name)
    if not referenced:
        raise ValueError("evaluator_command must reference at least one evaluator_files entry")
    return command, files, "trusted"


def _validate_evaluator_files_on_disk(output_dir, evaluator_files):
    """Verify evaluator file hashes before any split output is published."""
    normalized = _normalize_evaluator_files(evaluator_files)
    output_dir = _as_path(output_dir, "output_dir").resolve()
    for filename, expected in normalized.items():
        target = output_dir.joinpath(*PurePosixPath(filename).parts)
        _reject_symlink_components(target, "evaluator file")
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"evaluator file is missing or symlinked: {filename}")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"evaluator file fingerprint does not match: {filename}")
    return normalized


def _validate_cases(cases, *, require_minimum=True):
    """Validate the public case collection before sorting or serializing it."""
    if not isinstance(cases, (list, tuple)):
        raise ValueError("cases must be a list or tuple of JSON objects")
    validated = []
    seen = set()
    for index, item in enumerate(cases, 1):
        if not isinstance(item, dict):
            raise ValueError(f"case {index} must be a JSON object")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"case {index} needs a non-empty string id")
        if case_id in seen:
            raise ValueError(f"duplicate case id {case_id!r}")
        seen.add(case_id)
        validated.append(item)
    if require_minimum and len(validated) < 5:
        raise ValueError("need at least five cases to make non-empty train/selection/holdout splits")
    return validated


def load_cases(path):
    path = _as_path(path, "source corpus")
    cases = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: each case must be a JSON object")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{path}:{line_number}: each case needs a non-empty string id")
        cases.append(item)
    try:
        return _validate_cases(cases)
    except ValueError as exc:
        # Keep the file/line-oriented diagnostics from the loader while still
        # sharing the same fail-closed collection checks as the public API.
        if str(exc).startswith("duplicate case id"):
            raise ValueError(f"{path}: {exc}") from exc
        raise


def _reject_symlink_components(path, label):
    """Reject user-controlled symlink path components, allowing macOS aliases."""
    raw = _as_path(path, label)
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current /= part
        if not current.is_symlink():
            continue
        resolved = current.resolve()
        # macOS commonly exposes /tmp and /var as aliases under /private.
        if current in {Path("/tmp"), Path("/var")} and resolved == Path("/private") / current.name:
            continue
        raise ValueError(f"{label} must not contain a symlink component: {current}")


def _atomic_write_text(path, content):
    path = _as_path(path, "output target")
    if path.is_symlink():
        raise ValueError(f"output target must not be a symlink: {path}")
    if path.parent.is_symlink():
        raise ValueError(f"output parent must not be a symlink: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Link-then-unlink publishes the completed file atomically while
        # refusing to replace a target created by another process.
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValueError(f"output target already exists; refusing to overwrite: {path}") from exc
    except Exception:
        raise
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def split_cases(cases, seed, train_ratio, selection_ratio):
    cases = _validate_cases(cases)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    train_ratio = _finite_ratio(train_ratio, "train_ratio")
    selection_ratio = _finite_ratio(selection_ratio, "selection_ratio")
    if not 0 < train_ratio < 1 or not 0 < selection_ratio < 1:
        raise ValueError("ratios must be between 0 and 1")
    if train_ratio + selection_ratio >= 1:
        raise ValueError("train_ratio + selection_ratio must be below 1")
    ordered = sorted(cases, key=lambda case: case["id"])
    random.Random(seed).shuffle(ordered)
    count = len(ordered)
    train_end = max(1, min(count - 2, round(count * train_ratio)))
    selection_end = max(train_end + 1, min(count - 1, round(count * (train_ratio + selection_ratio))))
    return {
        "train": ordered[:train_end],
        "selection": ordered[train_end:selection_end],
        "holdout": ordered[selection_end:],
    }


def write_jsonl(path, cases):
    cases = _validate_cases(cases, require_minimum=False)
    _atomic_write_text(path, "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases))


def ids_sha256(case_ids):
    """Hash the ordered IDs so a manifest cannot silently change task membership."""
    payload = json.dumps(list(case_ids), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_splits(
    source,
    output_dir,
    seed=42,
    train_ratio=0.6,
    selection_ratio=0.2,
    evaluator_name="manual",
    evaluator_version="1",
    evaluator_command=None,
    evaluator_files=None,
    evaluator_trust=None,
):
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    train_ratio = _finite_ratio(train_ratio, "train_ratio")
    selection_ratio = _finite_ratio(selection_ratio, "selection_ratio")
    raw_source = _as_path(source, "source corpus")
    if raw_source.is_symlink():
        raise ValueError("source corpus must not be a symlink")
    _reject_symlink_components(raw_source, "source corpus")
    if not raw_source.is_file():
        raise ValueError("source corpus must be a regular file")
    source = raw_source.resolve()
    output_dir = _as_path(output_dir, "output_dir")
    if output_dir.is_symlink():
        raise ValueError("output_dir must not be a symlink")
    _reject_symlink_components(output_dir, "output_dir")
    output_dir = output_dir.resolve()
    if output_dir == source or output_dir in source.parents:
        raise ValueError("source corpus must be outside output_dir")
    command, declared_files, trust = _validate_evaluator_declaration(
        evaluator_name,
        evaluator_version,
        evaluator_command,
        evaluator_files,
        evaluator_trust,
    )
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    cases = load_cases(source)
    splits = split_cases(cases, seed, train_ratio, selection_ratio)
    output_names = ["train.jsonl", "selection.jsonl", "holdout.jsonl", "test.jsonl", "manifest.json"]
    split_payloads = {
        name: "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in items)
        for name, items in splits.items()
    }
    split_files = {}
    for name, items in splits.items():
        split_payload = split_payloads[name].encode("utf-8")
        case_ids = [item["id"] for item in items]
        split_files[name] = {
            "path": f"{name}.jsonl",
            "sha256": hashlib.sha256(split_payload).hexdigest(),
            "id_sha256": ids_sha256(case_ids),
            "count": len(case_ids),
        }
    # Preserve the original filename for callers migrating from the first gate.
    alias_payload = split_payloads["holdout"]
    alias_hash = hashlib.sha256(alias_payload.encode("utf-8")).hexdigest()
    manifest = {
        "source": str(source),
        "source_sha256": source_hash,
        "seed": seed,
        "ratios": {
            "train": train_ratio,
            "selection": selection_ratio,
            "holdout": 1 - train_ratio - selection_ratio,
        },
        "schema_version": 1,
        "counts": {name: len(items) for name, items in splits.items()},
        "splits": {name: [item["id"] for item in items] for name, items in splits.items()},
        "split_files": split_files,
        "holdout_alias_sha256": alias_hash,
        "evaluator": {"name": evaluator_name, "version": evaluator_version},
        "contract": "Mine edits from train only; selection gates candidates; holdout runs once for release evidence.",
    }
    manifest["evaluator_trust"] = trust
    if command is not None:
        manifest["evaluator_command"] = command
        manifest["evaluator_files"] = declared_files
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    output_payloads = {
        **{f"{name}.jsonl": payload for name, payload in split_payloads.items()},
        "test.jsonl": alias_payload,
        "manifest.json": manifest_payload,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if declared_files is not None:
        # Evaluator files are expected to be prepared beside the source/output
        # manifest; verify their bytes before writing any output. We defer the
        # check until the output directory exists to support nested paths.
        _validate_evaluator_files_on_disk(output_dir, declared_files)
    existing = {}
    for output_name in output_names:
        destination = output_dir / output_name
        if destination.is_symlink():
            raise ValueError(f"output target must not be a symlink: {destination}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"output target must be a regular file: {destination}")
        existing[output_name] = destination.exists()
    if any(existing.values()):
        if not all(existing.values()):
            raise ValueError("output directory contains partial split outputs; refusing to overwrite")
        mismatched = [
            name for name, payload in output_payloads.items()
            if (output_dir / name).read_bytes() != payload.encode("utf-8")
        ]
        if mismatched:
            raise ValueError(
                "output already exists with different content; refusing to overwrite: "
                + ", ".join(mismatched)
            )
        return manifest
    for output_name, payload in output_payloads.items():
        _atomic_write_text(output_dir / output_name, payload)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Split Skill evaluation cases into train, selection, and holdout")
    parser.add_argument("source", help="JSONL source with stable case id fields")
    parser.add_argument("output_dir", help="Directory for train.jsonl, selection.jsonl, holdout.jsonl, and manifest.json (test.jsonl is a compatibility alias)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--selection-ratio", type=float, default=0.2)
    parser.add_argument("--evaluator-name", default="manual", help="Stable evaluator name recorded in the manifest")
    parser.add_argument("--evaluator-version", default="1", help="Evaluator version recorded in the manifest")
    parser.add_argument(
        "--evaluator-command",
        help="Shell-free evaluator command (must reference a file listed by --evaluator-files)",
    )
    parser.add_argument(
        "--evaluator-file",
        action="append",
        dest="evaluator_files",
        metavar="PATH=SHA256",
        help="Hashed evaluator file relative to output_dir; may be repeated",
    )
    parser.add_argument(
        "--evaluator-trust",
        choices=("trusted", "untrusted"),
        help="Explicit evaluator trust state (trusted requires command and file hashes)",
    )
    args = parser.parse_args(argv)
    try:
        evaluator_files = None
        if args.evaluator_files:
            evaluator_files = {}
            for declaration in args.evaluator_files:
                if not isinstance(declaration, str) or "=" not in declaration:
                    raise ValueError("--evaluator-file must use PATH=SHA256")
                filename, digest = declaration.split("=", 1)
                if not filename or not digest:
                    raise ValueError("--evaluator-file must use PATH=SHA256")
                if filename in evaluator_files:
                    raise ValueError(f"duplicate evaluator file: {filename}")
                evaluator_files[filename] = digest
        manifest = create_splits(
            args.source,
            args.output_dir,
            args.seed,
            args.train_ratio,
            args.selection_ratio,
            args.evaluator_name,
            args.evaluator_version,
            args.evaluator_command,
            evaluator_files,
            args.evaluator_trust,
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
