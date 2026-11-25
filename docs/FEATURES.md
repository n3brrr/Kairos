# Ideas de mejora y «pasadas»

Este archivo guarda lo que **podría** añadirse a Kairos. Nada de aquí se implementa sin aprobación del usuario.

## Cómo se hace una pasada

Una *pasada* es una ronda corta y periódica (por ejemplo, al terminar cada etapa) para proponer mejoras.

1. Leer `STATUS.md`, el spec vigente y lo que ya existe en el producto.
2. Mirar el producto funcionando, no solo el código: ¿qué fricción hay al usarlo con agentes?
3. Añadir ideas nuevas a la tabla con un ID `IDEA-nn` siguiente, valor, coste y etapa sugerida. No duplicar: buscar antes.
4. Registrar la pasada en el log de abajo.
5. El usuario decide por idea: **aceptada** (pasa a una tarea de Kairos), **pospuesta** o **descartada** (con motivo breve). Las ideas no se borran.

Escalas: valor y coste en `B` (bajo), `M` (medio), `A` (alto).

## Ideas

| ID | Idea | Valor | Coste | Etapa sugerida | Estado |
|---|---|---|---|---|---|
| IDEA-01 | Plantillas de tarea por tipo, con criterios de aceptación precargados | A | B | 1 | propuesta |
| IDEA-02 | Vista «Hoy / Esta semana» para enfocar entre las ~200 tareas activas | A | M | 2 | propuesta |
| IDEA-03 | Búsqueda global y filtros guardados (SQLite FTS5) | A | M | 2 | propuesta |
| IDEA-04 | Paleta de comandos (`Ctrl+K`) y atajos de teclado en el tablero | M | B | 2 | propuesta |
| IDEA-05 | Aprobación en lote con teclado («modo revisión rápida») | A | B | 2 | propuesta |
| IDEA-06 | Detección de tareas estancadas (en curso sin eventos durante N días) | A | B | 2 | propuesta |
| IDEA-07 | Enlace tarea ↔ rama/PR de GitHub mediante el ID `KAI-n` | M | M | 2 | propuesta |
| IDEA-08 | Notificaciones de escritorio cuando hay aprobaciones pendientes | M | B | 3 | propuesta |
| IDEA-09 | Estimación de consumo de cuota de Claude Pro por agente y tarea | M | M | 3 | propuesta |
| IDEA-10 | Métricas de calidad por agente: tasa de rechazo en revisión, tiempo hasta aprobación | M | B | 2 | propuesta |
| IDEA-11 | Rutinas personales recurrentes (revisión semanal, mantenimiento) como plantillas de automatización | M | B | 3 | propuesta |
| IDEA-12 | Backup programado a JSON/Markdown con restauración verificada | A | M | 4 | propuesta |
| IDEA-13 | Políticas por agente: límites de ediciones, de tiempo en curso, de tipos permitidos editables desde la UI | M | M | 3 | propuesta |
| IDEA-14 | Enlace al transcript o resumen de la sesión del agente desde cada tarea en revisión | M | M | 3 | propuesta |

## Log de pasadas

| Fecha | Quién | Qué se añadió |
|---|---|---|
| 2026-11-26 | Claude | Pasada inicial: IDEA-01 a IDEA-14, a partir de los requisitos del brainstorming. |
