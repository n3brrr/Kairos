---
name: new-adr
description: Create an architecture decision record in docs/adr/. Use when a decision changes architecture, tooling, workflow or a golden rule, or when a new decision supersedes an old one.
---

# New ADR

1. **Number.** List `docs/adr/` and take the next free number, zero-padded to four digits (`0007-…`). Never reuse or renumber.
2. **File name.** `docs/adr/NNNN-short-kebab-title.md`, in English.
3. **Template.**

```markdown
# ADR-NNNN: <Decision as a short sentence>

- **Status:** proposed | accepted | superseded by ADR-MMMM
- **Date:** YYYY-MM-DD

## Context
Why a decision is needed: the forces and constraints.

## Decision
What we decided, stated plainly.

## Consequences
What gets easier, what gets harder, what we must now do.
```

4. **Never edit an accepted ADR.** To change a decision, write a new ADR that says `Supersedes ADR-NNNN`, then change only the old ADR's `Status` line to `superseded by ADR-MMMM`. Nothing else in the old file changes.
5. Link the ADR from the doc it affects (spec, `CLAUDE.md`), and update `docs/README.md` if it indexes ADRs.
6. If the decision comes from a spike or a measurement, record the real results, not the expectation.
