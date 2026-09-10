# Dependency Upgrade Workflow

Use when upgrading libraries, frameworks, or language toolchains.

This file is the full Complex path. Complexity classification overrides it.

Dependency install stays blocked unless Main Session explicitly authorizes the install command on the Implementer task card. Default remains blocked.

## When To Use

- Package or framework upgrades
- Breaking-change upgrades
- Lockfile or toolchain updates

## Main Session Decision

Inventory breaking changes before editing. Upgrade in the smallest safe scope.

Before any install or lockfile-mutating command, Main Session must write the authorized command on the Implementer task card. Without that authorization, Implementer must stop.

## Subagents

- Explorer: identify affected usage and breaking changes
- Implementer: apply the upgrade and required code updates
- Reviewer: check compatibility and unintended churn
- Main Session: run tests, builds, or install checks. Do not spawn Verifier.

## Flow

1. Main Session confirms the target versions and compatibility constraints.
2. Explorer maps current usage and likely breaking changes.
3. Main Session approves the upgrade scope.
4. Implementer applies the upgrade only after the task card authorizes required install commands.
5. Reviewer checks compatibility risk.
6. Main Session validates the project still builds and tests.

## Expected Output

- Target versions
- Breaking changes handled
- Files changed
- Validation results
- Remaining compatibility risk
