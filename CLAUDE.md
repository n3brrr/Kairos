# Kairos

Tablero de tareas **preciso y gobernado** para una persona y sus agentes de Claude Code. Corre en Docker sobre Windows (`localhost`), es una PWA de escritorio en español con modo oscuro, y se usa a sí mismo para gestionar su propio desarrollo. El repo es público: también es una muestra de ingeniería profesional.

## Leé esto antes de actuar

1. `docs/STATUS.md`: dónde estamos y qué sigue. **Al cerrar cada bloque de trabajo, reescribilo.**
2. `docs/superpowers/specs/`: el diseño vigente. `docs/adr/`: decisiones y su porqué. `docs/GLOSSARY.md`: vocabulario.
3. Para proponer mejoras: `docs/FEATURES.md` (ahí se explican las «pasadas»).

## Cómo se trabaja (superpowers)

brainstorming → spec aprobado → writing-plans → TDD (rojo/verde) → verificación antes de dar nada por hecho.

- **No se escribe código de producto sin spec aprobado y plan.**
- No se afirma que algo funciona sin haber ejecutado el comando de verificación y leído su salida.

## Estado del código

Todavía no hay código. Stack decidido (ADR-0001): backend Python (FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite), frontend React + Vite + TypeScript, un solo contenedor Docker. Los comandos (`check`, tests, arranque) se documentarán aquí cuando existan: **no inventes comandos que no estén listados**.

## Mapa previsto del repo (lo que ya existe está marcado)

```
CLAUDE.md                ✓  este archivo
docs/                    ✓  contexto, estado, roadmap, ADR, specs, planes
.claude/                    agents/ · skills/ · rules/ · settings.json   (etapa 0)
.mcp.json                   Kairos conectado a sí mismo                   (etapa 1)
backend/                    Python: domain/ (puro) · features/ · adapters/
frontend/                   React: features/ (dashboard, board, task, agents)
e2e/                        Playwright
Dockerfile · compose.yaml   un solo contenedor
.github/                    CI, Dependabot, plantilla de PR               (etapa 0)
```

## Reglas de oro (no negociables)

1. **Puerta única.** UI, MCP y automatizaciones llaman a los mismos casos de uso con un `Actor` (humano, agente u orquestador). Candados y permisos viven en `domain/`; ninguna entrada puede saltárselos, ni un script.
2. **Los agentes nunca aprueban, cancelan ni borran.** Solo solicitan; decide el humano.
3. **Historial inmutable.** `events` es solo-anexar: nunca UPDATE ni DELETE sobre él.
4. **Contratos.** Los modelos Pydantic son la fuente; los tipos TypeScript se generan desde OpenAPI y no se editan a mano.
5. **Sin API de Anthropic.** El usuario usa cuota de Claude Pro: Kairos nunca llama a Claude. Son las sesiones de Claude Code las que se conectan a Kairos por MCP.
6. **Seguridad.** El puerto solo escucha en `127.0.0.1`; contraseñas y tokens solo como hash; ningún secreto en el repo (`.env` fuera, `.env.example` dentro).
7. **Datos.** SQLite en volumen Docker **nombrado**, no en bind mount (WAL no es fiable en bind mounts de Windows).
8. **Un PR = un propósito.** Cambios pequeños y enfocados.

## Idioma

- UI: español.
- Código, identificadores, commits, PR, ADR y README: **inglés**.
- Este archivo y los docs de trabajo (`STATUS`, `ROADMAP`, `FEATURES`, `GLOSSARY`, specs y planes): español.

## Flujo git (sobrescribe la skill `git-commit-push`; ver ADR-0004)

La skill asume una persona y una rama `dev` de larga vida. Aquí trabajan varios agentes en paralelo, así que:

- **Trunk-based.** `main` siempre estable. Nunca commit ni push directo a `main`. **No existe `dev`.**
- **Una rama corta por tarea**, creada desde `origin/main`: `<tipo>/<ID>-<slug>`. Ejemplo: `feat/KAI-12-approval-queue`. Antes de que Kairos exista, el ID es `BOOT-<n>` (ver `docs/bootstrap-tasks.md`). Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`.
- **Un worktree por agente**, nunca una carpeta compartida: `git worktree add ../Kairos-wt/<ID> -b <rama> origin/main`. La carpeta `Kairos-wt/` es hermana del repo, fuera de él.
- **Commits:** Conventional Commits en inglés, imperativo, ≤72 caracteres, atómicos. `git add <archivo>` por nombre, nunca `git add .`. Nunca `--no-verify`.
- **Rama al día:** `git merge origin/main`; no hacer rebase de una rama ya publicada.
- **PR a `main`:** título convencional con ID (`feat(tasks): add approval queue (KAI-12)`), cuerpo en inglés con *What changed / Why / How it was tested* y enlace a la tarea. Antes de abrirlo, `check` en verde sobre el estado final.
- **Merge: solo el usuario**, por **squash**, y se borra la rama. Ningún agente hace merge (misma regla que con las tareas).
- **Ruleset de `main`** (lo importa el usuario en la web): PR obligatorio, check `check` obligatorio y rama al día, **historial lineal**, sin force-push ni borrado, 0 aprobaciones, sin bypass. Dependabot apunta a `main`.
- **Sigue vigente el resto de la skill:** revisión previa del repo, avisar antes de añadir CI o bots, no hacer force-push, no reescribir historia publicada, no subir secretos, no mezclar propósitos en un PR.

## Mantener la documentación

- `docs/STATUS.md`: se reescribe al cerrar cada bloque (hecho, siguiente, bloqueos).
- `docs/ROADMAP.md`: se actualiza al completar o mover etapas.
- `docs/adr/`: una decisión nueva es un ADR nuevo. Los aceptados no se editan: los reemplaza otro que los *supersede*.
- `docs/FEATURES.md`: las ideas nuevas se anotan ahí; no se implementan sin aprobación.
- Si el código cambia algo que un doc describe, el doc cambia en el mismo PR.
