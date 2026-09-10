# Performance Workflow

Use when the user wants to diagnose or improve latency, throughput, or resource use.

This file is the full Complex path. Complexity classification overrides it.

## When To Use

- Slow APIs or pages
- High CPU, memory, or I/O
- Explicit optimization requests

## Main Session Decision

Measure before changing. Do not optimize without a bottleneck and a success criterion.

## Subagents

- Explorer: locate likely bottlenecks
- Implementer: apply scoped optimizations
- Reviewer: check for correctness or regression risk
- Main Session: compare before/after behavior and measurements. Do not spawn Verifier.

## Flow

1. Main Session clarifies the slow path and success criterion.
2. Explorer identifies likely bottlenecks and relevant files.
3. Main Session confirms the optimization target.
4. Implementer applies scoped changes.
5. Reviewer checks correctness risk.
6. Main Session reports before/after results.

## Expected Output

- Bottleneck
- Change made
- Before metrics
- After metrics
- Remaining risk
