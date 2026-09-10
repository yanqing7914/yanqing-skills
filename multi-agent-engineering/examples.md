# Examples

## Small change — no subagents

User: Change the submit button label to Save.

Main Session: edit the file directly. Do not spawn Explorer, Reviewer, or Verifier.

## Feature — full loop

User: Add invite-only signup.

1. Ask whether invites expire and whether existing users must stay compatible.
2. Spawn Explorer on auth and user models.
3. Review findings and write a plan.
4. Spawn Implementer with allowed paths.
5. Spawn Reviewer on the diff (`explore` only).
6. Main Session runs tests.
7. Deliver files changed, validation, and remaining risk.

## Bug — known failure

User: Login returns 500 when the password is wrong.

1. Spawn Explorer to find the error path.
2. Confirm the cause.
3. Spawn Implementer for the fix.
4. Main Session runs the regression test.

## Debugging — unknown cause

User: Checkout occasionally hangs.

1. Do not patch first.
2. Spawn Explorer for hypotheses.
3. Use Explorer or Main Session to reproduce or disprove. Do not use Verifier for hypothesis checks.
4. Spawn Implementer only after the cause is confirmed.
5. After a fix exists, Main Session validates. No extra writable subagent.
