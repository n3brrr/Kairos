# Estado de Kairos

> **Leé esto primero.** Si se perdió el contexto, este archivo dice dónde estamos. Reescribilo (no lo apiles) al cerrar cada bloque de trabajo.

**Última actualización:** 2026-11-26 · **Fase:** diseño cerrado; plan de la etapa 0 en redacción.

## Dónde estamos

- Concepto, alcance y stack definidos con el usuario y documentados en [`superpowers/specs/2026-11-26-kairos-design.md`](superpowers/specs/2026-11-26-kairos-design.md). La revisión del spec por un subagente dejó dos preguntas; el usuario las respondió (§17.1 del spec). No quedan preguntas abiertas.
- Remoto conectado: <https://github.com/n3brrr/Kairos> (público, MIT, `main` sin protección todavía).
- El PR `docs/BOOT-001-project-context` lleva este contexto a `main`; **lo fusiona el usuario** (squash).
- **No hay código de producto.** El siguiente paso es el plan de la etapa 0 (`writing-plans`).

## Hecho

- Brainstorming: requisitos, límites del agente, orquestador, stack (backend Python + frontend React), flujo git trunk-based.
- Contexto del repo: `CLAUDE.md`, `docs/`, ADR 0001–0006, `.gitignore`, `.gitattributes`, `.editorconfig`.
- Spec de diseño revisado por un subagente y cerrado con las respuestas del usuario.

## Siguiente (en orden)

1. El usuario revisa y fusiona el PR de BOOT-001.
2. Plan de la etapa 0 en `docs/superpowers/plans/` (BOOT-002).
3. Ejecutar la etapa 0: tooling, `check`, Docker, `.claude/`, CI. Después, el spike MCP (ADR-0005).

## Pendiente del usuario

- Fusionar el PR de BOOT-001 (squash).
- Cuando exista CI: importar el ruleset de `main` en GitHub (Settings → Rules → Rulesets → Import). Lo preparo yo.
- Si lo pide el plan: confirmar la instalación de `uv` (no está instalado).

## Riesgos abiertos

- **MCP + token por agente en Windows:** hay reportes de que Claude Code ignora la cabecera `Authorization` si el servidor anuncia OAuth, y de fallos con `.mcp.json` de proyecto en Windows. Se valida con el spike (ADR-0005).
- **¿Un subagente puede llevar su propio token o hereda el de la sesión?** Mientras tanto se tratan como el mismo agente, con atribución (`via`).
- **Dos lenguajes:** el contrato entre backend y frontend depende de generar los tipos desde OpenAPI (ADR-0001); la deriva se comprueba en CI.

## Cómo retomar

1. Leer este archivo, luego `CLAUDE.md`, luego el spec vigente.
2. `git status` y `git log --oneline -10` para ver el estado real.
3. Revisar `docs/bootstrap-tasks.md` para la siguiente tarea.
4. Al terminar el bloque: reescribir este archivo.
