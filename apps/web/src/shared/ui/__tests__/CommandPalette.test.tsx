import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette, type PaletteGroup } from "../CommandPalette";

afterEach(cleanup);

function groups(onSelect = vi.fn()): PaletteGroup[] {
  return [
    {
      heading: "Accounts",
      items: [
        { id: "a1", label: "XXXX-4471", hint: "SBIN", keywords: ["SBIN", "CLU-MH-1"], onSelect },
        { id: "a2", label: "XXXX-9902", hint: "HDFC", keywords: ["HDFC", "CLU-DL-2"], onSelect: vi.fn() },
      ],
    },
    { heading: "Empty group", items: [] },
  ];
}

describe("CommandPalette", () => {
  it("finds a masked account ref by its own text", async () => {
    render(<CommandPalette open onOpenChange={() => {}} groups={groups()} />);
    await userEvent.setup().keyboard("4471");
    expect(screen.getByText("XXXX-4471")).toBeTruthy();
    expect(screen.queryByText("XXXX-9902")).toBeNull();
  });

  it("finds accounts by a bank code that is not shown as their label", async () => {
    render(<CommandPalette open onOpenChange={() => {}} groups={groups()} />);
    await userEvent.setup().keyboard("HDFC");
    expect(screen.getByText("XXXX-9902")).toBeTruthy();
    expect(screen.queryByText("XXXX-4471")).toBeNull();
  });

  it("runs the selected item and closes", async () => {
    const onSelect = vi.fn();
    const onOpenChange = vi.fn();
    render(<CommandPalette open onOpenChange={onOpenChange} groups={groups(onSelect)} />);
    const user = userEvent.setup();
    await user.keyboard("4471");
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("hides empty groups and reports no matches", async () => {
    render(<CommandPalette open onOpenChange={() => {}} groups={groups()} />);
    expect(screen.queryByText("Empty group")).toBeNull();
    await userEvent.setup().keyboard("zzzzzz");
    expect(screen.getByText("Nothing matches.")).toBeTruthy();
  });
});
