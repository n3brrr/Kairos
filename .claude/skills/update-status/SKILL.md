---
name: update-status
description: Rewrite docs/STATUS.md when a block of work closes. Use at the end of any task or session, or when the Stop hook reminds you that STATUS.md is older than the code.
---

# Update `docs/STATUS.md`

`docs/STATUS.md` is the first file anyone reads after context is lost. **Rewrite it; never append to it.**

1. Read the current file and `git log --oneline -10`, `git status` and `gh pr list` so the facts are real, not remembered.
2. Rewrite these sections, keeping them short:
   - **Last updated** (today's date) and **Phase**.
   - **Where we are:** what exists in `main`, which branches and PRs are open, what is running.
   - **Next (in order):** the concrete next steps.
   - **Waiting on the owner:** merges, approvals and decisions only the owner can make.
   - **Open risks** and **How to resume** (the resume steps must still be true).
3. Remove what is no longer true. A stale line is worse than a missing one.
4. Update `docs/bootstrap-tasks.md` (statuses and criteria) and `docs/ROADMAP.md` if a stage moved.
5. Write in English. Do not claim anything works unless you ran its verification command in this session.
6. Commit the docs change with the code it describes, or as `docs: update status (<ID>)`.
