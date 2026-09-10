# Complexity Assessment

Classify tasks before execution. This classification overrides workflow files. Workflows describe the full Complex path; Simple and Medium must trim steps.

## Simple

Single area, clear change, low risk.

Use Main Session directly. Skip Explorer, Reviewer, and Verifier. Do not follow unused workflow steps.

## Medium

Requires investigation or multiple steps.

Use Explorer and Implementer. Skip Reviewer and Verifier unless independent review or a named validation command is required.

## Complex

Large scope, uncertainty, or high risk.

Use Explorer, Implementer, and Reviewer. Main Session verifies. Follow the full workflow. Do not spawn Verifier.

## Override

If a workflow lists Reviewer or Verifier and complexity is Simple or Medium, omit those steps. Do not spawn extra roles just because the workflow file includes them.

If the root cause is already known, skip Explorer.

Never assign overlapping `allowed_paths` to two Implementers.
