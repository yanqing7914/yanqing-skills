# Git Provenance

## Navigation

- [Current state](#current-state)
- [Release rule](#release-rule)
- [What not to do](#what-not-to-do)

## Current state

This Skill lives under the parent repository `/Users/yanqing/multi-agent`.
It is not a nested Git repository.

`git ls-files -- multi-agent-engineering` is empty until someone tracks the tree.
`--git` therefore reports `source_provenance: unavailable` with untracked material files.

## Release rule

Publish-grade `--engineering` requires the complete material tree to be tracked and committed in that parent repo, then clean.

This task does not `git add`, commit, or push.

## What not to do

- Do not `git init` a nested repository inside this Skill.
- Do not invent a commit hash.
- Do not `git reset --hard`, force-push, or checkout to hide dirtiness.
- Do not claim the Skill is Git-versioned while files remain untracked.
