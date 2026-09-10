# Evaluation

## Navigation

- [Status](#status)
- [Why this Skill is not scored](#why-this-skill-is-not-scored)
- [If a corpus is added later](#if-a-corpus-is-added-later)

## Status

There is no `evals/` corpus, no `manifest.json`, and no independent evaluator.
No quality or SkillOpt conclusion is available.

Do not invent scores. Do not treat this file as evaluation evidence.

## Why this Skill is not scored

Orchestration quality is judgment-heavy: whether to ask, whether to delegate,
and whether delivery matches the user goal. That is not a stable numeric
metric. Use the routing contract, unittest, and human forward tests instead.

## If a corpus is added later

Only then create `evals/manifest.json` plus disjoint `train.jsonl`,
`selection.jsonl`, and `holdout.jsonl`, bound to a trusted evaluator.
Until that exists, keep `evals/` absent so automation audits report
evaluation as not applicable rather than as a missing-manifest failure.
