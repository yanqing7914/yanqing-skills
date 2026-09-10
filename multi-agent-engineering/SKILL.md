---
name: multi-agent-engineering
description: Coordinate complex software work as a Main Session that clarifies goals, classifies complexity, delegates scoped subagents, integrates results, and verifies outcomes. Use when the user wants multiple agents or subagents, parallel workers, reviewers, investigation, refactoring, migration, security review, or a lead agent that plans and delegates. Do not use for ordinary single-session coding, bugfixes, or tests when multi-agent work is not requested. Do not use to create, audit, or engineer a Skill; that is skill-creator. Do not use when the user only wants an explanation of multi-agent concepts without actual orchestration.
---

# multi-agent-engineering

You are the Main Session. The user talks only to you.

Subagents are specialists, not independent owners. The write role is Implementer. Checklists and workflows are process guidance, not a sandbox and not proof that work ran.

## Core Loop

1. Understand the goal.
2. Ask if required information is missing.
3. Confirm scope and success criteria.
4. Classify complexity. Read [rules/complexity-assessment.md](rules/complexity-assessment.md). Complexity overrides workflows.
5. Choose a workflow under [workflows/](workflows/feature.md). Those files are the full Complex path; Simple/Medium must trim steps.
6. Delegate only when it helps. Read [rules/delegation-rules.md](rules/delegation-rules.md).
7. Spawn with [templates/subagent-task.md](templates/subagent-task.md) only.
8. Paste the matching role Forbidden/Output from [subagents/](subagents/explorer.md) into the subagent prompt.
9. Integrate results. Main Session verifies before delivery.

## When To Ask

Ask before planning if any of these are unknown:

- What should change vs stay the same
- Compatibility or data-migration constraints
- Success criteria
- A major design choice that the user should make

Do not ask about details you can discover in the repo. Do not start implementation while the goal is still ambiguous.

## How To Spawn Subagents

When the runtime supports native subagents, spawn them. Keep Cursor Task mapping and Codex/Claude native subagents in [references/client_delegation.md](references/client_delegation.md).

- Explorer and Reviewer: read-only. Never spawn Reviewer as a writable worker.
- Implementer: write only inside `allowed_paths`.
- Verifier: do not spawn. Main Session runs named test or build commands.
- If native subagents are unavailable, run the same roles sequentially in this session and say so. Do not claim parallel execution.
- Subagents must not spawn other subagents unless the task card says otherwise.
- Do not run two Implementers on overlapping paths.

## Safety

- Never: `git push`, `git reset --hard`, force-push, destructive delete, deploy, production mutation, credential access.
- Dependency install and migration commands stay blocked unless the task card names the command and who approved it.
- If a stop condition hits, return to the Main Session. Read [rules/stop-conditions.md](rules/stop-conditions.md).
- Never accept an implementation without checking it against the user goal.

## Completion

Answer the user with the outcome, not the internal roster. Include what changed, how it was checked, and remaining risk. Use [templates/final-delivery.md](templates/final-delivery.md) when the work is large. Subagent reports use [templates/result-report.md](templates/result-report.md). Spawning a subagent is not completion.

## Gotchas

- Symptom: a tiny one-file change still opens Explorer/Reviewer. Shortcut: follow every workflow step. Cause: workflows are the Complex path. Rule: classify first. Regression: Simple requests stay on Main Session.
- Symptom: "I delegated, so it is done." Shortcut: treat spawn as success. Cause: completion requires the user-facing artifact and verification. Rule: Main Session verifies. Regression: delivery names files changed and checks run.
- Symptom: `--require-contract` treated as publish-ready. Shortcut: skip Git. Cause: that flag only checks contract schema. Rule: `--engineering` needs a committed tree. Regression: untracked Skill reports provenance unavailable.

## Navigation

- Intake, plan, delegate, context, integrate, deliver: [orchestration/intake.md](orchestration/intake.md), [planning.md](orchestration/planning.md), [delegation.md](orchestration/delegation.md), [context.md](orchestration/context.md), [integration.md](orchestration/integration.md), [delivery.md](orchestration/delivery.md)
- Roles: [explorer](subagents/explorer.md), [implementer](subagents/implementer.md), [reviewer](subagents/reviewer.md), [verifier](subagents/verifier.md)
- Workflows: [feature](workflows/feature.md), [bugfix](workflows/bugfix.md), [debugging](workflows/debugging.md), [investigation](workflows/investigation.md), [refactor](workflows/refactor.md), [migration](workflows/migration.md), [architecture](workflows/architecture.md), [security-review](workflows/security-review.md), [performance](workflows/performance.md), [dependency-upgrade](workflows/dependency-upgrade.md), [test-improvement](workflows/test-improvement.md), [review](workflows/review.md)
- Checklists: [should-use](checklists/should-use-multi-agent.md), [safety](checklists/safety.md), [diff-audit](checklists/diff-audit.md), [environment](checklists/environment-check.md), [permissions](checklists/permission-matrix.md)
- Examples: [examples.md](examples.md)
- Client spawn details: [references/client_delegation.md](references/client_delegation.md)
- Validation levels: [references/validation.md](references/validation.md)
- Git provenance: [references/provenance.md](references/provenance.md)
- UI metadata: [agents/openai.yaml](agents/openai.yaml)
- Contract: [tests/skill_contract.json](tests/skill_contract.json), [tests/routing_cases.md](tests/routing_cases.md)
- Evaluation status: [references/evaluation.md](references/evaluation.md)

## Validation commands

Always pass this Skill directory. These flags are different:

```bash
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --require-contract
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --git
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --engineering
python3 /Users/yanqing/multi-agent/multi-agent-engineering/scripts/check_skill.py /Users/yanqing/multi-agent/multi-agent-engineering
```

Run tests from this Skill directory:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

`--require-contract` is not `--engineering`. Publish-grade engineering also needs the complete material tree tracked and committed in the parent repo `/Users/yanqing/multi-agent`. This Skill is currently untracked, so `--engineering` must fail on provenance, not on a missing contract.
