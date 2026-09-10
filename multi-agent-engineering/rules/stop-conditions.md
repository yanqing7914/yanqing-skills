# Stop Conditions

Subagents must stop and return control to the Main Session when:

- The task requires work outside the assigned scope or allowed paths.
- Requirements are ambiguous.
- A forbidden path or secret value may be involved.
- A blocked command is needed and the task card does not authorize it.
- A destructive operation is required.
- Validation fails for unclear reasons or cannot be completed.
- Tests fail for unclear or unrelated reasons.
- User changes may be overwritten.
- A major design decision is required.

The Main Session decides whether to continue, adjust scope, or ask the user.
