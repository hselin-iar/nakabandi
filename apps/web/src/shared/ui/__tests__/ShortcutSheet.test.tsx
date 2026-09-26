import { afterEach, beforeEach, describe, it, expect } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShortcutSheet } from "../ShortcutSheet";
import { registerShortcuts, setShortcutSheetOpen } from "../shortcutRegistry";

describe("ShortcutSheet", () => {
  beforeEach(() => setShortcutSheetOpen(false));
  afterEach(cleanup);

  it("opens on ? and closes on Escape", async () => {
    const user = userEvent.setup();
    render(<ShortcutSheet />);
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.keyboard("?");
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists registered scopes and drops them when unregistered", async () => {
    const user = userEvent.setup();
    const unregister = registerShortcuts({
      scope: "test-scope",
      title: "Test scope",
      entries: [{ keys: "J / K", description: "Move selection" }],
    });
    render(<ShortcutSheet />);
    await user.keyboard("?");
    expect(screen.getByText("Test scope")).toBeTruthy();
    expect(screen.getByText("Move selection")).toBeTruthy();
    unregister();
    await user.keyboard("{Escape}");
    await user.keyboard("?");
    expect(screen.queryByText("Test scope")).toBeNull();
  });

  it("ignores ? while a form field has focus", async () => {
    const user = userEvent.setup();
    render(
      <>
        <input aria-label="filter" />
        <ShortcutSheet />
      </>,
    );
    await user.click(screen.getByLabelText("filter"));
    await user.keyboard("?");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
