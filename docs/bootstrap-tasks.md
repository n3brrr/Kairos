# Tareas de arranque (bootstrap)

Kairos todavía no existe, así que sus primeras tareas viven aquí. Usan el mismo formato que tendrán en Kairos (tipo, estado, criterios) para migrarlas sin reescribir. En la etapa 1 se importan a Kairos y este archivo queda como histórico.

Estados: `ready` · `in_progress` · `in_review` · `done`. IDs: `BOOT-nn`.

## BOOT-001 — Contexto del proyecto en el repo
- **Tipo:** docs · **Estado:** `in_review` · **Rama:** `docs/BOOT-001-project-context`
- **Criterios:**
  - [x] `CLAUDE.md` con mapa, reglas de oro y flujo git.
  - [x] `docs/` con estado, roadmap, ideas, glosario y ADR.
  - [x] Spec de diseño revisado por un subagente.
  - [ ] El usuario aprueba el spec y fusiona el PR.

## BOOT-002 — Plan de la etapa 0
- **Tipo:** plan · **Estado:** `ready` · **Depende de:** BOOT-001
- **Criterios:**
  - [ ] Plan en `docs/superpowers/plans/` con tareas pequeñas y verificables (skill `writing-plans`).

## BOOT-003 — Spike MCP: token por agente
- **Tipo:** spike · **Estado:** `ready` · **Depende de:** BOOT-001
- **Criterios:**
  - [ ] Un servidor MCP mínimo por HTTP exige `Authorization: Bearer` y Claude Code se conecta desde `.mcp.json` en Windows.
  - [ ] Se comprueba si un subagente puede llevar su propio token o hereda el de la sesión.
  - [ ] Resultado anotado en ADR-0005 (aceptado o reemplazado). El código del spike se descarta.

## BOOT-004 — Fundaciones del repo
- **Tipo:** chore · **Estado:** `ready` · **Depende de:** BOOT-002
- **Criterios:**
  - [ ] `uv` instalado y `backend/` con tooling (Ruff, pyright, pytest).
  - [ ] `frontend/` con Vite, Biome y Vitest.
  - [ ] Comando único `check` que ejecuta ambos lados y falla si algo falla.
  - [ ] Docker «hola mundo» con volumen nombrado y puerto solo en `127.0.0.1`.

## BOOT-005 — CI, Dependabot y plantilla de PR
- **Tipo:** ci · **Estado:** `ready` · **Depende de:** BOOT-004
- **Criterios:**
  - [ ] Workflow de GitHub Actions que ejecuta `check` (job `check`).
  - [ ] `dependabot.yml` para `pip`, `npm`, `docker` y `github-actions`, apuntando a `main`.
  - [ ] Plantilla de PR en inglés.
  - [ ] El usuario importa el ruleset de `main` en GitHub.
