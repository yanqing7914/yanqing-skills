# Context Management

The Main Session controls what context is provided to subagents.

## Principle

Give each subagent enough information to complete its task, but avoid unnecessary context.

Paste the matching role Forbidden/Output into every spawn prompt. Do not spawn Verifier. Main Session runs verification.

## Explorer Context

Provide:
- User goal
- Repository context
- Investigation scope
- Relevant constraints

## Implementer Context

Provide:
- Confirmed objective
- Implementation plan
- Relevant findings
- Allowed paths
- Validation requirements

## Reviewer Context

Provide:
- Original goal
- Changed files
- Implementation summary
- Acceptance criteria

## Verifier Context

Provide:
- Expected behavior
- Acceptance criteria
- Validation commands
- Write forbidden; do not change files
