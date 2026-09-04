#!/usr/bin/env python3
"""Run conservative, read-only local health checks for a GitHub repository."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def run(*args: str, cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.strip()


def finding(severity: str, title: str, evidence: str, impact: str, recommendation: str, confidence: str = "confirmed") -> dict[str, str]:
    return {
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "impact": impact,
        "recommendation": recommendation,
        "confidence": confidence,
    }


def has(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def repository_files(root: Path) -> tuple[list[str], bool]:
    """Return files in scope and whether the list came from Git tracking."""
    if (root / ".git").exists():
        tracked = run("git", "ls-files", "-z", cwd=root)
        return [item for item in tracked.split("\0") if item], True
    files = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not ({".git", "debug", "tmp", "node_modules", ".venv", "__pycache__"} & set(p.parts))
    ]
    return files, False


def docker_instructions(text: str, instruction: str) -> list[tuple[int, str]]:
    """Extract logical Docker instructions, including ``\\`` continuations."""
    result: list[tuple[int, str]] = []
    pending: list[str] = []
    pending_line = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        if not pending:
            pending_line = line_number
        continued = stripped.endswith("\\")
        pending.append(stripped[:-1].rstrip() if continued else stripped)
        if continued:
            continue
        logical = " ".join(pending)
        pending = []
        match = re.match(rf"^{instruction}\s+(.*)$", logical, re.IGNORECASE)
        if match:
            result.append((pending_line, match.group(1).strip()))
    if pending:
        logical = " ".join(pending)
        match = re.match(rf"^{instruction}\s+(.*)$", logical, re.IGNORECASE)
        if match:
            result.append((pending_line, match.group(1).strip()))
    return result


def docker_base_images(text: str) -> list[tuple[int, str]]:
    images: list[tuple[int, str]] = []
    for line_number, value in docker_instructions(text, "FROM"):
        try:
            tokens = shlex.split(value, comments=False, posix=True)
        except ValueError:
            tokens = value.split()
        while tokens and tokens[0].startswith("--"):
            tokens.pop(0)
        if tokens:
            images.append((line_number, tokens[0]))
    return images


def is_root_user(value: str) -> bool:
    token = value.split()[0] if value.split() else ""
    username = token.split(":", 1)[0].lower()
    return username in {"root", "0"}


def audit(root: Path) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    checks: list[str] = []
    all_files, files_are_tracked = repository_files(root)
    workflow_paths = {
        Path(relative)
        for relative in all_files
        if relative.startswith(".github/workflows/") and Path(relative).suffix in {".yml", ".yaml"}
    }
    workflows = sorted(root / path for path in workflow_paths)
    if files_are_tracked:
        checks.append(f"{len(all_files)} tracked file(s) inspected")

    if not has(root, "README.md") and not has(root, "README.rst"):
        findings.append(finding("P2", "Repository has no README", "README.md/README.rst missing", "New contributors and operators lack the project entry point.", "Add a README with local setup, test, release, deploy, and rollback commands."))
    else:
        checks.append("README present")
    if not has(root, ".gitignore"):
        findings.append(finding("P2", "Repository has no .gitignore", ".gitignore missing", "Build output, local credentials, or editor files can be committed accidentally.", "Add a language-appropriate .gitignore and review existing tracked files."))
    else:
        checks.append(".gitignore present")
    if not has(root, "LICENSE") and not any(p.startswith("LICENSE.") for p in all_files):
        findings.append(finding("P3", "License is not declared", "LICENSE file missing", "Reuse and contribution terms are ambiguous.", "Add the appropriate license or document the private-project policy."))
    if not has(root, "SECURITY.md"):
        findings.append(finding("P3", "Security policy is missing", "SECURITY.md missing", "Security reporters do not have a documented disclosure path.", "Add SECURITY.md for projects exposed outside a trusted team."))

    if not workflows:
        findings.append(finding("P1", "No GitHub Actions workflow found", ".github/workflows/*.yml missing", "Pull requests and releases have no repository-enforced automation.", "Add a minimal PR CI workflow before relying on manual validation."))
    else:
        checks.append(f"{len(workflows)} workflow(s) found")
        workflow_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in workflows)
        if "pull_request" not in workflow_text:
            findings.append(finding("P1", "CI does not show a pull_request trigger", ".github/workflows/*.yml", "Broken changes may merge without repository-side validation.", "Trigger CI on pull_request and require it in branch protection."))
        if "permissions:" not in workflow_text:
            findings.append(finding("P2", "Workflow permissions are not explicit", ".github/workflows/*.yml", "A future default-permission change can grant more access than intended.", "Declare least-privilege top-level and job-level permissions."))
        if re.search(r"^\s*(?:-\s*)?uses:\s+(?!\./|docker://)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@(?!(?:[0-9a-fA-F]{40})$)[^\s]+\s*$", workflow_text, re.MULTILINE):
            findings.append(finding("P2", "At least one Action is not pinned", ".github/workflows/*.yml", "A moving action tag can change CI behavior without a repository commit.", "Pin third-party actions to a full commit SHA and annotate the version."))
        if "docker build" in workflow_text and not has(root, ".dockerignore"):
            findings.append(finding("P2", "Docker build has no .dockerignore", ".dockerignore missing", "Secrets, tests, and large local files can enter the build context.", "Add .dockerignore and explicitly allow only build inputs."))

    tags = run("git", "tag", "--list", cwd=root) if (root / ".git").exists() else ""
    if tags:
        checks.append(f"{len(tags.splitlines())} Git tag(s) found")
        semver = [tag for tag in tags.splitlines() if re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", tag)]
        if not semver:
            findings.append(finding("P2", "Tags do not use an obvious SemVer form", "git tag --list", "Release ordering and automation may be ambiguous.", "Document and enforce one version format, preferably SemVer."))
    else:
        findings.append(finding("P2", "No version tags exist", "git tag --list returned no tags", "There is no durable repository-level release identity.", "Create a documented first release tag and use it for published artifacts."))

    dockerfiles = [
        root / rel
        for rel in all_files
        if Path(rel).name.startswith("Dockerfile")
    ]
    for dockerfile in dockerfiles:
        text = dockerfile.read_text(encoding="utf-8", errors="replace")
        rel = dockerfile.relative_to(root).as_posix()
        for line_number, image in docker_base_images(text):
            if not re.search(r"@sha256:[0-9a-fA-F]{64}(?:$|\s)", image):
                findings.append(finding("P2", "Docker base image is not digest-pinned", f"{rel}:{line_number} ({image})", "A rebuild can silently consume a different base image.", "Pin production base images by digest and update them through review."))
        from_lines = [line_number for line_number, _ in docker_instructions(text, "FROM")]
        final_stage_start = from_lines[-1] if from_lines else 0
        users = [(line_number, value) for line_number, value in docker_instructions(text, "USER") if line_number > final_stage_start]
        if not users or is_root_user(users[-1][1]):
            evidence = f"{rel}:{users[-1][0]} ({users[-1][1]})" if users else rel
            findings.append(finding("P2", "Docker image does not declare a non-root user", evidence, "A container compromise has a larger impact when the process runs as root.", "Create/use an unprivileged user unless root is required and documented."))
        healthchecks = [
            value for line_number, value in docker_instructions(text, "HEALTHCHECK")
            if line_number > final_stage_start
        ]
        if not any(value.strip().upper() != "NONE" for value in healthchecks):
            findings.append(finding("P3", "Docker image has no HEALTHCHECK", rel, "Orchestrators cannot distinguish a running process from a ready service.", "Add a cheap health or readiness check where the service supports one."))

    secret_patterns = re.compile(
        r"(ghp_[A-Za-z0-9]{32,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|"
        r"-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----)"
    )
    for rel in all_files:
        if ".github/workflows" in rel or rel.endswith((".md", ".yaml", ".yml", ".json", ".py", ".sh", ".ts", ".js")):
            try:
                text = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if secret_patterns.search(text):
                findings.append(finding("P1", "Possible credential material is tracked", rel, "A committed token or private key may allow unauthorized access if the value is live.", "Confirm whether the value is a fixture; if live, revoke/rotate it, remove it from history, and enable secret scanning.", "likely"))

    return {"repository": str(root), "workflow_count": len(workflows), "findings": findings, "positive_checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"repository root is not a directory: {root}")
    result = audit(root)
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"Repository: {result['repository']}")
        for item in result["findings"]:
            print(f"[{item['severity']}] {item['title']} ({item['confidence']})")
            print(f"  Evidence: {item['evidence']}")
            print(f"  Impact: {item['impact']}")
            print(f"  Recommendation: {item['recommendation']}")
        print("Positive checks:")
        for check in result["positive_checks"]:
            print(f"  - {check}")
    return 1 if any(item["severity"] in {"P0", "P1"} for item in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
