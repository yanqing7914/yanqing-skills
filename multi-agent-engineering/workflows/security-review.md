# Security Review Workflow

Use when the user asks for security analysis or a change touches auth, secrets, permissions, or untrusted input.

This file is the full Complex path. Complexity classification overrides it.

## When To Use

- Login, auth, or permission changes
- Handling secrets, tokens, or user input
- Explicit security review requests

## Main Session Decision

Keep the first pass read-only. Do not mix security review with unrelated implementation.

## Subagents

- Explorer: map the relevant trust boundary and data flow
- Reviewer: identify security findings with severity and evidence
- Implementer: only after Main Session and the user accept the fix scope
- Main Session: confirm the accepted findings are addressed. Do not spawn Verifier.

## Flow

1. Main Session defines the review target and sensitivity constraints.
2. Explorer maps the relevant flow and files.
3. Reviewer reports findings by severity with evidence.
4. Main Session decides which findings need fixes.
5. Implementer applies approved fixes only if requested.
6. Main Session checks the accepted findings.

## Expected Output

- Findings by severity
- Evidence
- Recommended fixes
- Residual risk
