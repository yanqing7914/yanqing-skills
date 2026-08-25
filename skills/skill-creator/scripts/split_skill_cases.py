#!/usr/bin/env python3
"""Create deterministic train/selection/holdout JSONL splits for a Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import tempfile
from pathlib import Path


def load_cases(path):
    cases = []
    seen = set()
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
        if case_id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate case id {case_id!r}")
        seen.add(case_id)
        cases.append(item)
    if len(cases) < 5:
        raise ValueError("need at least five cases to make non-empty train/selection/holdout splits")
    return cases


def _reject_symlink_components(path, label):
    """Reject user-controlled symlink path components, allowing macOS aliases."""
    raw = Path(path)
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
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"output target must not be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def split_cases(cases, seed, train_ratio, selection_ratio):
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
):
    raw_source = Path(source)
    if raw_source.is_symlink():
        raise ValueError("source corpus must not be a symlink")
    _reject_symlink_components(raw_source, "source corpus")
    if not raw_source.is_file():
        raise ValueError("source corpus must be a regular file")
    source = raw_source.resolve()
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise ValueError("output_dir must not be a symlink")
    _reject_symlink_components(output_dir, "output_dir")
    output_dir = output_dir.resolve()
    if output_dir == source or output_dir in source.parents:
        raise ValueError("source corpus must be outside output_dir")
    if not isinstance(evaluator_name, str) or not evaluator_name.strip():
        raise ValueError("evaluator_name must be a non-empty string")
    if not isinstance(evaluator_version, str) or not evaluator_version.strip():
        raise ValueError("evaluator_version must be a non-empty string")
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    cases = load_cases(source)
    splits = split_cases(cases, seed, train_ratio, selection_ratio)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_names = ["train.jsonl", "selection.jsonl", "holdout.jsonl", "test.jsonl", "manifest.json"]
    for output_name in output_names:
        destination = output_dir / output_name
        if destination.is_symlink():
            raise ValueError(f"output target must not be a symlink: {destination}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"output target must be a regular file: {destination}")
    split_files = {}
    for name, items in splits.items():
        split_path = output_dir / f"{name}.jsonl"
        write_jsonl(split_path, items)
        case_ids = [item["id"] for item in items]
        split_files[name] = {
            "path": split_path.name,
            "sha256": hashlib.sha256(split_path.read_bytes()).hexdigest(),
            "id_sha256": ids_sha256(case_ids),
            "count": len(case_ids),
        }
    # Preserve the original filename for callers migrating from the first gate.
    holdout_alias = output_dir / "test.jsonl"
    write_jsonl(holdout_alias, splits["holdout"])
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
        "holdout_alias_sha256": hashlib.sha256(holdout_alias.read_bytes()).hexdigest(),
        "evaluator": {"name": evaluator_name, "version": evaluator_version},
        "contract": "Mine edits from train only; selection gates candidates; holdout runs once for release evidence.",
    }
    _atomic_write_text(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
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
    args = parser.parse_args(argv)
    try:
        manifest = create_splits(
            args.source,
            args.output_dir,
            args.seed,
            args.train_ratio,
            args.selection_ratio,
            args.evaluator_name,
            args.evaluator_version,
        )
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
