import { render, screen } from "@testing-library/react";
import { App } from "./App";
import { api } from "./api/client";
import { messages } from "./messages";

it("renders the app name from the message catalog", () => {
  vi.spyOn(api, "GET").mockResolvedValue({ data: { status: "ok", version: "0.1.0" } } as never);
  render(<App />);
  expect(screen.getByRole("heading", { name: messages.appName })).toBeInTheDocument();
});

it("shows the server version once the health check answers", async () => {
  vi.spyOn(api, "GET").mockResolvedValue({ data: { status: "ok", version: "0.1.0" } } as never);
  render(<App />);
  expect(await screen.findByText(messages.serverConnected("0.1.0"))).toBeInTheDocument();
});
