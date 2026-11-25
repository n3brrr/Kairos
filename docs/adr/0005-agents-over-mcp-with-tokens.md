# ADR-0005: Agents connect over MCP with one token per agent

- **Status:** proposed (pending spike BOOT-003)
- **Date:** 2026-11-26

## Context

The owner runs Claude Code on a Claude Pro subscription (quota, no API key). Agents must be identifiable, see only their own tasks, and be unable to approve, cancel or delete. Kairos must not call the Anthropic API.

## Decision

Kairos exposes an **MCP server over Streamable HTTP** at `/mcp`, mounted in the same FastAPI process. Each agent has its own random token (`kai_…`, 256 bits), stored only as a hash, with a scope (specialty, allowed task types and projects) and revocable. Claude Code sends it as `Authorization: Bearer ${KAIROS_TOKEN}` from `.mcp.json`, with the token in an environment variable. The server validates `Origin` and `Host` (DNS-rebinding protection) and listens on `127.0.0.1` only.

## Open questions (the spike answers them)

1. Does Claude Code attach the `Authorization` header from a project `.mcp.json` on Windows? Public reports describe the header being ignored when the server also advertises OAuth.
2. Can a subagent carry its own token, or does it inherit the session's MCP connection? This decides whether "one agent" means "one Claude Code session".

## Consequences

- If the spike fails, fall back to a thin stdio MCP proxy that injects the token (documented and tested), or to an environment-variable-selected identity.
- This ADR is replaced by an *accepted* one once the spike is done.
