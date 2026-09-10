# Subagent Delegation

Decide whether native subagents are worth using.

Complexity classification overrides workflow files. Workflows describe the full Complex path; Simple/Medium must trim steps.

## Simple

Handle directly when the change is small, the path is obvious, and investigation is unnecessary.

## Medium

Use Explorer, then Implementer.

## Complex

Use Explorer, Implementer, and Reviewer. Main Session verifies. Do not spawn Verifier.

## Spawn Rules

- One task card per subagent from `templates/subagent-task.md` only
- Paste the role Forbidden/Output into the prompt
- Reviewer: `explore` only. Verifier: do not spawn; Main Session verifies
- Never spawn two Implementers on overlapping paths
- Objective, context, scope, expected output, and validation are required
- Prefer fewer specialists over a crowd
- Do not spawn an Implementer until the plan is clear
- Read `orchestration/context.md` before sending work
