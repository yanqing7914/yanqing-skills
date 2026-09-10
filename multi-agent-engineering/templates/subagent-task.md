# Subagent Task

The only spawn contract. Paste the matching role Forbidden/Output from `subagents/` into the prompt.

Task ID:
Mode: debugging | investigation | migration | architecture | security | performance | dependency-upgrade | test-improvement | feature | bugfix | refactor | review
Role: Explorer | Implementer | Reviewer | Verifier
Write permission: true only for Implementer inside Allowed Paths; false for Explorer, Reviewer, Verifier

## Objective

## Context

## Allowed Paths

## Forbidden Paths

- .env
- .env.*
- .npmrc
- .pypirc
- .netrc
- ~/.ssh/**
- **/*.pem
- **/*.key
- secrets, keys, credentials

## Allowed Commands

- rg / file listing / read-only inspection
- project-specific tests if listed here

## Blocked Commands

Never allowed: deploy / publish / release, git push / git reset --hard / force-push, destructive delete, production data mutation, credential sync/export.

Blocked unless this card names the command and who approved it:

- dependency install
- migration commands

## Acceptance Criteria

## Expected Output

Use `templates/result-report.md`.

## Validation Required

## Stop Conditions

- Need to edit outside allowed paths
- Need to read a forbidden path or secret value
- Need scope expansion
- Requirements are unclear
- Need a blocked command this card does not authorize
- Need to deploy, publish, or mutate production data
- Validation cannot be completed
- Tests fail for unclear or unrelated reasons
- User changes may be overwritten

## Optional

- Title
- Dependencies
- Target type: code | diff | plan | document | artifact
- may_spawn_subagents: false
