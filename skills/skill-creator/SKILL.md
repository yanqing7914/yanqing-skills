---
name: skill-creator
description: Create, audit, standardize, test, and iteratively improve Codex Skills. Use when a user wants to build or update a Skill, clarify its routing boundary, split SKILL.md into scripts/references/assets, turn failures into regression cases, or establish reproducible validation and forward-testing. Do not use for executing an existing domain Skill, building a general software project, or creating a Codex plugin.
metadata:
  short-description: Create or update a skill
---

# Skill Creator

Use this Skill to turn a Skill idea or an existing Skill into a bounded,
reviewable, testable artifact. Preserve validated behavior and user changes.

## Operating contract

- Start existing-Skill work with a read-only inventory. Record findings before editing.
- Keep routing in frontmatter; keep core behavior here; put conditional detail in `references/`; deterministic work in `scripts/`; output templates in `assets/`.
- Treat every observed failure as a regression candidate. Do not hide tool, permission, or configuration failures in prompt wording.
- Never claim that a Skill is stable, engineered, optimized, or distributable without the corresponding validator and evidence.
- Do not fabricate scores. A SkillOpt result is valid only when its split, evaluator, complete-tree fingerprint, and evidence are bound together.
- Stage accepted candidates. Never silently replace an active Skill; only an explicit, reviewed `adopt` operation may do that, with a backup.
- Do not initialize Git, commit, adopt, or change a production Skill automatically.

## Scope and resource layout

Route here when the request is to create, audit, standardize, test, document,
or improve a Codex Skill. Do not route here for ordinary domain work, generic
repository changes, or plugin creation; use the relevant domain, coding, or
plugin Skill instead.

```text
skill-name/
├── SKILL.md                 # required trigger metadata and core workflow
├── agents/openai.yaml       # UI metadata (recommended)
├── scripts/                 # deterministic executable helpers (optional)
├── references/              # conditional knowledge and protocols (optional)
├── tests/                   # contract and regression evidence (recommended)
└── assets/                  # files copied into outputs (optional)
```

Read [skill_engineering_details.md](references/skill_engineering_details.md)
for the longer anatomy, freedom-level, progressive-disclosure, and
forward-testing guidance. Read [openai_yaml.md](references/openai_yaml.md)
before editing UI metadata.

## Engineering workflow

Follow the stages in order. If a stage is skipped, record why in the work
notes or final report.

### 1. Inventory (read-only)

Inspect and record:

- frontmatter name, description, positive triggers, exclusions, and adjacent-Skill boundaries;
- `agents/openai.yaml` and whether its display text/default prompt match the Skill;
- scripts, references, assets, tests, local links, executable entry points, and permissions;
- current tests, contract/routing matrix, optional `evals/` corpus, and missing evidence;
- source Git provenance using the `--git` command below.

Do not edit during inventory. Separate facts, risks, assumptions, and proposed
changes. For an existing Skill, preserve unrelated user changes.

### 2. Align scope and completion

Agree on the trigger boundary before writing instructions. Define:

- what requests should trigger the Skill;
- what requests must not trigger it;
- the smallest reusable workflow and resource split;
- success, invalid-input, tool/permission-failure, and repeated-run behavior;
- completion evidence that proves the final artifact or state, not merely that a command ran.

Use lowercase hyphen-case names (maximum 64 characters) and make the directory
name exactly match `SKILL.md` frontmatter `name`.

### 3. Initialize or edit

For a new Skill, ask for the destination and run the initializer. It creates a
draft; finish or remove every placeholder before validation. It never runs
`git init` or creates a commit.

```bash
python3 scripts/init_skill.py <skill-name> --path <output-directory> \
  [--resources scripts,references,assets] [--examples] [--evals]
```

For an existing Skill, edit in place and preserve unrelated files. If
`--examples` was used, replace or delete example placeholders. If `--evals`
was used, treat `evals/EVALUATION.md` as an inactive scaffold until a real
corpus, evaluator, and provenance-bound results exist.

Generate or refresh UI metadata only after reading the Skill:

```bash
python3 scripts/generate_openai_yaml.py <path/to/skill-folder> \
  --interface key=value
```

### 4. Implement with progressive disclosure

Keep this file focused on decisions and the happy-path workflow. Move long
concept explanations, variant-specific instructions, forward-test details,
and evaluation protocol into directly linked references. Keep references one
level deep; a reference longer than 100 lines must begin with a table of
contents or clear section navigation.

Use low-freedom instructions or scripts for fragile operations, medium freedom
for repeatable patterns with parameters, and high freedom for judgment-heavy
work. Add a script only when it improves determinism or avoids repeated code.

### 5. Validate at the right level

Always pass the Skill directory explicitly. These commands are intentionally
different:

```bash
# Static structure, links, metadata, and optional inactive-eval checks.
python3 scripts/quick_validate.py <skill-dir>

# Contract/routing/behavior/completion schema; does not require Git or imply release readiness.
python3 scripts/quick_validate.py <skill-dir> --require-contract

# Source Git provenance only; useful for any Skill, including one without a contract.
python3 scripts/quick_validate.py <skill-dir> --git

# Publish-grade engineering gate: completed content, metadata, contract, tests,
# a committed complete material tree, and clean scoped Git provenance.
python3 scripts/quick_validate.py <skill-dir> --engineering
```

`--require-contract` is not `--engineering`: it checks the contract schema and
does not claim that the Skill is Git-versioned, tested in a release environment,
or ready for distribution. A missing repository or commit must be reported as
provenance unavailable; never invent a hash. Run changed scripts directly and
run the standard-library regression suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

### 6. Forward-test and iterate

Use isolated realistic tasks when complexity or risk warrants it. Give an
independent tester the Skill and a user-like request, not your diagnosis or
expected answer. Review raw outputs and artifacts, then convert real failures
to the smallest regression and rerun validation. Do not forward-test against
live production systems without approval and a rollback path.

### 7. Release review

Before calling a Skill engineered or distributable, verify:

- the three validation levels above have appropriate results;
- routing, behavior, and completion contract evidence is present;
- all local references resolve and no unsafe links/symlinks remain;
- scripts and tests actually execute with truthful results;
- Git provenance is committed and clean, or the report explicitly says it is unavailable;
- no real eval corpus means no optimization or quality conclusion.

## SkillOpt-style gate (only for scoreable recurring work)

Use this loop only when an independent, repeatable evaluator exists. For
subjective, one-off, or open-ended work, use a human rubric and forward tests;
do not create artificial scores.

1. Create stable cases and deterministic `train`, `selection`, and `holdout` splits.
2. Evaluate the active Skill on `selection` to establish a baseline.
3. Learn edits from `train` only; make a bounded candidate change (normally one to three related edits).
4. Evaluate both trees with the same evaluator and record manifest hash, evaluator version, tree fingerprint, IDs, scores, and evidence.
5. Run the selection gate. It requires a strict aggregate improvement and, by default, no per-case regression.
6. Stage the complete candidate tree. Rejected candidates never become active and staging does not mutate the active tree.
7. Run `holdout` once, after selection acceptance, only as release evidence. It cannot train or choose a candidate.
8. After human review, run `adopt` explicitly; it verifies evidence, preserves a backup, and performs a guarded replacement with rollback on operation errors. Treat an interrupted process as needing a backup/target recovery check before retrying.

Read [skillopt_evaluation.md](references/skillopt_evaluation.md) before using
the protocol. The executable interfaces are:

```bash
python3 scripts/split_skill_cases.py <cases.jsonl> <eval-dir>

python3 scripts/skill_gate.py \
  --manifest <eval-dir>/manifest.json \
  --current-results <eval-dir>/results/current-selection.json \
  --candidate-results <eval-dir>/results/candidate-selection.json \
  --current-skill <active-skill> \
  --candidate-skill <candidate-skill> \
  --state-dir <state-dir>

python3 scripts/skill_gate.py holdout \
  --manifest <eval-dir>/manifest.json \
  --candidate-skill <state-dir>/runs/<run>/candidate \
  --results <eval-dir>/results/candidate-holdout.json \
  --state-dir <state-dir> --run-dir <state-dir>/runs/<run>

python3 scripts/skill_gate.py adopt \
  --state-dir <state-dir> --run-dir <state-dir>/runs/<run> \
  --target-skill <active-skill>
```

The splitter requires all three non-empty splits and binds split bytes and
ordered IDs in `manifest.json`. Result artifacts must bind the manifest hash,
evaluator identity/version, complete Skill fingerprint, exact IDs, finite
scores, and non-empty evidence. The gate rejects equal scores, mismatched IDs,
manifest/evaluator/fingerprint changes, tampered candidates, and repeated
holdout records. See the reference for artifact fields and privacy rules.

## Contract and regression minimum

Maintain `tests/skill_contract.json` and, when useful for manual review,
`tests/routing_cases.md`. The routing matrix must contain at least three normal
positive, two nonstandard positive, two negative, and two adjacent-Skill cases.
Behavior cases must cover success, invalid input, tool/permission failure, and
idempotence. Completion evidence must identify an artifact or authoritative
verification result and its assertions.

Each retained Gotcha should state the failure symptom, tempting shortcut, root
cause, replacement rule, and regression assertion. Test final state and
authoritative evidence; do not count an accepted request as a completed result.

## Safety and Gotchas

- Preserve user edits and permissions; inspect before changing or deleting anything.
- Reject path traversal, broken local links, symlinks, malformed metadata, and placeholder drafts at the relevant validation level.
- Treat evaluation case payloads as immutable source evidence; matching IDs alone are not enough, and staging/report paths must not be symlink boundaries.
- Keep evaluator cases and outputs redacted and local unless the user explicitly authorizes sharing.
- Never let holdout results influence edits, selection, or the active Skill.
- Never treat an inactive `evals/` scaffold or a manual score as proof of optimization.
- A clean Git check is scoped to the Skill's material tree; a missing Git repo, missing HEAD, untracked material file, ignored material file, or modified file is a release blocker.

## Resource navigation and commands

- UI metadata: [references/openai_yaml.md](references/openai_yaml.md)
- Detailed anatomy, progressive disclosure, and forward-testing: [references/skill_engineering_details.md](references/skill_engineering_details.md)
- SkillOpt split/result/gate protocol: [references/skillopt_evaluation.md](references/skillopt_evaluation.md)
- Static, contract, Git, and engineering validation: `scripts/quick_validate.py`
- New Skill scaffold: `scripts/init_skill.py`
- UI metadata generation: `scripts/generate_openai_yaml.py`
- Deterministic split: `scripts/split_skill_cases.py`
- Selection/holdout/adopt lifecycle: `scripts/skill_gate.py`
- Contract and regression tests: `tests/test_skill_creator.py`, `tests/skill_contract.json`, `tests/routing_cases.md`

When handing off, report modified files, validation commands and results,
SKILL.md line count, whether an eval corpus is active, whether independent
selection/holdout evidence exists, Git provenance status, and remaining risks.
