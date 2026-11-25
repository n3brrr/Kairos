# Kairos documentation

This folder is the **project's memory**: what to read to resume work without relying on a chat history.

| File | Purpose | How it is maintained |
|---|---|---|
| [`STATUS.md`](STATUS.md) | Where we are, what comes next, what blocks. **Read first.** | **Rewritten** when closing each block of work. |
| [`ROADMAP.md`](ROADMAP.md) | Project stages and their status. | Updated when stages are completed or moved. |
| [`FEATURES.md`](FEATURES.md) | Improvement ideas and the log of review passes. | **Append-only**; ideas change status, they are never deleted. |
| [`GLOSSARY.md`](GLOSSARY.md) | Domain vocabulary (with a Spanish column for the owner's chat). | Extended when a new term appears. |
| [`bootstrap-tasks.md`](bootstrap-tasks.md) | Tasks until Kairos can track them itself. | Migrated into Kairos in stage 1, then kept as history. |
| [`adr/`](adr/) | Architecture decisions and their reasons. | One ADR per decision. Accepted ones are not edited; they are superseded. |
| [`superpowers/specs/`](superpowers/specs/) | Approved designs (output of brainstorming). | One per large feature. |
| [`superpowers/plans/`](superpowers/plans/) | Implementation plans (output of writing-plans). | One per spec. |

## Rules

- A fact lives in **one place**; everything else links to it.
- If the code changes something a doc describes, the doc is updated **in the same PR**.
- Everything in the repo is written in English. Spanish is only for chatting with the owner.
