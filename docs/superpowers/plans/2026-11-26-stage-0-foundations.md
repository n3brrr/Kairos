# Stage 0: Foundations and Spike — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leave the repo ready to build the core: backend and frontend tooling, one `check` command, a Docker image, Claude Code project configuration, CI, and the answer to the MCP authentication spike.

**Architecture:** A monorepo with `backend/` (FastAPI, one process), `frontend/` (React + Vite, served as static files by the backend) and `tools/` (repo tooling in stdlib-only Python, plus hook scripts). One container. Frontend types are generated from the backend's OpenAPI schema.

**Tech Stack:** Python 3.13 + uv, FastAPI, Pydantic v2, pytest, Ruff, pyright · Node 24 + pnpm, React, Vite, Vitest, Biome, vite-plugin-pwa, openapi-typescript, openapi-fetch · Docker Compose · GitHub Actions.

**Spec:** [`../specs/2026-11-26-kairos-design.md`](../specs/2026-11-26-kairos-design.md) (§4, §7, §9, §11, §12, §14, §15) · ADR-0001, 0002, 0004, 0005.

## Global Constraints

- Windows 11 with Docker Desktop; everything on `localhost`; the container port is published **only on `127.0.0.1`** (spec §4, §9).
- Python 3.13, Node 24, pnpm and `gh` are installed; **`uv` is not** (spec §4). Ask the owner before installing tools on their machine.
- FastAPI + Pydantic v2 backend; React + Vite + TypeScript frontend; one container whose runtime image contains only Python (ADR-0001).
- TypeScript API types are **generated** from OpenAPI, never edited by hand; CI fails when they are stale (ADR-0001).
- SQLite lives only in a **named** Docker volume, never a bind mount (ADR-0002). Stage 0 creates no database; it only reserves `/data`.
- `Host` is validated on every request (spec §9). `Origin` validation arrives with the MCP endpoint (ADR-0005).
- Non-root container with a read-only filesystem except the data volume (spec §9).
- Everything in the repo is English: code, identifiers, UI strings (kept in a message catalog), docs, commits, PRs. Only the chat with the owner is Spanish.
- Git: branches `<type>/BOOT-nn-slug` from `origin/main` in a worktree `../Kairos-wt/<ID>`; Conventional Commits in English; `git add <file>` by name; never `--no-verify`; the owner merges by squash (ADR-0004, `CLAUDE.md`).
- Package managers (owner rule): **pnpm** for everything JavaScript/TypeScript (install, run, exec, dlx); never `npm`, `npx`, `yarn` or a `package-lock.json`. **uv** for Python; never `pip install` into the system. (`npm` still appears as the Dependabot ecosystem name; that is a config key, not a command.)
- The CI job is named exactly `check`.
- No calls to the Anthropic API (spec §3).
- Out of scope (YAGNI): database, authentication, a real MCP endpoint, Tailwind, dnd-kit, TanStack Query, Playwright. They arrive in stage 1 or 2.

## Review Focus

Inputs the spec implies but no requirement states; each has a test or a verification in the task named:

1. A request with a foreign `Host` header (DNS rebinding) gets `400` — Task 2.
2. A deep SPA link (`/boards/1`) serves `index.html`, but an unknown `/api/...` path returns a JSON `404`, never HTML — Task 2.
3. The backend starts when the static directory does not exist (development without a build): `/api/health` answers and `/` is `404` — Task 2.
4. Windows CRLF line endings in the generated types file do not count as contract drift, otherwise `check` flaps between Windows and CI — Task 4.
5. A freshly created named volume is writable by the container's non-root user — Task 6.

## Order, branches and PRs

Each PR comes from `origin/main` in its own worktree. If the PR it depends on is not merged yet, stack on its branch and, after the squash merge, move with `git rebase --onto origin/main <old base>`.

| # | Branch | Tasks | Needs |
|---|---|---|---|
| 1 | `docs/BOOT-003-mcp-spike-result` | 1 | BOOT-001 merged |
| 2 | `chore/BOOT-004-foundations` | 2–5 | BOOT-001 merged |
| 3 | `build/BOOT-006-docker` | 6 | PR 2 |
| 4 | `chore/BOOT-007-claude-config` | 7–8 | PR 2 (its tests run inside `check`) |
| 5 | `ci/BOOT-005-ci` | 9 | PRs 2 and 3 |

---

### Task 1: MCP authentication spike (BOOT-003)

**Files:**
- Throwaway, outside the repo, in the scratchpad directory: `mcp-spike/server.py`, `mcp-spike/.mcp.json`, `mcp-spike/.claude/agents/spike-beta.md`
- Modify: `docs/adr/0005-agents-over-mcp-with-tokens.md`, `docs/STATUS.md`, `docs/bootstrap-tasks.md`

**Interfaces:**
- Produces: ADR-0005 `accepted` (or superseded) with the exact `.mcp.json` shape that works and whether a subagent can carry its own token. Stage 1 depends on this answer.

- [ ] **Step 1: Record versions.** Run `claude --version` and `python --version`. If `uv` is missing, ask the owner before running `winget install --id astral-sh.uv -e`.
- [ ] **Step 2: Write `server.py`.** Official `mcp` package, one tool `whoami() -> str`. An ASGI middleware reads `Authorization: Bearer <token>`, maps `kai_spike_alpha` → `agent-alpha` and `kai_spike_beta` → `agent-beta`, answers `401` otherwise and stores the identity in a `ContextVar` that the tool reads. Serve Streamable HTTP at `http://127.0.0.1:8765/mcp` with the SDK's Origin/Host protection (`TransportSecuritySettings`) enabled. Run with `uv run --with mcp --with uvicorn python server.py`.
- [ ] **Step 3: Write `.mcp.json`** exactly:

```json
{ "mcpServers": { "kairos": { "type": "http", "url": "http://127.0.0.1:8765/mcp",
  "headers": { "Authorization": "Bearer ${KAIROS_TOKEN}" } } } }
```

- [ ] **Step 4: Experiment A (header on Windows).** In the spike directory, with `$env:KAIROS_TOKEN = "kai_spike_alpha"`, run `claude -p "Call the whoami tool of the kairos MCP server and print only its result" --allowedTools "mcp__kairos__whoami"`. Expected: `agent-alpha`. Repeat with `kai_spike_beta` → `agent-beta`. With `kai_spike_wrong`, `claude mcp list` shows `kairos` as failed and the tool is never reached.
- [ ] **Step 5: Experiment B (subagent token).** Read the current docs for the subagent frontmatter key that declares MCP servers. Add `.claude/agents/spike-beta.md` declaring its own `kairos` server with `Bearer ${KAIROS_TOKEN_BETA}`. With the parent on alpha and `KAIROS_TOKEN_BETA=kai_spike_beta`, ask the session to call `whoami` itself and through `spike-beta`. Expected if supported: `agent-alpha`, then `agent-beta`. If the subagent inherits the session's connection: both `agent-alpha`.
- [ ] **Step 6: Decide.** A and B pass → ADR-0005 `accepted`: "one agent = one session; a subagent may carry its own token". A passes, B fails → `accepted`: "subagents share the session identity, attributed with `via`". A fails → record the failure and the fallback (a stdio proxy that injects the token) as a stage 1 task; do not accept the ADR.
- [ ] **Step 7: Record and commit.** Turn the ADR's "Open questions" into a "Results" table (experiment, command, observed output, Claude Code version). Refresh STATUS risks and mark BOOT-003 `done`. Use at most 6 `claude -p` calls in total: they spend the owner's quota.

```bash
git add docs/adr/0005-agents-over-mcp-with-tokens.md docs/STATUS.md docs/bootstrap-tasks.md
git commit -m "docs: record MCP auth spike results in ADR-0005 (BOOT-003)"
```

---

### Task 2: Backend skeleton (BOOT-004)

**Files:**
- Create: `backend/pyproject.toml`, `backend/src/kairos/__init__.py` (`__version__ = "0.1.0"`), `backend/src/kairos/config.py`, `backend/src/kairos/main.py`, `backend/src/kairos/domain/__init__.py`, `backend/src/kairos/features/__init__.py`, `backend/src/kairos/features/health/__init__.py`, `backend/src/kairos/features/health/api.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/tests/test_app_security.py`, `backend/tests/test_static.py`

**Interfaces:**
- Produces: `kairos.config.Settings(BaseSettings)` with env prefix `KAIROS_` and fields `data_dir: Path = Path("/data")`, `static_dir: Path | None = None`, `allowed_hosts: list[str] = ["localhost", "127.0.0.1"]`.
- Produces: `kairos.main.create_app(settings: Settings | None = None) -> FastAPI`, used with `uvicorn --factory`.
- Produces: `kairos.features.health.api.router: APIRouter` serving `GET /api/health` → `HealthResponse(status: Literal["ok"], version: str)` with `operation_id="get_health"` (stable generated names).
- Produces: fixtures `client` (app without static dir) and `make_client(static_dir: Path | None) -> TestClient`, both with `base_url="http://localhost"`.

- [ ] **Step 1: Write the failing tests** (the fixtures live in `conftest.py`).

```python
def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": kairos.__version__}

def test_foreign_host_is_rejected(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400

def test_spa_fallback_serves_index_for_deep_links(make_client, tmp_path):
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    r = make_client(tmp_path).get("/boards/1")
    assert r.status_code == 200 and "kairos" in r.text

def test_unknown_api_path_is_a_json_404(make_client, tmp_path):
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    r = make_client(tmp_path).get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")

def test_app_starts_without_a_static_dir(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail.** From `backend/`: `uv run pytest -q`. Expected: FAIL (`kairos` not importable).
- [ ] **Step 3: Implement.** `pyproject.toml`: project `kairos`, `requires-python = ">=3.13"`, dependencies `fastapi`, `uvicorn[standard]`, `pydantic-settings`; dev group `pytest`, `httpx`, `ruff`, `pyright`, `pyyaml`; Ruff line length 100 with rules `E,F,I,UP,B,SIM`; pyright `strict`; pytest `testpaths = ["tests"]`. `create_app` adds `TrustedHostMiddleware(allowed_hosts)`; when `static_dir` holds an `index.html` it mounts `static_dir/assets` and registers a last catch-all `GET` that serves `index.html`, raising `404` for paths starting with `api/` or `mcp`.
- [ ] **Step 4: Run to verify they pass.** `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`. Expected: 5 passed, and no findings.
- [ ] **Step 5: Commit.**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src backend/tests
git commit -m "feat(backend): add FastAPI app factory with health endpoint (BOOT-004)"
```

---

### Task 3: Frontend skeleton (BOOT-004)

**Files:**
- Create: `frontend/package.json` (`packageManager` = the installed pnpm version), `frontend/pnpm-lock.yaml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/biome.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/messages.ts`, `frontend/src/pwa-manifest.ts`, `frontend/public/icons/icon-192.png`, `frontend/public/icons/icon-512.png` (neutral dark placeholders, replaced when the look is designed)
- Test: `frontend/src/App.test.tsx`, `frontend/src/pwa-manifest.test.ts`

**Interfaces:**
- Produces: `messages` in `src/messages.ts`: `export const messages = { appName: "Kairos" } as const;` — the message catalog; components contain no hardcoded UI text.
- Produces: `manifest` in `src/pwa-manifest.ts`, typed `Partial<ManifestOptions>`: `name` and `short_name` `"Kairos"`, `lang: "en"`, `display: "standalone"`, `start_url: "/"`, dark `theme_color` and `background_color`, icons `192x192` and `512x512`.
- Produces: `App(): JSX.Element`; package scripts `dev`, `build`, `test`, `lint` (`biome check .`), `typecheck` (`tsc --noEmit`).

- [ ] **Step 1: Write the failing tests.**

```ts
it("renders the app name from the message catalog", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: messages.appName })).toBeInTheDocument();
});

it("declares an installable desktop manifest", () => {
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.icons?.map((i) => i.sizes)).toEqual(
    expect.arrayContaining(["192x192", "512x512"]),
  );
});
```

- [ ] **Step 2: Run to verify they fail.** From `frontend/`: `pnpm test`. Expected: FAIL (modules missing).
- [ ] **Step 3: Implement.** Vite + React + strict TypeScript; `vite-plugin-pwa` with `registerType: "autoUpdate"` and the manifest above; dev proxy `/api` → `http://127.0.0.1:8000`; Vitest with jsdom and Testing Library; Biome recommended rules with import sorting.
- [ ] **Step 4: Run to verify.** `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`. Expected: 2 passed, no findings, and `dist/manifest.webmanifest` plus `dist/sw.js` exist.
- [ ] **Step 5: Commit.**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/biome.json frontend/src frontend/public
git commit -m "feat(frontend): add React PWA skeleton with message catalog (BOOT-004)"
```

---

### Task 4: Contract pipeline (BOOT-004)

**Files:**
- Create: `tools/gen_api_types.py`, `tools/tests/conftest.py` (puts `tools/` and `tools/hooks/` on `sys.path`), `tools/tests/test_gen_api_types.py`, `frontend/src/api/schema.d.ts` (generated), `frontend/src/api/client.ts`
- Modify: `frontend/package.json` (add `openapi-typescript`, `openapi-fetch`), `frontend/biome.json` (ignore the generated `src/api/schema.d.ts` so `pnpm lint` never reformats it), `frontend/src/App.tsx`, `frontend/src/messages.ts`, `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: `normalize(text: str) -> str` (CRLF → LF) and `is_up_to_date(generated: str, committed: str) -> bool` in `tools/gen_api_types.py`.
- Produces: CLI `uv run --project backend python tools/gen_api_types.py [--check]`. It dumps `create_app(Settings()).openapi()` to a temp JSON, runs `pnpm exec openapi-typescript` into `frontend/src/api/schema.d.ts` (or, with `--check`, into a temp file that is compared). On drift it exits `1` printing `frontend/src/api/schema.d.ts is out of date; run: uv run --project backend python tools/gen_api_types.py`.
- Produces: `api` in `frontend/src/api/client.ts`: `createClient<paths>(...)` from `openapi-fetch` with a relative base URL.
- Produces: `messages.serverConnected(version: string): string` → `` `Server connected · v${version}` ``.

- [ ] **Step 1: Write the failing tests.**

```python
def test_crlf_is_not_drift():
    assert is_up_to_date("a\r\nb\r\n", "a\nb\n")

def test_real_change_is_drift():
    assert not is_up_to_date("a\nb\n", "a\nc\n")
```

```ts
it("shows the server version once the health check answers", async () => {
  vi.spyOn(api, "GET").mockResolvedValue({ data: { status: "ok", version: "0.1.0" } } as never);
  render(<App />);
  expect(await screen.findByText(messages.serverConnected("0.1.0"))).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify they fail.** `uv run --project backend pytest tools/tests -q` and `pnpm test`. Expected: FAIL.
- [ ] **Step 3: Implement** the helpers, the CLI, the client, and `App` calling `api.GET("/api/health")` to display the message.
- [ ] **Step 4: Generate and verify.** Run the CLI once to write `schema.d.ts`. Then `uv run --project backend python tools/gen_api_types.py --check` → exit `0`. Drift drill: add a field to `HealthResponse`, run `--check` → exit `1` with the message above; revert. `pnpm test` and `pytest tools/tests` pass.
- [ ] **Step 5: Commit.**

```bash
git add tools/gen_api_types.py tools/tests frontend/package.json frontend/pnpm-lock.yaml frontend/src
git commit -m "feat(contracts): generate TypeScript API types from OpenAPI with drift check (BOOT-004)"
```

---

### Task 5: Single `check` command (BOOT-004)

**Files:**
- Create: `tools/check.py`, `tools/tests/test_check.py`
- Modify: `CLAUDE.md` ("Code status": list the real commands), `docs/bootstrap-tasks.md`, `docs/STATUS.md`

**Interfaces:**
- Produces: `Step(name: str, argv: list[str], cwd: Path)` (NamedTuple), `StepResult(step: Step, returncode: int)`.
- Produces: `build_steps(root: Path) -> list[Step]`, in order: `backend:format` (`uv run ruff format --check --config pyproject.toml . ../tools`), `backend:lint` (`uv run ruff check --config pyproject.toml . ../tools`; both cover `tools/` with the backend's Ruff config), `backend:types` (`uv run pyright`), `backend:test` (`uv run pytest -q`), `tools:test` (`uv run --project backend pytest tools/tests -q`), `contracts` (`uv run --project backend python tools/gen_api_types.py --check`), `frontend:lint`, `frontend:types`, `frontend:test`, `frontend:build` (the pnpm scripts). Executables are resolved with `shutil.which` so `pnpm.cmd` works on Windows.
- Produces: `run_steps(steps: list[Step], runner=subprocess.run) -> list[StepResult]` — runs **all** steps even after a failure.
- Produces: `summarize(results: list[StepResult]) -> tuple[str, int]` — one `PASS`/`FAIL` line per step, exit code `1` if any failed else `0`.
- CLI: `python tools/check.py` (stdlib only, no environment needed).

- [ ] **Step 1: Write the failing tests:** `test_all_steps_run_even_after_a_failure`, `test_exit_code_is_one_when_any_step_fails`, `test_summary_lists_every_step_with_its_status`, `test_build_steps_cover_backend_frontend_and_contracts` (using a fake `runner`).
- [ ] **Step 2: Run to verify they fail.** `uv run --project backend pytest tools/tests/test_check.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Verify.** `python tools/check.py` → every step `PASS`, exit `0`. Break a backend test on purpose → `FAIL` for that step only and exit `1`; restore it.
- [ ] **Step 5: Document and commit.** Update `CLAUDE.md` with the commands that now exist; mark BOOT-004 `in_review`.

```bash
git add tools/check.py tools/tests/test_check.py CLAUDE.md docs/bootstrap-tasks.md docs/STATUS.md
git commit -m "feat(tools): add single check command for backend, frontend and contracts (BOOT-004)"
```

Then push the branch and open the PR (`chore: add backend, frontend and check tooling (BOOT-004)`) with the real `check` output in "How it was tested".

---

### Task 6: Docker image and compose (BOOT-006)

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`, `tools/tests/test_compose.py`
- Modify: `CLAUDE.md` (Docker commands), `docs/bootstrap-tasks.md`, `docs/STATUS.md`

**Interfaces:**
- Produces: compose service `kairos`, image `kairos:dev`, container user uid `10001`, env `KAIROS_DATA_DIR=/data` and `KAIROS_STATIC_DIR=/app/static`, healthcheck on `/api/health`.

- [ ] **Step 1: Write the failing tests** (parse `compose.yaml` with PyYAML):

```python
def test_host_port_is_published_on_loopback_only(compose):
    assert compose["services"]["kairos"]["ports"] == ["127.0.0.1:8000:8000"]

def test_data_lives_in_a_named_volume(compose):
    assert "kairos-data:/data" in compose["services"]["kairos"]["volumes"]
    assert "kairos-data" in compose["volumes"]

def test_container_is_read_only_and_drops_privileges(compose):
    svc = compose["services"]["kairos"]
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]
```

- [ ] **Step 2: Run to verify they fail** (no `compose.yaml`).
- [ ] **Step 3: Implement.** `Dockerfile`, multi-stage: (1) `node:24-slim` builds `frontend` with `pnpm install --frozen-lockfile` and `pnpm build`; (2) `python:3.13-slim` runtime runs `uv sync --frozen --no-dev` from `backend/`, copies `frontend/dist` to `/app/static`, sets `PYTHONDONTWRITEBYTECODE=1`, creates `/data` owned by `10001` **before** declaring `VOLUME` (so a fresh named volume is writable), runs as `10001`, and has a `HEALTHCHECK` using Python `urllib` (the slim image has no `curl`). `CMD ["uvicorn", "kairos.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]`; the container binds all interfaces but the host publishes loopback only. `compose.yaml`: port `127.0.0.1:8000:8000`, named volume `kairos-data:/data`, `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `restart: unless-stopped`.
- [ ] **Step 4: Verify.** The unit tests pass, then:
  - `docker compose build` succeeds; `docker compose up -d --wait` reports the service `healthy`.
  - `curl -s http://127.0.0.1:8000/api/health` → `{"status":"ok","version":"0.1.0"}`; `curl -s http://127.0.0.1:8000/` contains `<div id="root">`.
  - `curl -s -o NUL -w "%{http_code}" -H "Host: evil.example" http://127.0.0.1:8000/api/health` → `400`.
  - `docker compose exec kairos id -u` → `10001`; `docker compose exec kairos sh -c "touch /data/.w && echo ok"` → `ok` (fresh volume writable); `docker compose exec kairos sh -c "touch /app/x"` fails (read-only).
  - Record `docker image ls kairos` size and `docker stats --no-stream` memory in the PR description; flag them if the image exceeds 300 MB or idle RAM exceeds 200 MiB.
  - `docker compose down` — never with `-v`.
- [ ] **Step 5: Commit.**

```bash
git add Dockerfile compose.yaml .dockerignore tools/tests/test_compose.py CLAUDE.md docs/bootstrap-tasks.md docs/STATUS.md
git commit -m "build: add multi-stage Docker image and loopback-only compose (BOOT-006)"
```

---

### Task 7: Claude Code hooks and settings (BOOT-007)

**Files:**
- Create: `tools/hooks/guard_bash.py`, `tools/hooks/status_reminder.py`, `tools/hooks/format_on_edit.py`, `.claude/settings.json`
- Test: `tools/tests/test_guard_bash.py`, `tools/tests/test_status_reminder.py`, `tools/tests/test_format_on_edit.py`

Before writing, read the current Claude Code hooks and permissions documentation (event names, stdin JSON fields, exit-code semantics, settings syntax) and follow it; the behavior below is the intent.

**Interfaces:**
- Produces: `check_command(command: str) -> str | None` in `guard_bash.py`: a block reason, or `None`. It blocks, anywhere inside a chained command: `git push` with `--force`, `-f` or `--force-with-lease`; `git push` to `main` (`origin main`, `HEAD:main`); `git add .`, `-A`, `--all`; `git commit` with `--no-verify` or `-n`; `git reset --hard`; `gh pr merge`; `npm`, `npx` or `yarn` invocations (the project uses pnpm); `docker compose down` with `-v` or `--volumes`; `docker volume rm|prune`; `docker system prune`. The hook entry reads the JSON on stdin (`tool_input.command`), prints the reason to stderr and exits `2` when blocked.
- Produces: `needs_status_update(status_mtime: float, changed: dict[str, float]) -> bool` in `status_reminder.py`: `changed` maps changed paths outside `docs/` to their mtimes; true iff any is newer than `status_mtime`. The `Stop` hook exits `2` with a one-line reminder (`Update docs/STATUS.md before finishing`) unless `stop_hook_active` is true.
- Produces: `formatter_for(path: str) -> list[str] | None` in `format_on_edit.py`: `*.py` under `backend/` or `tools/` → `["uv", "run", "--project", "backend", "ruff", "format", "--config", "backend/pyproject.toml", path]` (same config as `check`, so the hook and `check` never disagree); `frontend/**/*.{ts,tsx,json}` → `["pnpm", "--dir", "frontend", "exec", "biome", "format", "--write", path]`; anything else → `None`.
- Produces: `.claude/settings.json` wiring `PreToolUse` on `Bash`, `PostToolUse` on `Edit|Write`, `Stop`; an allow-list for verification and read-only commands (`python tools/check.py`, `uv run *`, `pnpm *`, `git status|diff|log`, `docker compose ps|logs|build|up|down`); deny reading `.env` and `.env.*`; deny `gh pr merge`.

- [ ] **Step 1: Write the failing tests.**

```python
@pytest.mark.parametrize("cmd", [
    "git push --force", "git push -f origin feat/x", "git push origin main",
    "git push origin HEAD:main", "cd x && git push --force-with-lease", "git add .",
    "git add -A", "git commit -m x --no-verify", "git reset --hard HEAD~1",
    "gh pr merge 3 --squash", "docker compose down -v",
    "docker volume rm kairos_kairos-data", "docker system prune -af",
    "npm install", "npx biome check", "yarn add x",
])
def test_blocks_destructive_commands(cmd):
    assert check_command(cmd) is not None

@pytest.mark.parametrize("cmd", [
    "git status", "git push -u origin feat/BOOT-004-x", "git add backend/src/kairos/main.py",
    "python tools/check.py", "docker compose down", "pnpm test", "pnpm install --frozen-lockfile",
    "pnpm exec biome check .", "pnpm dlx some-tool", "git add .github/workflows/ci.yml",
    "git add .claude/settings.json", "git add -- .gitignore", "git push -u origin docs/main-notes",
])
def test_allows_normal_commands(cmd):
    assert check_command(cmd) is None
```

  Also: `test_needs_update_when_code_is_newer_than_status`, `test_no_update_needed_when_status_is_newer`, `test_no_update_needed_without_code_changes`, `test_python_files_use_ruff`, `test_frontend_files_use_biome`, `test_other_files_are_left_alone`.
- [ ] **Step 2: Run to verify they fail.** `uv run --project backend pytest tools/tests -q`.
- [ ] **Step 3: Implement** the three modules and `settings.json`.
- [ ] **Step 4: Verify.** Tests pass. Hook drill: `echo '{"tool_input":{"command":"git push --force"}}' | python tools/hooks/guard_bash.py` → exit `2` with the reason; a harmless command → exit `0`.
- [ ] **Step 5: Commit** (two commits).

```bash
git add tools/hooks tools/tests/test_guard_bash.py tools/tests/test_status_reminder.py tools/tests/test_format_on_edit.py
git commit -m "feat(claude): add guard, status reminder and format hooks (BOOT-007)"
git add .claude/settings.json
git commit -m "chore(claude): wire hooks and permissions in project settings (BOOT-007)"
```

---

### Task 8: Agents, rules and skills (BOOT-007)

**Files:**
- Create: `.claude/agents/orchestrator.md`, `.claude/agents/backend.md`, `.claude/agents/frontend.md`, `.claude/agents/bugs.md`, `.claude/agents/reviewer.md`, `.claude/rules/backend.md`, `.claude/rules/frontend.md`, `.claude/rules/docs.md`, `.claude/skills/update-status/SKILL.md`, `.claude/skills/new-adr/SKILL.md`
- Test: `tools/tests/test_claude_config.py`
- Modify: `CLAUDE.md` (map and hooks)

Read the current docs for the frontmatter keys first (agents: `name`, `description`, `tools`, `model`; rules: `paths`; skills: `name`, `description`).

**Interfaces:**
- `orchestrator`: decides who does what; may triage, assign and reorder; **never** approves, cancels or deletes; enforces the assignment invariants (spec §6.8); runs on demand; has no Kairos tools until stage 1.
- `backend` / `frontend`: own `backend/` / `frontend/`; follow TDD and run `python tools/check.py`; never edit generated types; the frontend keeps strings in the message catalog.
- `bugs`: reproduce with a failing test first, then the smallest fix.
- `reviewer`: read-only; reviews a diff against the spec and the golden rules and reports findings; never merges.
- Rules are path-scoped (`backend/**`, `frontend/**`, `docs/**`) with the conventions from `CLAUDE.md`.
- Skills: `update-status` (how to rewrite `docs/STATUS.md`) and `new-adr` (numbering, template, supersede rule).

- [ ] **Step 1: Write the failing tests** (parse frontmatter with PyYAML): `test_every_agent_has_name_and_description`, `test_agent_name_matches_filename`, `test_every_skill_has_name_and_description`, `test_rules_declare_paths`.
- [ ] **Step 2: Run to verify they fail.** `uv run --project backend pytest tools/tests/test_claude_config.py -q`.
- [ ] **Step 3: Write the files** following the interfaces above; every file is English.
- [ ] **Step 4: Verify.** The tests pass and `python tools/check.py` is green.
- [ ] **Step 5: Commit.**

```bash
git add .claude/agents .claude/rules .claude/skills tools/tests/test_claude_config.py CLAUDE.md
git commit -m "feat(claude): add project agents, path-scoped rules and skills (BOOT-007)"
```

Then push the branch and open the PR (`chore: add Claude Code project configuration (BOOT-007)`).

---

### Task 9: CI, Dependabot and PR template (BOOT-005)

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/pull_request_template.md`
- Modify: `docs/bootstrap-tasks.md`, `docs/STATUS.md`

**Interfaces:**
- Produces: a job named exactly `check` that the `main` ruleset will require.

- [ ] **Step 1: Write `ci.yml`.** Triggers: `pull_request` to `main` and `push` to `main`; `permissions: contents: read`; `concurrency` cancelling in-progress runs per ref. Job `check` on `ubuntu-latest`: checkout, `setup-uv` (cached), `setup-node` 24, pnpm setup (`pnpm/action-setup` pointed at `frontend/package.json` with `package_json_file`, since there is no root `package.json`; `setup-node` cached with `cache-dependency-path: frontend/pnpm-lock.yaml`), `uv sync --frozen` in `backend/`, `pnpm install --frozen-lockfile` in `frontend/`, then `python tools/check.py`. Job `docker`: `docker compose up -d --wait`, `curl --fail http://127.0.0.1:8000/api/health`, `docker compose down`. Use the current major versions of the official actions (verify them).
- [ ] **Step 2: Write `dependabot.yml`:** weekly, limit 5, ecosystems `uv` (`/backend`), `npm` (`/frontend`), `docker` (`/`), `github-actions` (`/`); no `target-branch` (default is `main`).
- [ ] **Step 3: Write `pull_request_template.md`** in English: *What changed*, *Why*, *How it was tested*, task link.
- [ ] **Step 4: Verify locally.** `uv run --project backend python -c "import sys, yaml; [yaml.safe_load(open(p)) for p in sys.argv[1:]]" .github/workflows/ci.yml .github/dependabot.yml` exits `0`; `python tools/check.py` is green.
- [ ] **Step 5: Commit, push, watch.**

```bash
git add .github docs/bootstrap-tasks.md docs/STATUS.md
git commit -m "ci: add check and docker smoke workflow, Dependabot and PR template (BOOT-005)"
git push -u origin ci/BOOT-005-ci
gh pr create --base main --head ci/BOOT-005-ci --body-file <body-file>
gh pr checks --watch
```

  Expected: `check` and `docker` green. The first workflow run must exist before the required check can be selected.
- [ ] **Step 6: Hand the ruleset to the owner.** After the first green run, write the `protect-main` ruleset JSON to the scratchpad (shape from the `git-commit-push` skill §0.5, with `required_linear_history` added and the required status check `check`), show it and the import steps (Settings → Rules → Rulesets → New ruleset → Import a ruleset). Do not create rulesets through the API.
