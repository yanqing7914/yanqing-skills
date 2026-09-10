# Client Delegation

## Navigation

- [Cursor](#cursor)
- [Codex](#codex)
- [Claude](#claude)
- [Fallback](#fallback)

Keep role contracts from `subagents/` in the prompt. This file only maps spawn mechanics.

## Cursor

Use the Task tool when available.

| Role | `subagent_type` | Write |
| --- | --- | --- |
| Explorer | `explore` | Never |
| Implementer | `generalPurpose` | `allowed_paths` only |
| Reviewer | `explore` only | Never |
| Verifier | Do not spawn | Never |

Never spawn Reviewer or Verifier as writable `generalPurpose`. If `explore` is unavailable for Reviewer, Main Session reviews.

## Codex

Use Codex native subagents when the client exposes them. Give each subagent one `templates/subagent-task.md`. Explorer and Reviewer stay read-only. Implementer stays inside `allowed_paths`. Main Session runs verification.

## Claude

Use Claude native subagents or `.claude/agents` when present. Same role contracts. Do not invent a Task tool that the client does not have.

## Fallback

If there is no native subagent mechanism, run Explorer, Implementer, and Reviewer sequentially in the Main Session and say that execution is sequential, not parallel.
