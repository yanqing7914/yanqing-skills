# Skill Engineering Details

## Navigation

- [Anatomy](#anatomy)
- [Freedom and determinism](#freedom-and-determinism)
- [Progressive disclosure](#progressive-disclosure)
- [Forward-testing](#forward-testing)
- [Gotchas](#gotchas)

## Anatomy

A Skill is a self-contained directory. `SKILL.md` is required and contains
frontmatter plus the core workflow. `agents/openai.yaml` supplies optional UI
metadata. Put deterministic executable behavior in `scripts/`, conditional
knowledge in `references/`, fixed output material in `assets/`, and tracked
contracts/regressions in `tests/`. Avoid README-style process documentation or
duplicate instructions that do not help an agent execute the Skill.

Frontmatter is the routing surface: keep the name exact, the description
specific about triggers, and exclusions explicit. Body text is loaded after the
Skill triggers, so do not hide trigger conditions only in the body.

## Freedom and determinism

Choose instruction precision by risk:

- **High freedom:** prose guidance for judgment-heavy tasks with many valid approaches.
- **Medium freedom:** parameterized patterns or pseudocode for repeatable work.
- **Low freedom:** a script or exact command for fragile operations, permissions, or reproducibility.

Prefer a short deterministic helper over asking an agent to rewrite the same
logic repeatedly. Test new scripts by executing them, not only by reading them.

## Progressive disclosure

Keep the main file focused on routing, decisions, the normal workflow, safety
boundaries, and completion checks. Move variant-specific knowledge, long
explanations, schemas, examples, and forward-test protocol here or to another
directly linked reference. Keep references one level deep. Any reference over
100 lines should start with a table of contents or clear navigation.

When splitting content, preserve behavior and links. After a move, run the
validator against the Skill directory and inspect every local Markdown link.
Do not create README, CHANGELOG, QUICK_REFERENCE, or installation files merely
to explain the development process.

## Forward-testing

Forward-testing asks an independent agent to use the Skill on a realistic,
user-like task. Use a fresh context and provide only the Skill path and task;
do not leak the suspected defect, intended patch, or expected answer. Capture
raw output, diffs, logs, and produced artifacts. Review whether the result
meets the completion contract, then convert an observed failure into the
smallest regression case.

Use an isolated copy or fixture. Ask for approval before a test could be slow,
require new access, or touch live production systems. Remove temporary
artifacts between independent passes so later agents cannot infer the answer
from stale files. If a test passes only because the agent saw your diagnosis,
discard the evidence and repeat with a clean prompt.

## Gotchas

Retain a Gotcha only when it changes behavior. Record five parts:

1. Failure symptom.
2. Tempting wrong shortcut.
3. Root cause.
4. Required replacement rule.
5. Regression assertion that proves the fix.

Common Skill Creator gotchas include treating a successful API acknowledgement
as completed work, accepting a placeholder initializer as a finished Skill,
using `--require-contract` as if it proved release readiness, and treating a
manual or fabricated score as SkillOpt evidence.
