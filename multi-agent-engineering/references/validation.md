# Validation Levels

## Navigation

- [Static](#static)
- [Contract](#contract)
- [Git](#git)
- [Engineering](#engineering)
- [Local check](#local-check)

These commands are different. Always pass the Skill directory.

Creator scripts live in `/Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/`.
This Skill lives in `/Users/yanqing/multi-agent/multi-agent-engineering`.

## Static

```bash
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering
```

Checks metadata, local Markdown links, optional UI YAML, and contract schema if present. Does not prove Git provenance or publish readiness.

## Contract

```bash
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --require-contract
```

Requires `tests/skill_contract.json`. Does not imply `--engineering`.

## Git

```bash
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --git --json
```

Reports scoped provenance. Untracked files yield `source_provenance: unavailable`. Do not invent a commit hash.

## Engineering

```bash
python3 /Users/yanqing/Documents/Codex/skill-creator-work/skill-creator/scripts/quick_validate.py /Users/yanqing/multi-agent/multi-agent-engineering --engineering
```

Publish gate: contract, `agents/openai.yaml`, executable tests, and a committed clean material tree. Workflows and checklists are not this gate.

## Local check

```bash
python3 /Users/yanqing/multi-agent/multi-agent-engineering/scripts/check_skill.py /Users/yanqing/multi-agent/multi-agent-engineering
```

Confirms this Skill's required files and Markdown links. Repeatable. Does not claim Git provenance.
