# Skill Creator

`skill-creator` helps create, audit, standardize, test, and release Codex Skills.

It includes:

- `SKILL.md`: routing boundaries and the engineering workflow;
- `scripts/`: static validation, initialization, metadata generation, deterministic evaluation splits, and the selection/holdout/adopt gate;
- `references/`: detailed engineering and SkillOpt protocol guidance;
- `tests/`: routing, behavior, completion, and regression evidence.

Start with the read-only inventory workflow in `SKILL.md`. For a completed Skill,
run the static, contract, Git, and engineering validation commands documented there.
The bundled evaluation scaffold is opt-in; no optimization result is implied
without an independent evaluator and provenance-bound artifacts.
