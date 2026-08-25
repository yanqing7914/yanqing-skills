# Routing Regression Matrix

Use these prompts as manual routing checks after changing `SKILL.md` frontmatter.

## Normal positive

- Create a new Codex Skill for handling our API workflow.
- Audit this existing Skill and split its long `SKILL.md` into references.
- Turn this Skill's repeated failure into a regression test and improve its trigger description.

## Nonstandard positive

- Productize this prompt workflow as a reusable Codex capability.
- Add scripts, assets, and metadata to standardize this Skill.

## Negative

- Use the existing PDF Skill to merge these files.
- Query today's Lark approval tasks.

## Adjacent-skill confusion

- Create a Codex plugin with its manifest and package structure.
- Coordinate several agents to implement this repository change.

## Validator CLI boundaries

- `python3 scripts/quick_validate.py <skill-dir>` checks static structure and may pass without Git provenance.
- `python3 scripts/quick_validate.py <skill-dir> --require-contract` additionally requires `tests/skill_contract.json` but does not claim publish readiness.
- `python3 scripts/quick_validate.py <skill-dir> --git --json` is a provenance probe; outside Git it exits nonzero with `status: not_versioned` and no invented commit.
- `python3 scripts/quick_validate.py <skill-dir> --engineering` is the publish gate; outside Git it exits nonzero and reports unavailable provenance.
- `--git` cannot be combined with `--engineering` or `--require-contract`; `--json` requires `--git`.

## Release-safety checks

- Recording holdout evidence leaves the active Skill unchanged.
- A split whose prompt, fixture, or expected payload differs from the immutable source is rejected even when IDs and byte descriptors are rewritten.
- Selection staging rejects symlinked state directories and never writes reports outside the requested state root.
- `skill_gate.py adopt` is explicit, creates a backup, and is the only operation that replaces the active Skill; an interrupted replacement requires recovery inspection before retrying.
