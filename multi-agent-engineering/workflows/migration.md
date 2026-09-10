# Migration Workflow

Use for framework, language, database, or platform migrations.

This file is the full Complex path. Complexity classification overrides it.

Migration commands stay blocked unless Main Session explicitly authorizes them on the Implementer task card. Default remains blocked.

## When To Use

- Moving between frameworks or runtimes
- Database or storage migrations
- Major version upgrades that change architecture

## Main Session Decision

Treat migration as phased work. Do not attempt a one-shot rewrite unless the scope is already small and confirmed.

Before any migration command, Main Session must write the authorized command on the Implementer task card. Without that authorization, Implementer must stop.

## Subagents

- Explorer: inventory current surface area and compatibility risks
- Implementer: execute one confirmed phase at a time
- Reviewer: check compatibility and rollback risk
- Main Session: confirm each phase preserves required behavior. Do not spawn Verifier.

## Flow

1. Main Session clarifies target platform, compatibility requirements, and allowed downtime.
2. Explorer maps current components and migration risks.
3. Main Session defines phases and boundaries.
4. Implementer completes the current phase only after the task card authorizes required migration commands.
5. Reviewer checks compatibility impact.
6. Main Session validates the phase.
7. Main Session reports progress and remaining phases.

## Expected Output

- Migration plan
- Completed phase
- Remaining work
- Compatibility risks
- Validation results
