# Bug Fix Workflow

Use for debugging and repairing existing behavior.

This file is the full Complex path. Complexity classification overrides it: Simple = Main Session only; Medium = Explorer + Implementer, skip Reviewer/Verifier unless needed.

If the root cause is already known, skip Explorer.

## Flow

1. Main Session understands the symptom and expected behavior.
2. Explorer investigates root cause.
3. Main Session reviews findings before assigning implementation.
4. Implementer applies the fix.
5. Main Session confirms regression behavior. Do not spawn Verifier.
6. Main Session reports outcome.
