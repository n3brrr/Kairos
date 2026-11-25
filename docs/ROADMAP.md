# Roadmap

Estados: ⬜ pendiente · 🟦 en curso · ✅ hecha. El detalle de cada etapa vive en su plan (`docs/superpowers/plans/`).

## Etapa −1: Diseño — 🟦

Brainstorming, spec, ADR, contexto del repo. **Sale cuando el usuario aprueba el spec.**

## Etapa 0: Fundaciones y spike — ⬜

- Tooling: `uv` + `pyproject`, `pnpm` + Vite, comando único `check` (lint, tipos, tests de ambos lados).
- Esqueleto del repo según el mapa de `CLAUDE.md`; Docker «hola mundo» con volumen nombrado y puerto en `127.0.0.1`.
- `.claude/`: agentes base, reglas por ruta, hooks (formato, bloqueo de comandos destructivos), recordatorio de actualizar `STATUS.md`.
- CI (GitHub Actions) + Dependabot + plantilla de PR, en su propio PR. Ruleset de `main` (lo importa el usuario).
- **Spike MCP** (descartable): token por agente, cabecera `Authorization` desde `.mcp.json` en Windows, ¿token por subagente?

**Hito:** `check` en verde en CI y el spike responde las dos preguntas de ADR-0005.

## Etapa 1: Núcleo «dogfood-ready» — ⬜

- Dominio puro: estados, candados, permisos, invariantes (con tests de propiedades).
- Persistencia SQLite + historial inmutable encadenado.
- API REST y servidor MCP con identidades y tokens; agente orquestador.
- UI mínima: acceso del usuario, lista y tablero básico, **cola de aprobaciones**, gestión de agentes y tokens.
- Migrar `bootstrap-tasks.md` a Kairos.

**Hito:** los agentes usan Kairos para llevar las tareas de Kairos.

## Etapa 2: Tablero y dashboard — ⬜

- Kanban filtrable (proyecto, tipo, estado, agente) con % de avance.
- Jerarquía completa, dependencias, fechas con semántica.
- Dashboard (ver spec §10) y actualización en vivo (SSE).
- Look «mitológico pero simple» (se diseña con mockups antes de implementarlo).

## Etapa 3: Automatizaciones — ⬜

- Motor de flujos JSON (disparador → condiciones → acciones), programación (cron), recordatorios y notificaciones, webhooks.
- Tres modos de edición sobre el mismo JSON: constructor visual, archivo declarativo y API (agentes).

## Etapa 4: Ejecución y endurecimiento — ⬜

- Runner en el host para lanzar agentes (Claude Code CLI) desde automatizaciones, con límites y aprobación previa.
- Passkeys, backups programados y restauración, README de portfolio, pasadas de `FEATURES.md`.
