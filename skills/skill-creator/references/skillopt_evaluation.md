# Skill Evaluation and Gate Protocol

## Navigation

- [When to use the protocol](#when-to-use-the-protocol)
- [Dataset layout](#dataset-layout)
- [Result artifact contract](#result-artifact-contract)
- [Candidate lifecycle](#candidate-lifecycle)
- [Gate semantics](#gate-semantics)
- [Safety and privacy](#safety-and-privacy)

Use this protocol only when a Skill handles recurring work with a credible,
repeatable outcome signal. It adapts the useful parts of SkillOpt without
pretending that every natural-language task has an objective score.

## When to use the protocol

Use it when all of these are true:

- The Skill has recurring, representative tasks.
- Each task can produce a numeric score where higher is better, or a reliable
  pass/fail assertion that can be converted to `0` or `1`.
- The evaluator runs equivalently for the current and candidate Skill.
- The team can keep a held-out holdout set away from editing decisions.

Do not use automated gating for open-ended writing, subjective design, sparse
one-off work, or tasks whose evaluator rewards the wrong behavior. Use a
reviewable human rubric and forward test instead.

## Dataset layout

Create an `evals/` directory beside the target Skill:

```text
evals/
├── train.jsonl       # Learn failure patterns and propose candidates.
├── selection.jsonl   # Accept or reject candidates; never mine edits from it.
├── holdout.jsonl     # Final release evidence only; never use while editing.
├── test.jsonl        # Backward-compatible alias; never a fourth split.
└── manifest.json     # Immutable split IDs/payloads, source checksum, and evaluator contract.
```

Each JSONL record must have a stable `id`; preserve the prompt, fixture or
input reference, expected outcome, and risk label needed by the evaluator.
Use `python3 scripts/split_skill_cases.py <cases.jsonl> <eval-dir>` to make
deterministic splits from one source file. The gate checks each split record's
full JSON payload against the source record with the same ID; changing a prompt,
fixture, expected outcome, or risk field is invalid even if split hashes are
rewritten. `test.jsonl` is only a byte-identical
compatibility alias for `holdout.jsonl`; it is not an independent split. Do not
move a failure from `selection` or `holdout` into `train` merely to make a
candidate pass.

## Result artifact contract

The evaluator writes one JSON object for a split:

```json
{
  "schema_version": 1,
  "split": "selection",
  "manifest_sha256": "<sha256 of manifest.json bytes>",
  "skill_fingerprint": "<sha256 of evaluated complete Skill tree>",
  "evaluator": {"name": "example-evaluator", "version": "1"},
  "results": [
    {"id": "case-001", "score": 1.0, "evidence": "logs/case-001.txt"},
    {"id": "case-002", "score": 0.0, "evidence": "logs/case-002.txt"}
  ]
}
```

Rules:

- Compare the same task IDs for the current and candidate Skill.
- Scores must be finite numbers and use the same higher-is-better metric.
- Keep evidence paths or concise raw outputs for disputed scores.
- Bind an artifact to the exact manifest, evaluator version, and complete Skill
  tree it evaluated. The gate refuses missing or mismatched provenance.
- Treat manifest, split, evaluator, result, and state paths as immutable local
  inputs; symlinked files or staging boundaries are rejected to prevent writes
  outside the requested evaluation directory.
- Mark the result `split` truthfully. The selection gate refuses non-selection
  results; held-out results have a separate release-only command.

## Candidate lifecycle

1. Record the current Skill's baseline on `selection`.
2. Use **only `train` trajectories** to identify a root cause and propose a
   bounded edit. Default edit budget: one to three related changes.
3. Run static validation, scripts, and the candidate evaluator.
4. Run `skill_gate.py` on the two `selection` result artifacts.
5. If rejected, retain the report and rejection reason; do not overwrite the
   active Skill.
6. If accepted, stage the *complete candidate directory* for review. The gate
   retains the highest accepted directory under `.skill-evals/best/skill`.
7. Before release, run the selected best candidate exactly once on `holdout`
   and record it separately. Held-out evidence never changes the selected best
   candidate or becomes edit feedback.

`selection` decides whether to accept a candidate. `holdout` estimates whether the
accepted process generalizes. A test result never retroactively becomes training
data without starting a new, explicitly documented evaluation cycle.

## Gate semantics

Run:

```bash
python3 scripts/skill_gate.py \
  --manifest evals/manifest.json \
  --current-results evals/results/current-selection.json \
  --candidate-results evals/results/candidate-selection.json \
  --current-skill active-skill/ \
  --candidate-skill candidate-skill/ \
  --state-dir .skill-evals
```

The candidate is accepted only when its mean selection score is **strictly**
higher than the current score. Per-case non-regression is the default; use
`--allow-regression` only when an approved trade-off permits it. A passing
candidate is copied as a timestamped full-tree snapshot; it never replaces the
active Skill. The script exits `0` for acceptance, `1` for a valid rejection,
and `2` for invalid, incomplete, or incomparable evidence.

Record release evidence only after selection acceptance:

```bash
python3 scripts/skill_gate.py holdout \
  --manifest evals/manifest.json \
  --candidate-skill .skill-evals/runs/<run>/candidate \
  --results evals/results/candidate-holdout.json \
  --state-dir .skill-evals \
  --run-dir .skill-evals/runs/<run>
```

The holdout command fails if the run was not accepted, the evaluated tree,
manifest, evaluator, selection report, or split differs, or release evidence
was already recorded. It deliberately does not update `best` or the active
Skill.

After reviewing the staged tree and its one-time holdout evidence, explicitly
promote it while retaining the prior active Skill as a backup:

```bash
python3 scripts/skill_gate.py adopt \
  --state-dir .skill-evals \
  --run-dir .skill-evals/runs/<run> \
  --target-skill active-skill/
```

`adopt` refuses runs without matching acceptance and holdout evidence. It
copies the complete staged tree, verifies the fingerprint again, moves the
previous active directory into `.skill-evals/backups/`, and then performs a
guarded two-step replacement with rollback on operation errors. If the process
is interrupted, inspect the backup and target paths before retrying. Optimization
itself never invokes this command implicitly.

Use `--dry-run` to inspect a decision without writing state. The script exits
`0` for acceptance, `1` for a valid rejection, and `2` for invalid or
incomparable evidence.

## Safety and privacy

- Do not send historical sessions, logs, task fixtures, or outputs to a remote
  optimizer without explicit authorization and a redaction review.
- Keep production mutations out of candidate evaluation unless an approved
  sandbox, fixture, or rollback exists.
- Keep evaluator changes versioned with the task set. A changed evaluator means
  prior scores are not directly comparable.
- Treat score movement smaller than the measurement noise as inconclusive; add
  more representative selection tasks rather than accepting a fragile change.
