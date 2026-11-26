---
paths:
  - "frontend/**"
---

# Frontend conventions

- **pnpm only**: install, run, exec and dlx. Never `npm`, `npx`, `yarn` or a `package-lock.json`.
- React + Vite + strict TypeScript. Tests with Vitest and Testing Library; write the failing test first.
- UI strings live in `src/messages.ts`. No hardcoded text in components.
- `src/api/schema.d.ts` is generated from OpenAPI: never edit it by hand. Call the backend through `src/api/client.ts`.
- Biome (recommended rules) must be clean; it ignores the generated schema file.
- Dark theme, desktop PWA. Keep `/api`, `/mcp` and the API docs out of the service worker's navigation fallback (`src/pwa-manifest.ts`).
- TypeScript stays on 5.x until `openapi-typescript` supports a newer major.
