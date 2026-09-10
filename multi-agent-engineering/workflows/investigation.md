# Investigation Workflow

Use when the cause is unknown and the task is diagnosis, not an immediate fix.

This file is the full Complex path. Complexity classification overrides it.

Do not use Verifier to investigate hypotheses. Use Explorer or Main Session for hypothesis checks. Verifier only validates after a fix exists.

## When To Use

- Unexplained failures
- Performance regressions
- Complex production symptoms
- Technical-debt analysis

## Main Session Decision

Do not assign an Implementer until a likely root cause exists. Prefer investigation over guessing a patch.

## Subagents

- Explorer: gather evidence and hypotheses
- Additional Explorers: only when independent areas need parallel investigation
- Main Session or Explorer: check the leading hypothesis (read-only)
- Implementer: only after Main Session confirms the diagnosis

## Flow

1. Main Session records the symptom, expected behavior, and known constraints.
2. Explorer investigates code, logs, tests, or recent changes.
3. Main Session reviews findings and ranks hypotheses.
4. Explorer or Main Session checks the leading hypothesis. Do not spawn Verifier for this.
5. Main Session reports the diagnosis and recommended next action.

## Expected Output

- Symptom
- Evidence
- Hypotheses
- Most likely cause
- Recommended next step
