# Routing Regression Matrix

Use these prompts as manual routing checks after changing `SKILL.md` frontmatter.

## Normal positive

- Use multiple subagents to refactor the payment module while keeping the public API stable.
- Act as the lead agent: plan first, then delegate an explorer, implementer, and reviewer for this feature.
- Checkout hangs sometimes. Investigate with subagents and integrate the findings before any patch.

## Nonstandard positive

- Spin up parallel workers to migrate this service and have someone review the risk.
- I only want to talk to one lead. Have specialists review auth for security issues.

## Negative

- Write a helper that title-cases a string. Do not use extra agents.
- Just explain what multi-agent means. Do not actually open subagents.

## Adjacent-skill confusion

- Engineer this Skill to the skill-creator standard and add contract tests.
- Fix the failing unit test in tests/test_foo.py.

## Validator CLI boundaries

- `python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering` checks static structure.
- `python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --require-contract` requires `tests/skill_contract.json` and does not claim publish readiness.
- `python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --git --json` reports provenance; untracked files are `source_provenance: unavailable`.
- `python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --engineering` is the publish gate and must fail while this Skill is untracked.
- `python3 /Users/yanqing/multi-agent/multi-agent-engineering/scripts/check_skill.py /Users/yanqing/multi-agent/multi-agent-engineering` is the local file/link check.

## Release-safety checks

- Do not treat workflows or checklists as proof of execution.
- Do not `git init` a nested repository.
- Do not invent a commit hash to make `--engineering` pass.
