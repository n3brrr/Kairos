import type { ManifestOptions } from "vite-plugin-pwa";

const DARK = "#0f1115";

export const manifest: Partial<ManifestOptions> = {
  name: "Kairos",
  short_name: "Kairos",
  lang: "en",
  display: "standalone",
  start_url: "/",
  theme_color: DARK,
  background_color: DARK,
  icons: [
    { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
  ],
};
