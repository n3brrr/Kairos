# Glosario

La UI usa el término en español; el código usa el inglés. Si aparece un concepto nuevo, se añade aquí antes de nombrarlo en el código.

| Español (UI) | Inglés (código) | Significado |
|---|---|---|
| Proyecto | `Project` | Contenedor de más alto nivel. Estados: activo, en cola, pausado, archivado. Tiene un **área** (Personal, Desarrollo…). |
| Épica | `Epic` (kind de `Item`) | Agrupa tareas de un mismo objetivo dentro de un proyecto. |
| Tarea | `Task` (kind de `Item`) | Unidad de trabajo asignable a un humano o a un agente. |
| Subtarea | `Subtask` (kind de `Item`) | Parte de una tarea; no se asigna por separado. |
| Tipo de tarea | `TaskType` | Define los campos obligatorios y la plantilla de criterios (bug, feature, chore…). |
| Estado | `Status` | Propuesta, Backlog, Lista, En curso, En revisión, Hecha, Cancelada. |
| Bloqueada | `is_blocked` (derivado) | Tiene dependencias abiertas. No es un estado guardado. |
| Transición | `Transition` | Cambio de estado permitido, con quién puede hacerlo. |
| Candado | `Gate` | Condición automática que debe cumplirse para una transición. |
| Criterio de aceptación | `AcceptanceCriterion` | Condición verificable de «hecho». |
| Evidencia | `Evidence` | Prueba adjunta a un criterio: texto, enlace o salida de un comando. |
| Dependencia | `Dependency` | «Esta tarea bloquea a aquella». Sin ciclos. |
| Actor | `Actor` | Quien ejecuta una acción: humano, agente, orquestador o sistema. |
| Agente | `Agent` | Sesión de Claude Code con identidad, especialidad, alcance y token. |
| Orquestador | `Orchestrator` | Agente con rol ampliado: asigna y tría, pero no aprueba. |
| Subagente | `Subagent` | Ayudante de un agente dentro de su sesión, para tareas grandes. Sin permisos propios; se registra solo como atribución (`via`). |
| Propuesta | `Proposal` (estado `proposed`) | Tarea creada por un agente que espera triaje. |
| Solicitud de aprobación | `ApprovalRequest` | Petición con descripción y motivo, al estilo de un PR. La decide el humano. |
| Asignación | `Assignment` | Relación tarea ↔ agente. Un agente, una tarea activa. |
| Forzar candado | `GateOverride` | El usuario salta un candado indicando un motivo; queda en el historial. |
| Historial | `events` (log) | Registro inmutable, solo-anexar, de todo cambio. |
| Puerta única | single door | Toda entrada pasa por los mismos casos de uso con un `Actor`. |
| Pasada | review pass | Ronda de propuesta de mejoras; ver `FEATURES.md`. |
| Dogfooding | dogfooding | Kairos gestiona su propio desarrollo. |
| Runner | runner | Proceso en el host que lanza agentes de Claude Code (etapa 4). |
