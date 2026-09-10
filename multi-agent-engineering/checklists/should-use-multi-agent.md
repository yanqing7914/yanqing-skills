# Should Use Multi-Agent Checklist

Use multi-agent-engineering when one or more are true:

- User explicitly asks for multiple agents, subagents, parallel workers, reviewers, or agent collaboration.
- Task spans multiple independent modules or layers.
- Task needs separate research, implementation, review, and verification passes.
- Codebase is large enough that parallel exploration reduces risk.
- User asks for multi-perspective review, security review, architecture review, or deep investigation.
- Risk is high enough to justify independent review.

Prefer Quick Path when:

- Single-file or obvious small change.
- Bug root cause is already known.
- Work has no safe ownership split.
- Requirements are unclear and need user clarification first.
- Multiple Implementers would modify the same files. Split paths or run them in sequence.
- Coordination cost is higher than execution cost.

Decision (complexity overrides workflows; workflow files are the full Complex path):

- Small task: Main Session directly handles the work.
- Medium task: Main Session with Explorer and Implementer.
- Large task: Main Session with Explorer, Implementer, Reviewer, and Verifier.
