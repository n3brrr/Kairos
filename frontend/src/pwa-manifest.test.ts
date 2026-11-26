import { manifest } from "./pwa-manifest";

it("declares an installable desktop manifest", () => {
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.icons?.map((i) => i.sizes)).toEqual(
    expect.arrayContaining(["192x192", "512x512"]),
  );
});
