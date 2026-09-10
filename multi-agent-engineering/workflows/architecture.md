# Architecture Workflow

Use when the user needs a design, architecture assessment, or system-split decision before implementation.

This file is the full Complex path. Complexity classification overrides it.

## When To Use

- Designing a new subsystem
- Evaluating whether to split or restructure modules
- Choosing between technical approaches

## Main Session Decision

Do not start implementation. Clarify constraints, then investigate current architecture.

## Subagents

- Explorer: map current structure, dependencies, and constraints
- Reviewer: challenge the proposed design
- Implementer: only if the user later asks to implement the approved plan

## Flow

1. Main Session clarifies goals, constraints, and non-goals.
2. Explorer maps current architecture and relevant files.
3. Main Session reviews findings and drafts a design proposal.
4. Reviewer evaluates trade-offs, risks, and missing alternatives.
5. Main Session delivers the architecture summary.

## Expected Output

- Current state
- Proposed design
- Trade-offs
- Risks
- Recommended next step
