# Documentación de Kairos

Esta carpeta es la **memoria del proyecto**: lo que hay que leer para retomar el trabajo sin depender del historial de una conversación.

| Archivo | Para qué sirve | Cómo se mantiene |
|---|---|---|
| [`STATUS.md`](STATUS.md) | Dónde estamos, qué sigue, qué bloquea. **Se lee primero.** | Se **reescribe** al cerrar cada bloque de trabajo. |
| [`ROADMAP.md`](ROADMAP.md) | Etapas del proyecto y su estado. | Se actualiza al completar o mover etapas. |
| [`FEATURES.md`](FEATURES.md) | Ideas de mejora y registro de «pasadas». | Solo se **añade**; las ideas cambian de estado, no se borran. |
| [`GLOSSARY.md`](GLOSSARY.md) | Vocabulario del dominio (ES/EN). | Se amplía cuando aparece un término nuevo. |
| [`bootstrap-tasks.md`](bootstrap-tasks.md) | Tareas del proyecto hasta que Kairos pueda llevarlas él mismo. | Se migra a Kairos en la etapa 1 y queda como archivo histórico. |
| [`adr/`](adr/) | Decisiones de arquitectura y su porqué (en inglés). | Un ADR por decisión. Los aceptados no se editan; se reemplazan. |
| [`superpowers/specs/`](superpowers/specs/) | Diseños aprobados (salida del brainstorming). | Uno por funcionalidad grande. |
| [`superpowers/plans/`](superpowers/plans/) | Planes de implementación (salida de writing-plans). | Uno por spec. |

## Reglas

- Un dato vive en **un solo sitio**; el resto lo enlaza.
- Si el código cambia algo que un doc describe, el doc se actualiza **en el mismo PR**.
- Los docs de trabajo van en español; los ADR y el README raíz, en inglés.
