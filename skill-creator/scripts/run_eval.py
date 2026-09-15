#!/usr/bin/env python3
"""Run declared Skill eval cases against one or two Skill trees.

The runner captures raw outputs, exit status, and timing. It deliberately does
not grade outputs or infer quality scores from process success; a separate,
independent evaluator is required before using ``skill_gate.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
import re


SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _load_cases(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("eval file must be a regular file")
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("evals") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("eval file must contain a non-empty evals list")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case.get("id"):
            raise ValueError("each eval must contain a non-empty string id")
        if not SAFE_CASE_ID.fullmatch(case["id"]):
            raise ValueError(f"eval id is not a safe path component: {case['id']!r}")
        if not isinstance(case.get("prompt"), str) or not case.get("prompt"):
            raise ValueError(f"eval {case['id']}: prompt must be a non-empty string")
        if case["id"] in ids:
            raise ValueError(f"duplicate eval id: {case['id']}")
        ids.add(case["id"])
    return cases


def _run_case(case: dict, skill: Path | None, output_dir: Path, timeout: int) -> dict:
    if output_dir.exists() and output_dir.is_symlink():
        raise ValueError(f"output path must not be a symlink: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = case["prompt"]
    command = case.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError(f"eval {case['id']}: command must be a non-empty argv list")
    env = os.environ.copy()
    env["SKILL_PATH"] = str(skill) if skill else ""
    started = time.monotonic()
    timed_out = False
    error = None
    try:
        completed = subprocess.run(
            [*command, prompt],
            cwd=skill.parent if skill else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        error = f"timeout after {timeout}s"
        completed = subprocess.CompletedProcess(command, returncode=None, stdout=exc.stdout or "", stderr=exc.stderr or "")
    except OSError as exc:
        error = str(exc)
        completed = subprocess.CompletedProcess(command, returncode=None, stdout="", stderr=str(exc))
    elapsed = time.monotonic() - started
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    result = {
        "id": case["id"],
        "prompt": prompt,
        "returncode": completed.returncode,
        "timed_out": timed_out,
        "duration_seconds": round(elapsed, 6),
        "stdout": "stdout.txt",
        "stderr": "stderr.txt",
        "evidence": "stdout.txt",
    }
    if error:
        result["error"] = error
    return result


def run(eval_file: Path, output: Path, current_skill: Path | None, candidate_skill: Path | None, timeout: int) -> dict:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    cases = _load_cases(eval_file)
    for label, skill in (("current", current_skill), ("candidate", candidate_skill)):
        if skill is not None and (skill.is_symlink() or not skill.is_dir()):
            raise ValueError(f"{label} Skill path must be a real directory")
    if output.exists() and output.is_symlink():
        raise ValueError("output directory must not be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "eval_file": str(eval_file), "results": {}}
    for label, skill in (("current", current_skill), ("candidate", candidate_skill)):
        if skill is None:
            continue
        report["results"][label] = []
        for case in cases:
            report["results"][label].append(
                _run_case(case, skill, output / label / str(case["id"]), timeout)
            )
    (output / "run.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run declared Skill eval cases without fabricating scores")
    parser.add_argument("eval_file", type=Path, help="JSON file containing an evals list")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current-skill", type=Path)
    parser.add_argument("--candidate-skill", type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.current_skill and not args.candidate_skill:
        parser.error("at least one of --current-skill or --candidate-skill is required")
    try:
        run(args.eval_file, args.output, args.current_skill, args.candidate_skill, args.timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    print(f"Wrote eval run artifacts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
