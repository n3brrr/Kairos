# Kairos — Documento de diseño

**Fecha:** 2026-11-26 · **Estado:** borrador para aprobación · **Tamaño:** proyecto (diseño completo)

Convención: lo que el usuario decidió va tal cual. Lo que decidí yo (Claude) sin que lo acordáramos está marcado **(mi llamada)** y reunido en el §17, para que lo revise y lo cambie si no le gusta.

## 1. Intención y por qué

Kairos (del griego *kairós*, el momento oportuno) es un tablero de tareas para **una persona y sus agentes de Claude Code**. Nace de dos carencias de Trello:

1. Con muchas tareas abiertas (hasta ~200 activas, más proyectos y tareas en cola) no hay forma de categorizarlas ni de tener un panorama general.
2. No se puede trabajar con un agente de IA con control real sobre lo que hace.

Lo distingue (a) un modelo de datos preciso (estados con transiciones, tipos con campos obligatorios, dependencias, criterios de aceptación con evidencia, jerarquía, fechas con semántica, historial inmutable) y (b) un **control estricto del agente**: identidad, alcance acotado, una tarea a la vez y aprobación humana para cerrar, como un PR.

Objetivo secundario, explícito: el repo es **público** y debe mostrar a reclutadores ingeniería profesional e integración con LLMs.

## 2. Actores

- **Usuario (humano):** único dueño. Tiene todos los permisos.
- **Agentes:** sesiones de Claude Code con identidad propia: nombre, especialidad (por ejemplo «bugs»), tipos de tarea y proyectos permitidos, token. Pueden trabajar a la vez en el mismo proyecto.
- **Orquestador:** agente con rol ampliado que decide quién hace qué. No aprueba.
- **Sistema (etapa 3):** las automatizaciones actúan como un actor con permisos acotados.

## 3. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
- Modelo preciso y control del agente según el §1.
- Dashboard como pantalla de entrada para ver el panorama de un vistazo (§10).
- Kairos gestiona su propio desarrollo desde que tenga lo mínimo (etapa 1).
- Huella pequeña: poca RAM y CPU, sin sacrificar funcionalidad.
- Repo optimizado para trabajar con Claude Code y varios agentes (§12).
- Calidad profesional visible: tests, CI, ADR, documentación.

**No-objetivos (por ahora)**
- Varios usuarios humanos; acceso móvil; edición sin conexión o sincronización entre dispositivos.
- Otro idioma de interfaz que no sea español.
- Exposición a internet o despliegue en el servidor casero.
- Llamar a la API de Anthropic (el usuario usa cuota de Claude Pro).
- Ejecución automática de agentes (llega con el *runner*, etapa 4).

**Anti-objetivos (fracaso aunque «funcione»)**
- Un candado cosmético: reglas que viven solo en la UI y que un agente puede saltarse por otra entrada.
- Un repo que solo funciona en el camino feliz o sin pruebas.
- Complejidad por encima de la escala (microservicios, PostgreSQL, Kubernetes).
- Depender de la API de pago.

## 4. Restricciones

- Windows 11 con Docker Desktop; todo en `localhost`. Python 3.13, Node 24, pnpm y `gh` ya instalados; **`uv` no está instalado**.
- UI de escritorio, en español, modo oscuro.
- Base de datos local (SQLite, ADR-0002), accesible para los agentes a través de Kairos y no directamente.
- Tecnologías web: TypeScript, Python, SQL.
- Repo público en GitHub, licencia MIT, `main` sin protección hasta que el usuario importe el ruleset.

## 5. Enfoques considerados

Detalle y consecuencias en ADR-0001.

| Enfoque | Resultado |
|---|---|
| A. TypeScript de punta a punta | Recomendado por mí: un solo lenguaje y un solo esquema de contratos. **No elegido.** |
| **B. Backend Python + frontend React, un contenedor** | **Elegido por el usuario.** Mejor ecosistema LLM/MCP y aprovecha Python. Costo: dos lenguajes; se mitiga generando los tipos TS desde OpenAPI (Pydantic es la fuente) y comprobando la deriva en CI. |
| C. Servicios separados + PostgreSQL | Descartado: más contenedores y RAM sin beneficio a esta escala. |
| PHP / Laravel | Descartado: MCP y tiempo real encajan peor. |

## 6. Modelo de dominio

### 6.1 Jerarquía y comportamiento de cada clase
Proyecto › Épica › Tarea › Subtarea. Una tarea puede colgar directamente de un proyecto, sin épica. Cómo se modelan en tablas se deja al constructor (recomendación: una tabla `items` con `kind` y `parent_id`). Cada clase se comporta distinto **(mi llamada)**:

- **Proyecto:** ciclo propio (activo, en cola, pausado, archivado) y un atributo **área** (lista editable, por ejemplo Personal, Desarrollo). Sin criterios ni revisión.
- **Épica:** agrupa tareas. Sin asignación, criterios ni revisión. Su estado se **deriva** de sus hijos: sin empezar, en curso, o completa cuando todas sus tareas están hechas o canceladas.
- **Tarea:** la unidad asignable. Usa los siete estados, criterios y revisión. **Es la única clase que cuenta** para «una en curso por agente».
- **Subtarea:** paso de una tarea, con estado simple (pendiente o hecha) y sin asignación propia: la lleva quien lleve la tarea. Una tarea no puede pasar a `in_review` con subtareas pendientes.

### 6.2 Campos y tipos
**Campos base** de una tarea: título, descripción, tipo, prioridad (P0–P3), etiquetas libres, padre (proyecto o épica), fechas (§6.7), dependencias, criterios de aceptación, asignado y resumen de entrega. **Categorizar** una tarea es combinar proyecto (con su área), tipo, etiquetas y prioridad **(mi llamada)**.

Un **tipo** (bug, feature, chore, investigación, personal…) define **cuáles de los campos base son obligatorios** y una plantilla de criterios de aceptación. Los tipos son datos editables, no código. **Decidido con el usuario: lista fija de campos en la etapa 1.** Los campos propios por tipo quedan como idea futura (`IDEA-15` en `FEATURES.md`).

### 6.3 Estados guardados y transiciones

`proposed → backlog → ready → in_progress → in_review → done`, más `cancelled`. En la UI: Propuesta, Backlog, Lista, En curso, En revisión, Hecha, Cancelada.

**Bloqueada no es un estado guardado:** es derivada. Una tarea con dependencias abiertas se muestra bloqueada y no puede pasar a `in_progress`.

| Acción | Usuario | Orquestador | Agente |
|---|---|---|---|
| Crear (siempre como `proposed` si lo crea un agente) | sí | sí | sí, solo como propuesta |
| `proposed → backlog` (triaje) | sí | sí | no |
| `backlog → ready` | sí | sí | no |
| Asignar a un agente (asignar ya es reservar) | sí | sí | no |
| `ready → in_progress` | sí | no | sí, solo si está asignada a él |
| `in_progress → in_review` | sí | no | sí, si pasa los candados |
| `in_review → done` (aprobar) | sí | **no** | **no** |
| Devolver una entrega con comentario (`in_review → ready`, **conserva la asignación**) | sí | no | no |
| Liberar una tarea (`in_progress → ready`, **quita la asignación**) | sí | sí | sí, con motivo |
| Mover hacia atrás (por ejemplo `ready → backlog`, arrastrando en el tablero) | sí | no | no |
| Descartar una propuesta (`proposed → cancelled`) | sí | **no** | no |
| Reabrir `done` o `cancelled` (a `backlog` o `ready`, con motivo) | sí | no | no |
| Cancelar | sí | **no** | solo solicita (§6.6) |
| Borrar | sí | **no** | **no** |
| Cambiar permisos, tokens, automatizaciones | sí | **no** | **no** |

El usuario también puede trabajar en una tarea a la vez que un agente, pero **nunca hay más de un agente activo** en la misma tarea.

### 6.4 Candados (automáticos)
Para pasar a `in_review`: campos obligatorios del tipo completos, **todos los criterios con evidencia**, sin dependencias abiertas y un resumen de entrega no vacío. Si falla, el sistema rechaza la acción y dice por qué.
Para pasar a `in_progress`: la tarea está asignada al actor, no tiene dependencias abiertas y el agente no tiene otra tarea en curso.
Para pasar a `ready`: al menos **un criterio de aceptación**, de modo que «todos los criterios con evidencia» nunca sea vacío **(mi llamada)**.

**Los candados obligan siempre a agentes y orquestador.** El usuario puede **forzarlos** indicando un motivo, que queda en el historial como `gate_overridden` **(mi llamada)**.

### 6.5 Criterios, evidencia y avance
Cada tarea tiene criterios de aceptación; cada criterio se marca cumplido con una **evidencia** (texto, enlace o salida de un comando). **Avance** de una hoja = criterios cumplidos / total (100 % si está hecha). Los contenedores promedian a sus hijos (fórmula exacta, al plan).

**Quién escribe los criterios (mi llamada).** Los define el usuario o el orquestador, o salen de la plantilla del tipo. Un agente puede *redactarlos dentro de una propuesta*; una vez promovida, **no puede añadir, editar ni borrar criterios: solo adjuntar evidencia**. En una tarea suya, un agente puede cambiar únicamente comentarios, evidencias, resumen de entrega y notas de trabajo; ni título, tipo, prioridad, fechas, padre ni dependencias.

### 6.6 Solicitudes de aprobación
Como un PR: un agente que quiera cancelar o cerrar una tarea crea una **solicitud** con descripción y motivo; queda pendiente hasta que el usuario la aprueba o rechaza (con nota). Pasar a `in_review` crea implícitamente la solicitud de aprobación de la entrega.

### 6.7 Dependencias, fechas y recurrencia
Dependencias «bloquea a», sin ciclos. Una dependencia **cancelada cuenta como resuelta** y el usuario recibe un aviso **(mi llamada)**. Fechas con semántica: inicio, vencimiento y recurrencia (el modelo la guarda desde la etapa 1; el motor que genera instancias llega en la etapa 3).

### 6.8 Asignación
Un agente no se auto-asigna: empieza solo lo que le asignó el orquestador o el usuario. **No existe una «reserva» aparte:** asignar ya es reservar. Invariantes que impone el dominio **también al orquestador**: una tarea `in_progress` por agente, un agente activo por tarea, tipo y proyecto dentro del alcance del agente, sin dependencias abiertas.

**Cola.** Decidido con el usuario: un agente **no está limitado a una sola tarea asignada**. Puede tener una cola de hasta 3 tareas asignadas (límite configurable por agente **(mi llamada)**) pero **una sola `in_progress`**. Las tareas en `in_review`, que esperan tu aprobación, no cuentan para el límite.

**Subagentes en tareas grandes.** El usuario pidió poder usar «un par de subagentes o más» en tareas grandes. **Mi interpretación:** un agente puede apoyarse en subagentes de su propia sesión. Kairos los trata como el **mismo agente** (sin permisos extra, y sigue habiendo un único agente activo por tarea) y registra en el historial qué subagente hizo cada cosa, solo como atribución. Que cada subagente tenga token propio depende del spike (ADR-0005).

### 6.9 Visibilidad
- **Agente:** ve sus tareas asignadas completas, más el contexto mínimo para trabajar: proyecto o épica padre (título y resumen) y, de lo que lo bloquea, id, título y estado. No ve el contenido de las tareas de otros agentes.
- **Orquestador:** ve todas las tareas (necesita repartir) y los perfiles de los agentes, nunca los tokens.
- **Usuario:** ve todo.

### 6.10 Historial
Registro de eventos inmutable, solo-anexar, encadenado por hash (ADR-0006). Cada evento guarda quién (usuario, qué agente) y por qué.

## 7. Arquitectura

Un contenedor con un proceso FastAPI que expone:

- **REST** `/api/*` para la UI, con sesión del usuario.
- **MCP** `/mcp` (Streamable HTTP) para los agentes, con token por agente (ADR-0005).
- **SSE** para actualizaciones en vivo de la UI.
- La SPA de React como archivos estáticos.

Capas del backend (ADR-0003): `domain/` (puro: estados, candados, permisos), `features/<x>/` (casos de uso, repositorio, rutas, herramientas MCP y tests juntos) y `adapters/`. Los contratos son modelos Pydantic; el frontend recibe tipos TypeScript generados desde OpenAPI (ADR-0001). Defensa en profundidad: índice único parcial «un `in_progress` por agente» y triggers que prohíben modificar `events` (ADR-0002).

## 8. Interfaz de agentes (MCP)

Herramientas previstas (nombres exactos, al plan):
- **Agente:** consultar su contexto y sus tareas, ver una tarea, empezarla, liberarla con motivo, comentar, actualizar campos permitidos, registrar evidencia en un criterio, enviar a revisión con resumen, proponer una tarea, solicitar cancelación.
- **Orquestador (añade):** listar todas las tareas y agentes, asignar, triar propuestas, partir una épica en propuestas.

El spike (ADR-0005) valida la autenticación antes de fijar este diseño.

## 9. Seguridad

- El puerto escucha solo en `127.0.0.1`; se validan `Origin` y `Host` (protección frente a DNS rebinding).
- **Usuario:** contraseña con argon2id, cookie de sesión `HttpOnly` y `SameSite=Strict`, protección CSRF y límite de intentos. Passkeys como refuerzo posterior **(mi llamada)**. La cuenta inicial se crea con un comando local, una sola vez **(mi llamada)**.
- **Agentes:** token aleatorio de 256 bits, guardado solo como hash, con alcance y revocable, y `last_used_at`. Se muestra una sola vez al crearlo. Un token de agente no sirve en los endpoints del usuario, ni al revés.
- Ningún secreto en el repo; el token del agente llega por variable de entorno.
- Contenedor sin root, sistema de archivos de solo lectura salvo el volumen de datos.

## 10. Dashboard y vistas

Pantalla de entrada: dashboard con las métricas principales, los proyectos activos y los pendientes. Lo que debe responder de un vistazo:

1. **Esperando tu aprobación:** entregas y solicitudes pendientes. Va primero, porque es lo que frena a los agentes.
2. **Proyectos activos** con % de avance, y aparte los proyectos en cola.
3. **Bloqueadas y atrasadas.**
4. **Qué hace cada agente ahora**, en vivo.
5. **Actividad reciente**, tomada del historial.

**Tablero kanban** adaptado: columnas por estado, filtrables por proyecto, tipo, estado de sus subtareas, agente y % de avance. En la etapa 1 existe una **lista simple** de tareas como UI mínima para el dogfooding **(mi llamada)**; el calendario y la línea de tiempo quedan fuera hasta que se pidan.

**Look:** «mitológico pero simple», modo oscuro. Se diseña con mockups en la etapa 2; ahora solo se reserva que los colores y la tipografía sean tokens de tema reemplazables.

## 11. PWA y tiempo real

PWA de escritorio instalable (`localhost` cuenta como contexto seguro, sin HTTPS): manifiesto y service worker para el shell. Sin modo sin conexión de los datos (no-objetivo). Los cambios que hacen los agentes aparecen en pantalla por SSE, sin recargar.

## 12. Repo optimizado para Claude Code

- `CLAUDE.md` raíz corto (mapa, reglas de oro, flujo git) y `CLAUDE.md` por módulo cuando haga falta; `.claude/rules/` con alcance por ruta.
- Estructura por funcionalidad y archivos pequeños: un agente trabaja en una sola carpeta sin cargar el resto.
- `.claude/agents/` (orquestador, backend, frontend, bugs, revisor), `.claude/skills/` con procedimientos repetibles (nueva migración, nueva herramienta MCP) y hooks para lo que no puede romperse (formato, bloqueo de comandos destructivos, recordatorio de actualizar `docs/STATUS.md`).
- Un comando único `check` (lint, tipos, tests de backend y frontend) como bucle de verificación.
- Un git worktree por agente (ADR-0004).
- `docs/` como memoria del proyecto: estado, roadmap, glosario, ideas, ADR y tareas de arranque.
- Kairos se conecta a sí mismo por `.mcp.json` desde la etapa 1.

## 13. Automatizaciones (etapa 3; el modelo de eventos las prepara desde la 1)

- Flujos definidos como **JSON versionado y validado** con Pydantic: disparador (evento o cron) → condiciones → acciones (crear o mover una tarea, notificar, webhook).
- **Tres modos de edición sobre el mismo JSON:** constructor visual, archivo declarativo y API (los agentes pueden diseñarlos).
- Programación con un scheduler en el proceso; recordatorios y notificaciones; webhooks de salida.
- **Ejecución de agentes:** no puede lanzarse desde dentro del contenedor porque Claude Code vive en Windows. Hará falta un *runner* en el host (etapa 4), con límites y aprobación previa.

## 14. Calidad y entrega

- Pirámide de pruebas: unitarias y de propiedades (Hypothesis) sobre `domain/`, integración con SQLite en memoria, pruebas de contrato del MCP con un cliente real, y e2e con Playwright.
- TDD rojo/verde en cada funcionalidad.
- CI: un job `check` en GitHub Actions que ejecuta el mismo `check` local, más comprobación de deriva de tipos generados, construcción de la imagen y Dependabot (`pip`, `npm`, `docker`, `github-actions`), todo en su propio PR.
- Imagen Docker multi-stage, usuario sin root, healthcheck.

## 15. Etapas

Resumen; el estado vivo está en [`docs/ROADMAP.md`](../../ROADMAP.md).

0. **Fundaciones y spike:** tooling, estructura, `check`, Docker, `.claude/`, CI, spike MCP.
1. **Núcleo «dogfood-ready»:** dominio con el **modelo completo de jerarquía, dependencias y fechas** (los candados y el contexto del agente lo necesitan), persistencia con historial, REST y MCP con tokens, orquestador, UI mínima con lista simple y cola de aprobaciones. *Desde aquí los agentes usan Kairos para construir Kairos.*
2. **Tablero y dashboard:** kanban filtrable, vistas de jerarquía, dependencias y fechas, dashboard, SSE, look.
3. **Automatizaciones:** motor, cron, notificaciones, webhooks, constructor visual.
4. **Ejecución y endurecimiento:** runner, passkeys, backups, README de portfolio.

## 16. Riesgos

- **Autenticación MCP en Windows** (ADR-0005): se descarta o confirma con el spike, antes de fijar la etapa 1.
- **Token por subagente:** si no es posible, «un agente» será «una sesión de Claude Code» y el diseño de roles se adapta.
- **Deriva de contratos entre dos lenguajes:** generación de tipos y comprobación en CI.
- **SQLite en Docker Desktop:** solo con volumen nombrado (ADR-0002).
- **Cuota de Claude Pro:** un orquestador que corra en bucle la consumiría; corre a demanda.

## 17. Mis llamadas (no acordadas; el usuario puede cambiarlas)

- Idioma: código, commits, PR, ADR y README en inglés; docs de trabajo y `CLAUDE.md` en español.
- Historial encadenado por hash (ADR-0006) y comando `verify`.
- pyright en modo estricto y Ruff; Biome en el frontend; pnpm.
- Autenticación del usuario: contraseña + sesión en el MVP; passkeys después. Cuenta inicial creada por comando local.
- «Bloqueada» como estado derivado, no guardado.
- Un agente no se auto-asigna; el orquestador puede triar (promover) propuestas pero **no** descartarlas: descartar es del usuario.
- Propuestas de agentes: cualquier agente puede crearlas dentro de su alcance.
- Rama única `main` + ramas cortas con squash, y worktree por agente (ADR-0004).
- El orquestador corre a demanda, no en bucle.
- Comportamiento por clase de ítem, campos base y categorización por proyecto + área + tipo + etiquetas + prioridad (§6.1, §6.2).
- Un agente solo adjunta evidencia; no edita criterios tras el triaje; una tarea necesita al menos un criterio para pasar a `ready` (§6.4, §6.5).
- Devolver una entrega la pasa a `ready` conservando la asignación; liberar una tarea quita la asignación (§6.3).
- Descartar una propuesta y reabrir tareas cerradas son solo del usuario; el usuario puede forzar candados con motivo registrado.
- Una dependencia cancelada cuenta como resuelta, con aviso.
- Sin «reserva» aparte: asignar ya es reservar.
- Etapa 1 con el modelo completo de jerarquía y una lista simple; kanban en la etapa 2.

## 17.1 Resuelto con el usuario tras la revisión del spec

1. **Tareas por agente** (§6.8): no solo una. Cola corta de asignadas, una sola en curso, y subagentes de apoyo en tareas grandes (la lectura de los subagentes es mía; ver §6.8).
2. **Campos propios por tipo** (§6.2): lista fija en la etapa 1; campos propios más adelante.

No quedan preguntas abiertas del spec.

## 18. Se deja al constructor

Versiones exactas de dependencias; ORM síncrono o asíncrono (recomendación: síncrono para SQLite, con SSE asíncrono sobre un bus de eventos en memoria); nombres de tablas, columnas y herramientas MCP; formulación exacta del avance de contenedores; ejecutor del comando `check` multiplataforma (candidatos: `poethepoet` o `just`); estructura exacta de carpetas dentro de cada funcionalidad; configuración de Tailwind y tokens de tema.
