# Test Improvement Workflow

Use when the user wants better coverage, missing tests, or stronger regression protection.

This file is the full Complex path. Complexity classification overrides it. Verifier is optional if there is no validation command.

## When To Use

- Low coverage
- Missing tests for a risky area
- Adding regression tests after a bug

## Main Session Decision

Find the weakest important area first. Do not generate broad, low-value tests.

## Subagents

- Explorer: locate untested or weakly tested risk areas
- Implementer: add or improve tests in the approved scope
- Reviewer: check that tests assert meaningful behavior
- Main Session: run the new or updated tests. Do not spawn Verifier.

## Flow

1. Main Session clarifies the target area and success criterion.
2. Explorer identifies coverage gaps and high-risk untested paths.
3. Main Session approves the test scope.
4. Implementer adds or updates tests.
5. Reviewer checks assertion quality.
6. Main Session runs the tests. Do not spawn Verifier.

## Expected Output

- Target area
- Tests added or changed
- Validation results
- Remaining coverage gaps
