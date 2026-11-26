---
paths:
  - "docs/**"
  - "CLAUDE.md"
---

# Documentation conventions

- Everything is English: docs, ADRs, specs, plans, `CLAUDE.md`. Only chat with the owner is Spanish. `docs/GLOSSARY.md` has a Spanish column only to map the owner's vocabulary.
- `docs/STATUS.md` is **rewritten, not appended**, when a block of work closes (use the `update-status` skill).
- Accepted ADRs are never edited: a new decision is a new ADR that supersedes the old one (use the `new-adr` skill).
- New ideas go in `docs/FEATURES.md`; they are not built without the owner's approval.
- If code changes something a doc describes, the doc changes in the same pull request.
- Do not invent commands: document only commands that exist and that you ran.
