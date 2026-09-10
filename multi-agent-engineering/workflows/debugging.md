# Debugging Workflow

Use when the failure is intermittent, hard to reproduce, or needs hypothesis testing before a fix.

This file is the full Complex path. Complexity classification overrides it.

Do not use Verifier to investigate hypotheses. Use Explorer or Main Session for hypothesis checks. Verifier only validates after a fix exists, except a reproduction check that is still read-only / no code change.

## When To Use

- Flaky failures
- Race conditions or deadlocks
- Symptoms without a clear stack trace
- Cases where bugfix would guess too early

## Main Session Decision

Do not jump to a patch. Form a hypothesis, try to confirm it, then fix.

## Subagents

- Explorer: collect evidence and propose hypotheses
- Explorer or Main Session: check the leading hypothesis (read-only)
- Implementer: apply the confirmed fix
- Reviewer: check the fix does not hide the symptom
- Main Session: optional read-only reproduction check, then validate after a fix exists. Do not spawn Verifier.

## Flow

1. Main Session records the symptom, reproduction notes, and expected behavior.
2. Explorer gathers evidence and proposes hypotheses.
3. Main Session selects the leading hypothesis.
4. Explorer or Main Session attempts reproduction or hypothesis checks. Do not spawn Verifier.
5. Implementer applies the confirmed fix.
6. Main Session re-checks the original symptom after the fix exists.
7. Main Session reports cause, fix, and remaining uncertainty.

## Expected Output

- Symptom
- Hypothesis
- Evidence
- Fix
- Reproduction / validation result
