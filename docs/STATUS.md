# Estado de Kairos

> **Leé esto primero.** Si se perdió el contexto, este archivo dice dónde estamos. Reescribilo (no lo apiles) al cerrar cada bloque de trabajo.

**Última actualización:** 2026-11-26 · **Fase:** Diseño (brainstorming con superpowers), a la espera de aprobación del spec.

## Dónde estamos

- Concepto, alcance y stack definidos con el usuario. El diseño vive en [`superpowers/specs/2026-11-26-kairos-design.md`](superpowers/specs/2026-11-26-kairos-design.md) (borrador en revisión).
- Remoto conectado: <https://github.com/n3brrr/Kairos> (público, MIT, `main` sin protección todavía).
- **No hay código de producto.** No se escribe hasta que el usuario apruebe el spec y exista un plan (`writing-plans`).

## Hecho

- Brainstorming: requisitos, límites del agente, orquestador, stack (backend Python + frontend React), flujo git trunk-based.
- Estructura de contexto del repo: `CLAUDE.md`, `docs/`, ADR 0001–0006, `.gitignore`, `.gitattributes`, `.editorconfig`.
- Spec de diseño redactado y revisado por un subagente («builder check»).

## Siguiente (en orden)

1. El usuario responde las preguntas que dejó la revisión del spec y lo aprueba.
2. Abrir el PR `docs/BOOT-001-project-context` (lo fusiona el usuario).
3. `writing-plans`: plan de la **etapa 0** (fundaciones + spike MCP) con tareas pequeñas.
4. Ejecutar el spike del token por agente (ADR-0005) antes de fijar la etapa 1.

## Pendiente del usuario

- Aprobar el spec y responder las preguntas abiertas del chat.
- Instalar `uv` (gestor de Python; no está instalado): `winget install astral-sh.uv`. Hace falta en la etapa 0.
- Cuando exista CI: importar el ruleset de `main` en GitHub (Settings → Rules → Rulesets → Import). Lo preparo yo.

## Riesgos abiertos

- **MCP + token por agente en Windows:** hay reportes de que Claude Code ignora la cabecera `Authorization` si el servidor anuncia OAuth, y de fallos con `.mcp.json` de proyecto en Windows. Se valida con el spike (ADR-0005).
- **¿Un subagente puede llevar su propio token o hereda el de la sesión?** Decide si «un agente» equivale a «una sesión de Claude Code».
- **Dos lenguajes:** el contrato entre backend y frontend depende de la generación de tipos desde OpenAPI (ADR-0001); hay que comprobar la deriva en CI.

## Cómo retomar

1. Leer este archivo, luego `CLAUDE.md`, luego el spec vigente.
2. `git status` y `git log --oneline -10` para ver el estado real.
3. Revisar `docs/bootstrap-tasks.md` para la siguiente tarea.
4. Al terminar el bloque: reescribir este archivo.
