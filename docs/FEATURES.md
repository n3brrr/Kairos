# Improvement ideas and review passes

This file holds what **could** be added to Kairos. Nothing here is built without the owner's approval.

## How a pass works

A *pass* is a short, periodic round (for example at the end of each stage) to propose improvements.

1. Read `STATUS.md`, the current spec and what already exists in the product.
2. Look at the running product, not only the code: what friction is there when using it with agents?
3. Add new ideas to the table with the next `IDEA-nn` ID, value, cost and suggested stage. Do not duplicate: search first.
4. Record the pass in the log below.
5. The owner decides per idea: **accepted** (becomes a Kairos task), **postponed** or **discarded** (with a short reason). Ideas are never deleted.

Value and cost scale: `L` (low), `M` (medium), `H` (high).

## Ideas

| ID | Idea | Value | Cost | Suggested stage | Status |
|---|---|---|---|---|---|
| IDEA-01 | Task templates per type, with pre-filled acceptance criteria | H | L | 1 | proposed |
| IDEA-02 | "Today / This week" view to focus among the ~200 active tasks | H | M | 2 | proposed |
| IDEA-03 | Global search and saved filters (SQLite FTS5) | H | M | 2 | proposed |
| IDEA-04 | Command palette (`Ctrl+K`) and keyboard shortcuts on the board | M | L | 2 | proposed |
| IDEA-05 | Keyboard-driven batch approval ("quick review mode") | H | L | 2 | proposed |
| IDEA-06 | Stalled-task detection (in progress with no events for N days) | H | L | 2 | proposed |
| IDEA-07 | Task ↔ GitHub branch/PR link through the `KAI-n` ID | M | M | 2 | proposed |
| IDEA-08 | Desktop notifications when approvals are pending | M | L | 3 | proposed |
| IDEA-09 | Estimated Claude Pro quota use per agent and task | M | M | 3 | proposed |
| IDEA-10 | Per-agent quality metrics: review rejection rate, time to approval | M | L | 2 | proposed |
| IDEA-11 | Recurring personal routines (weekly review, upkeep) as automation templates | M | L | 3 | proposed |
| IDEA-12 | Scheduled backup to JSON/Markdown with verified restore | H | M | 4 | proposed |
| IDEA-13 | Per-agent policies: edit limits, time-in-progress limits, allowed types editable from the UI | M | M | 3 | proposed |
| IDEA-14 | Link to the agent session transcript or summary from each task in review | M | M | 3 | proposed |
| IDEA-15 | Custom fields per task type (dynamic schema and type editor) | M | H | 3+ | postponed: fixed fields in stage 1 |
| IDEA-16 | Own identity per subagent (token with permissions bounded by the parent agent's) | M | M | after the spike | proposed, depends on ADR-0005 |

## Pass log

| Date | Who | What was added |
|---|---|---|
| 2026-11-26 | Claude | Initial pass: IDEA-01 to IDEA-14, from the brainstorming requirements. |
| 2026-11-26 | Claude | IDEA-15 and IDEA-16, from the answers about custom fields and subagents. |
