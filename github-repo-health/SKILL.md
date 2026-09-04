---
name: github-repo-health
description: Audit a local GitHub repository for structural, CI/CD, release, security, dependency, Docker, and maintainability risks. Use when a user asks whether a repository is initialized correctly, whether its GitHub Actions or release process has problems, how healthy a repository is, or what should be improved before production. Prefer read-only inspection and report verified findings separately from checks that require GitHub API access.
---

# GitHub Repo Health

Perform a read-only health audit of a repository and produce an evidence-based
report. Do not change files, create branches, push commits, trigger workflows,
or alter GitHub settings unless the user explicitly asks for a separate fix.

## Quick Start

1. Identify the repository root. Accept the current checkout or a local path
   for the bundled checker. A GitHub URL is supported at the Skill level only:
   use an available GitHub/API or browser tool to inspect it, and do not claim
   that `scripts/audit_repo.py` can consume the URL directly.
2. Read repository-local `AGENTS.md`, `CLAUDE.md`, and relevant security or
   contribution instructions before interpreting findings.
3. Run the bundled local checker from the repository root:

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/github-repo-health/scripts/audit_repo.py" .
   ```

   When `CODEX_HOME` is unset, use `~/.codex/skills/github-repo-health/scripts/audit_repo.py`.
4. Inspect the reported files and workflow details. Use `rg --files` and `rg`
   rather than broad recursive commands.
5. If GitHub access is available, separately inspect branch protection/rulesets,
   required status checks, Actions permissions, environments, secrets naming,
   Dependabot, recent workflow runs, and release/tag state. Mark API-dependent
   checks as `unverified` when access is unavailable.

## Implemented Local Checks

The bundled checker currently implements:

- README, `.gitignore`, LICENSE, and `SECURITY.md` presence;
- PR workflow presence, explicit workflow permissions, and third-party Action
  pinning to a full 40-character commit SHA;
- Git tag presence and an obvious SemVer shape;
- tracked-file-only scanning in Git repositories;
- Docker `FROM` digest pinning, final-stage non-root `USER`, and final-stage
  `HEALTHCHECK` checks;
- conservative pattern detection for common GitHub/cloud credentials.

Treat these results as static evidence. They do not prove that a remote GitHub
setting or a running container is secure.

## Manual and GitHub-Side Checks

Cover these areas, adapting to the repository's actual technology and risk:

- **Repository foundation**: contribution guidance, source/test layout, and
  accidental generated files require contextual review; the bundled checker
  only implements the presence checks listed above.
- **Git and versioning**: default branch, tag format, SemVer consistency,
  mutable tags such as `latest`, release notes, changelog, and whether a
  published artifact can be traced to a commit.
- **CI**: test/lint/type-check coverage, dependency installation
  reproducibility, caching, timeouts, concurrency, artifact retention, and
  failure behavior require contextual review; only the trigger, permissions,
  and Action pin checks are implemented locally.
- **CD and releases**: immutable image/artifact identity, build/deploy
  separation, environment approvals, dry-run or staging validation, rollback,
  deployment health checks, and provenance manifest coverage require contextual
  review unless the repository provides explicit machine-readable contracts.
- **Security**: the local checker covers explicit workflow permissions, common
  credential patterns, and Docker user/root posture. Unsafe shell
  interpolation, untrusted pull-request permissions, OIDC, dependency
  scanning, and secret-scanning configuration require contextual or GitHub-side
  review.
- **Docker and deployment**: pinned base images, multi-stage builds, small
  context, `.dockerignore`, healthcheck, non-root execution, target-specific
  configuration, and reproducible compose/manifests.
- **Maintainability**: duplicated workflows, scripts without tests, stale
  references, undocumented manual steps, excessive environment-specific
  special cases, and missing observability require contextual review.

## Severity and Evidence

Use the following severity levels:

- **P0**: active compromise, destructive deployment risk, or inability to
  identify/rollback production artifacts.
- **P1**: likely production outage, bypassable release gate, secret exposure,
  or materially unsafe CI/CD behavior.
- **P2**: important reliability, security, or maintainability weakness.
- **P3**: polish, documentation, or optimization opportunity.

Every finding must include:

```text
[P1] Short title
Evidence: path:line or command output
Impact: what can fail or become unsafe
Recommendation: smallest coherent correction
Confidence: confirmed | likely | unverified
```

Do not call a missing GitHub setting a confirmed defect from local files alone.
Say `unverified: inspect GitHub rulesets/API` when the repository cannot prove
the setting. Avoid inventing standards that do not apply to the project.

## Output Format

Start with the result, then list findings ordered by severity. Keep the report
concise and actionable:

1. One-line overall assessment and scope inspected.
2. Findings, highest severity first, with file references.
3. Unverified GitHub-side checks.
4. Positive controls already present.
5. A prioritized repair sequence, normally no more than five items.
6. Commands run and any limitations.

If no findings are found, state that explicitly and list residual risks or
unverified GitHub-side checks. A health score is optional; never let a score
replace evidence or hide a P0/P1 finding.

## Bundled Checker

Use `scripts/audit_repo.py` for the implemented deterministic local checks. It
emits JSON to stdout by default and supports `--format text` for a compact
human-readable view. Treat its results as leads to verify, not as a substitute
for reviewing the exact workflow and project context.

Load `references/github-checklist.md` when a deeper GitHub-side review is
requested or when deciding which API/settings checks remain unverified.
