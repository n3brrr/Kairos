# ADR-0005: Agents connect over MCP with one token per agent

- **Status:** accepted (spike BOOT-003, 2026-11-26)
- **Date:** 2026-11-26

## Context

The owner runs Claude Code on a Claude Pro subscription (quota, no API key). Agents must be identifiable, see only their own tasks, and be unable to approve, cancel or delete. Kairos must not call the Anthropic API.

## Decision

Kairos exposes an **MCP server over Streamable HTTP** at `/mcp`, mounted in the same FastAPI process. Each agent has its own random token (`kai_…`, 256 bits), stored only as a hash, with a scope (specialty, allowed task types and projects) and revocable. Claude Code sends it as `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json`, with the token in an environment variable. The server validates `Origin` and `Host` (DNS-rebinding protection) and listens on `127.0.0.1` only.

The spike confirmed this works on Windows with Claude Code 2.1.332. The exact `.mcp.json` shape that works:

```json
{ "mcpServers": { "kairos": { "type": "http", "url": "http://127.0.0.1:8765/mcp",
  "headers": { "Authorization": "Bearer ${KAIROS_TOKEN}" } } } }
```

**Identity model: one agent = one Claude Code session.** The session's token comes from `KAIROS_TOKEN`. By default, subagents of that session share its identity and Kairos only records which subagent acted, as a `via` label (attribution, no extra permissions).

**A subagent may carry its own token**, as an opt-in, when all of these hold (each one observed in the spike):

1. The subagent declares an inline MCP server (`mcpServers` in its frontmatter, or the `--agents` option) with its own `Authorization` header, for example `Bearer ${KAIROS_TOKEN_BETA}`. `${VAR}` is expanded there.
2. That inline server has a **name different from the session's** (for example `kairos_beta`, not `kairos`). Tools are routed by their `mcp__<server>__<tool>` name: with the same name the subagent's calls go through the session's connection and carry the session's identity. The subagent must then be told to use the `mcp__kairos_beta__*` tools.
3. For an agent file under the project's `.claude/agents/`, the folder must be trusted. Otherwise Claude Code skips the inline servers of that file and only logs it at debug level (see Results, row 5).

Per-subagent tokens give **attribution, not isolation**: both tokens are environment variables of the same Claude Code process, so the parent session can read them. They are not a privilege boundary against the session that owns them.

## Results

All runs on Windows 11 Pro (10.0.26300), Claude Code 2.1.332, Python 3.13.1, `mcp` 2.3.0, uvicorn 0.54.0, uv 0.13.10. The spike server logged the identity of every request, which corroborates what the session printed. `claude -p` runs used `--model haiku` to save quota and `--settings approve.json` (content: `{"enabledMcpjsonServers": ["kairos"]}`) to approve the project server, because a project `.claude/settings.local.json` is ignored in an untrusted folder and `claude mcp list` otherwise shows `⏸ Pending approval`.

| # | Experiment | Command | Observed output | Claude Code |
|---|---|---|---|---|
| 1 | A: header from `.mcp.json`, alpha | `KAIROS_TOKEN=kai_spike_alpha`; `claude -p "Call the whoami tool of the kairos MCP server and print only its result" --allowedTools "mcp__kairos__whoami" --settings approve.json --model haiku` | `agent-alpha` | 2.1.332 |
| 2 | A: header from `.mcp.json`, beta | same, `KAIROS_TOKEN=kai_spike_beta` | `agent-beta` | 2.1.332 |
| 3 | A: wrong token | `KAIROS_TOKEN=kai_spike_wrong`; `claude --settings approve.json mcp list` | `kairos: … ✘ Failed to connect — Server rejected the configured Authorization header (HTTP 401). … OAuth fallback is disabled when headers.Authorization is set.` The server log shows only `401` responses, so no tool was reached | 2.1.332 |
| 4 | A: variable unset | `claude --settings approve.json mcp list` without `KAIROS_TOKEN` | Same failure as row 3, plus the warning `Missing environment variables: KAIROS_TOKEN`. An `Authorization` header was sent and rejected (the docs say the literal `${KAIROS_TOKEN}` is sent) | 2.1.332 |
| 5 | B as written: agent file `.claude/agents/spike-beta.md` with `mcpServers: - kairos: {type: http, url, headers: Authorization: Bearer ${KAIROS_TOKEN_BETA}}`; session on alpha, `KAIROS_TOKEN_BETA=kai_spike_beta` | `claude -p "… call whoami yourself … use the spike-beta subagent …" --allowedTools "mcp__kairos__whoami" --settings approve.json --model haiku` | `self: agent-alpha`, `spike-beta: agent-alpha`. The server never saw `agent-beta`. Debug log: `Skipping frontmatter MCP servers for agent 'spike-beta': the folder its definition file came from is not trusted (source: projectSettings)` | 2.1.332 |
| 6 | B, bypassing the folder-trust rule with `--agents` (inline server named `kairos`, same as the session's) | same prompt, plus `--agents agents-cli.json` and a third line for `spike-cli` | `spike-cli: agent-alpha`. Debug log: `[Agent: spike-cli] Connected to MCP server 'kairos' with 1 tools` and the server saw 3 requests as `agent-beta` (the beta header was sent), but the `whoami` call went out through the session's `kairos` connection and the server saw it as `agent-alpha` | 2.1.332 |
| 7 | B with a distinct server name (`kairos_beta`) via `--agents agents-cli2.json` | `claude -p "… call whoami yourself … use the spike-cli subagent …" --allowedTools "mcp__kairos__whoami" "mcp__kairos_beta__whoami" --settings approve.json --agents agents-cli2.json --model haiku --debug-file debug-b3.log` | `self: agent-alpha`, `spike-cli: agent-beta`. Debug log: `MCP server "kairos_beta": Calling MCP tool: whoami`; server log: last request as `agent-beta` | 2.1.332 |
| 8 | Server hardening (curl, no quota) | `POST /mcp` without token; with `Origin: http://evil.example`; with `Host: evil.example` | `401`, `403 Invalid Origin header`, `421 Invalid Host header` | n/a |
| 9 | Identity is per request, not per session (curl, no quota) | initialize with alpha, then `tools/call whoami` on the same session id with the beta token | `agent-beta` (a `ContextVar` set by the auth middleware is correct on every request) | n/a |

5 of the 6 allowed `claude -p` calls were used (rows 1, 2, 5, 6, 7).

Not tested, so not claimed:

- The agent-file route with the folder trusted. Row 5 is skipped for lack of trust; the docs say trusted project agent files load their inline servers, and rows 6 and 7 show the mechanism works through `--agents`. Verifying the file route needs the folder trusted in `~/.claude.json`, which the spike did not touch.
- `claude -p` without `--settings approve.json`. The docs say headless runs load project servers without asking; the spike always passed the approval setting.
- Servers that also advertise OAuth. The spike server does not, so the public reports of the header being ignored in that case are neither confirmed nor ruled out. The documented behavior is that a configured `Authorization` header disables the OAuth fallback (row 3 text).

## Consequences

- Stage 1 builds the MCP server as designed. Identity comes from the `Authorization` header on every request (a `ContextVar` or the request object), never from MCP session state: in the spike Claude Code (negotiated protocol `2026-07-28`) sent no `Mcp-Session-Id` header on any request.
- The `.mcp.json` shape above is the one to commit to the repo from stage 1, with `KAIROS_TOKEN` in the environment. `claude mcp list` is the health check; a missing variable shows up as a failed server plus a `Missing environment variables` warning.
- Project `.mcp.json` servers need approval. In an untrusted folder, a project `.claude/settings.local.json` does not approve them; use the interactive prompt once, or `--settings`, user settings or managed settings for unattended runs.
- Subagents share the session identity by default (events carry `via`). Per-subagent tokens are supported under the three conditions in the Decision and give attribution only; the role design (`.claude/agents/`) must give each such subagent a server name distinct from `kairos` and tool names to match.
- The thin stdio proxy fallback is not needed. It stays documented as the escape hatch if a future Claude Code release stops sending the header.
- Token variable names must avoid the ones Claude Code treats as credentials in remote headers (`ANTHROPIC_API_KEY`, `NPM_TOKEN` and similar read as empty, per the docs). `KAIROS_TOKEN` and `KAIROS_TOKEN_BETA` expanded correctly.
