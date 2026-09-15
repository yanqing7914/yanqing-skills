# Anthropic Workflow Alignment

This note maps the upstream Anthropic `skill-creator` workflow to this Skill's
Codex implementation. It is guidance, not evidence that an evaluator or viewer
is installed.

## Workflow mapping

| Upstream emphasis | Codex implementation |
| --- | --- |
| Capture intent and interview | Inventory, scope alignment, trigger boundary, and completion contract in `SKILL.md` |
| Draft realistic test prompts | `tests/routing_cases.md`, contract cases, and optional `evals/evals.json` |
| Run with-skill and baseline | `scripts/run_eval.py` can run the same declared command against current and candidate trees; use an isolated old snapshot for baseline |
| Capture outputs and timing | `run_eval.py` writes per-case stdout, stderr, exit status, and duration; `aggregate_benchmark.py` summarizes process evidence only |
| Grade and compare | An independent evaluator must produce provenance-bound result artifacts consumed by `skill_gate.py`; process success is not a quality score |
| Iterate from failures | Convert observed failures into the smallest contract or regression case; edits must not use holdout data |
| Optimize description triggering | Review positive, negative, and adjacent prompts, make a bounded frontmatter edit, and rerun routing checks |
| Viewer / presentation | No viewer is bundled. Keep raw local artifacts and provide paths or a human-readable report when authorized |

## Honest limitations

- `evals/evals.json` created by the initializer is an inactive empty scaffold.
- `run_eval.py` requires each case to declare a safe argv-style `command`; it
  does not spawn model agents, grade outputs, or invent scores.
- A credible SkillOpt conclusion requires an independent evaluator, immutable
  train/selection/holdout splits, matching fingerprints, and accepted evidence.
- Description optimization is a routing experiment, not permission to broaden
  a Skill until it triggers on unrelated work.

## Suggested iteration record

For each iteration, retain the prompt set, old/candidate Skill fingerprints,
raw outputs, timing, reviewer notes, and the exact changed files. Do not publish
private prompts, fixtures, or outputs without redaction and authorization.
