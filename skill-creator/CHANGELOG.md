# Changelog

## [0.4.0] - 2026-09-14

### Added

- New real-task eval runner: `scripts/run_eval.py`, keeps real prompts in `evals/evals.json`, captures stdout/stderr/exit status/timing against current and candidate trees, and never infers a quality score from process success.
- New transparent timing/process aggregator: `scripts/aggregate_benchmark.py`.
- New reference: `references/anthropic_alignment.md`, mapping the workflow to the upstream Anthropic Skill process and its Codex-specific limits.
- Routing-description optimization workflow: snapshot the previous tree, compare with-Skill vs baseline on realistic prompts, and treat description changes as hypotheses until routing tests confirm fewer false negatives without unacceptable false positives.
- Frontmatter `compatibility` field support in the validator.
- `init_skill.py --evals` now also scaffolds an empty inactive `evals/evals.json` case corpus.

### Changed

- Engineering publish gate now blocks recursive re-entry from a Skill's own test suite via the `SKILL_CREATOR_ENGINEERING_VERIFY` environment marker.
- Automation audit now reports optional SkillOpt evaluation evidence (manifest presence and evaluator trust) without treating absence as failure.

## [0.3.0] - 2026-09-07

### Added

- New read-only automation readiness audit: `scripts/audit_skill_automation.py`, with `ready` / `partial` / `not-ready` verdicts across deterministic entrypoints, contract, tests, failure handling, and Git provenance.
- `--run-tests` option to explicitly execute the Skill's declared or standard-library test command during the audit.
- SKILL.md section documenting when and how to audit another Skill's automation readiness.
- Regression tests covering both the `ready` and `partial`/`not-ready` audit paths.

## [0.2.0] - 2026-08-25

### Changed

- Synced `scripts/generate_openai_yaml.py`, `scripts/quick_validate.py`, `scripts/skill_gate.py`, and `scripts/split_skill_cases.py` from the upstream working copy.
- Synced regression tests in `tests/test_skill_creator.py` to match the updated tooling.

## [0.1.0] - 2026-08-25

### Added

- Initial engineered `skill-creator` Skill with validation, contract tests, Git provenance checks, and bounded SkillOpt-style selection/holdout/adopt tooling.
