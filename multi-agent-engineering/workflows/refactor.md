# Refactoring Workflow

Use for structural changes.

This file is the full Complex path. Complexity classification overrides it: Simple = Main Session only; Medium = Explorer + Implementer, skip Reviewer/Verifier unless needed.

## Flow

1. Main Session clarifies the refactor goal, invariants, and what must not change.
2. Explorer maps current architecture.
3. Main Session evaluates findings and defines refactoring boundaries.
4. Implementer performs incremental changes.
5. Reviewer evaluates design impact.
6. Main Session checks behavior preservation. Do not spawn Verifier.
7. Main Session delivers results.
