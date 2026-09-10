# Result Integration

The Main Session owns final integration of subagent results.

## Process

1. Collect structured reports (`templates/result-report.md`).
2. Compare results with the original goal.
3. Confirm Implementer changes stayed in `allowed_paths`. Read `checklists/diff-audit.md`.
4. Resolve conflicts. Re-delegate at most twice, then ask the user.
5. Main Session runs verification. Do not spawn a writable Verifier.
6. Do not accept changes without checking them against the user goal.

## Integration Checklist

- Goal satisfied
- Scope respected
- Risks understood
- Validation completed
