// Message catalog: every UI string lives here so another language can be added later.
export const messages = {
  appName: "Kairos",
  serverConnected: (version: string) => `Server connected · v${version}`,
} as const;
