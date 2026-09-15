#!/usr/bin/env python3
"""Aggregate run timing and exit-status evidence; no synthetic quality scores."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def aggregate(run_file: Path) -> dict:
    if run_file.is_symlink() or not run_file.is_file():
        raise ValueError("run JSON must be a regular file")
    report = json.loads(run_file.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("run JSON must have schema_version 1")
    if not isinstance(report.get("results"), dict):
        raise ValueError("run JSON results must be an object")
    summary = {"schema_version": 1, "source": str(run_file), "configurations": {}}
    for label, rows in report.get("results", {}).items():
        if not isinstance(label, str) or not isinstance(rows, list):
            raise ValueError("each run configuration must map to a list")
        durations = []
        passed = 0
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise ValueError(f"{label}: each result must contain a string id")
            duration = row.get("duration_seconds")
            if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise ValueError(f"{label}/{row['id']}: duration_seconds must be finite and non-negative")
            durations.append(duration)
            if row.get("returncode") == 0:
                passed += 1
        summary["configurations"][label] = {
            "cases": len(rows),
            "successful_processes": passed,
            "process_success_rate": (passed / len(rows)) if rows else None,
            "mean_duration_seconds": (sum(durations) / len(durations)) if durations else None,
            "quality_score": None,
            "quality_note": "No evaluator score is inferred from process success; provide independent grading evidence.",
        }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate Skill eval timing without fabricating quality scores")
    parser.add_argument("run_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = aggregate(args.run_json)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote benchmark summary to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
