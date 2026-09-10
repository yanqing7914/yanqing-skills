# Delegation Rules

The Main Session decides whether to use subagents.

Complexity classification overrides workflow files. Workflows describe the full Complex path; Simple/Medium must trim steps.

## Delegate when

- The task requires repository exploration.
- Multiple independent areas need work.
- Independent review is valuable.
- Verification requires separate validation.

## Do not delegate when

- The change is small.
- The solution is already clear.
- Delegation costs more than execution.

## Role write rules

- Explorer, Reviewer, Verifier: never write. Paste Forbidden/Output from the role file into the spawn prompt.
- Reviewer: `explore` only. If `explore` is unavailable, Main Session reviews.
- Verifier: do not spawn. Main Session runs named test/build commands.
- Implementer: write only inside `allowed_paths`.
- Never spawn two Implementers whose allowed paths overlap. Split paths or run them in sequence.

## Retry

If a subagent is blocked or returns a conflict, Main Session may re-delegate at most twice. Then stop and ask the user.

The Main Session remains responsible for final decisions.
