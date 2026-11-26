import { manifest, navigateFallbackDenylist } from "./pwa-manifest";

it("declares an installable desktop manifest", () => {
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.icons?.map((i) => i.sizes)).toEqual(
    expect.arrayContaining(["192x192", "512x512"]),
  );
});

describe("service worker navigation fallback", () => {
  const denied = (path: string) => navigateFallbackDenylist.some((re) => re.test(path));

  it.each(["/api/health", "/api", "/mcp", "/docs", "/redoc", "/openapi.json"])(
    "does not answer %s with the app page",
    (path) => {
      expect(denied(path)).toBe(true);
    },
  );

  it.each(["/", "/boards/1", "/apiary", "/documents"])("still serves the app for %s", (path) => {
    expect(denied(path)).toBe(false);
  });
});
