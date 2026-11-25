# Glossary

The UI and the code use the same English term. The Spanish column only maps the owner's chat vocabulary to it. If a new concept appears, add it here before naming it in code.

| Term (UI and code) | Spanish (chat) | Meaning |
|---|---|---|
| Project (`Project`) | Proyecto | Highest-level container. States: active, queued, paused, archived. Has an **area** (Personal, Development…). |
| Epic (`Epic`, kind of `Item`) | Épica | Groups tasks of the same goal inside a project. |
| Task (`Task`, kind of `Item`) | Tarea | Unit of work assignable to a human or an agent. |
| Subtask (`Subtask`, kind of `Item`) | Subtarea | Step of a task; not assigned separately. |
| Task type (`TaskType`) | Tipo de tarea | Defines the required fields and the criteria template (bug, feature, chore…). |
| Status (`Status`) | Estado | Proposal, Backlog, Ready, In progress, In review, Done, Cancelled. |
| Blocked (`is_blocked`, derived) | Bloqueada | Has open dependencies. Not a stored status. |
| Transition (`Transition`) | Transición | A permitted status change, with who may perform it. |
| Gate (`Gate`) | Candado | Automatic condition that must hold for a transition. |
| Gate override (`GateOverride`) | Forzar candado | The owner skips a gate giving a reason; it is recorded in the history. |
| Acceptance criterion (`AcceptanceCriterion`) | Criterio de aceptación | Verifiable "done" condition. |
| Evidence (`Evidence`) | Evidencia | Proof attached to a criterion: text, link or command output. |
| Dependency (`Dependency`) | Dependencia | "This task blocks that one." No cycles. |
| Actor (`Actor`) | Actor | Who performs an action: human, agent, orchestrator or system. |
| Agent (`Agent`) | Agente | A Claude Code session with identity, specialty, scope and token. |
| Orchestrator (`Orchestrator`) | Orquestador | Agent with an extended role: assigns and triages, but does not approve. |
| Subagent (`Subagent`) | Subagente | An agent's helper inside its session, for large tasks. No permissions of its own; recorded only as attribution (`via`). |
| Proposal (status `proposed`) | Propuesta | A task created by an agent, waiting for triage. |
| Approval request (`ApprovalRequest`) | Solicitud de aprobación | A PR-like request with description and reason. The human decides it. |
| Assignment (`Assignment`) | Asignación | Task ↔ agent relation. An agent has one in-progress task. |
| History (`events` log) | Historial | Immutable, append-only record of every change. |
| Single door | Puerta única | Every entry point goes through the same use cases with an `Actor`. |
| Review pass | Pasada | A round of improvement proposals; see `FEATURES.md`. |
| Dogfooding | Dogfooding | Kairos manages its own development. |
| Runner | Runner | Host process that launches Claude Code agents (stage 4). |
