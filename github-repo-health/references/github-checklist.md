# GitHub-Side Review Checklist

Use this checklist only when the user authorizes or requests inspection of the
GitHub repository settings/API. Treat unavailable items as `unverified`.

## Repository and Rules

- Default branch is intentional and protected.
- Ruleset/branch protection requires pull requests, required CI checks, and
  review count appropriate to the team.
- Force pushes and branch deletion are restricted.
- CODEOWNERS is enabled and itself covered by review.
- Production environments require approval where risk warrants it.

## Actions

- `GITHUB_TOKEN` permissions are least privilege.
- Fork PR workflows do not expose write tokens or production secrets.
- Third-party actions are pinned or governed by an approved update policy.
- Concurrency prevents overlapping deployment to the same environment.
- Workflow runs and artifacts have sensible retention and are not expired before
  rollback evidence is no longer needed.

## Releases and Dependencies

- Releases are tied to protected tags or reviewed commits.
- Published artifacts expose commit, version, and digest identity.
- Dependabot or an equivalent update process is enabled.
- Dependency review and secret scanning are enabled where supported.
- Security advisories and private vulnerability reporting are configured when
  the repository is public or externally consumed.

## Deployment

- Registry and cloud credentials use OIDC or short-lived credentials.
- Deployment uses immutable digests or signed artifacts, not `latest`.
- Staging/canary validation happens before production.
- Rollback is documented and tested.
- Deployments emit health, version, and artifact identity evidence.
