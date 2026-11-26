import { render, screen } from "@testing-library/react";
import { App } from "./App";
import { messages } from "./messages";

it("renders the app name from the message catalog", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: messages.appName })).toBeInTheDocument();
});
