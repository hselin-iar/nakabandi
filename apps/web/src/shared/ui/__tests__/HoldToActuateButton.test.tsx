import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HoldToActuateButton } from "../HoldToActuateButton";

afterEach(cleanup);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("HoldToActuateButton", () => {
  it("does nothing if released before the hold completes", async () => {
    const onActuate = vi.fn();
    render(<HoldToActuateButton label="Freeze" durationMs={300} onActuate={onActuate} />);
    const btn = screen.getByRole("button");
    fireEvent.pointerDown(btn, { button: 0, pointerType: "mouse" });
    await sleep(100);
    fireEvent.pointerUp(btn);
    await sleep(400);
    expect(onActuate).not.toHaveBeenCalled();
  });

  it("fires exactly once when held to completion", async () => {
    const onActuate = vi.fn();
    render(<HoldToActuateButton label="Freeze" durationMs={200} onActuate={onActuate} />);
    const btn = screen.getByRole("button");
    fireEvent.pointerDown(btn, { button: 0, pointerType: "mouse" });
    await waitFor(() => expect(onActuate).toHaveBeenCalledTimes(1));
    await sleep(300);
    expect(onActuate).toHaveBeenCalledTimes(1);
  });

  it("works from the keyboard (hold Space) and cancels on key up", async () => {
    const onActuate = vi.fn();
    render(<HoldToActuateButton label="Freeze" durationMs={200} onActuate={onActuate} />);
    const btn = screen.getByRole("button");
    fireEvent.keyDown(btn, { key: " " });
    await sleep(60);
    fireEvent.keyUp(btn, { key: " " });
    await sleep(300);
    expect(onActuate).not.toHaveBeenCalled();

    fireEvent.keyDown(btn, { key: " " });
    await waitFor(() => expect(onActuate).toHaveBeenCalledTimes(1));
  });

  it("ignores presses while disabled or loading", async () => {
    const onActuate = vi.fn();
    const { rerender } = render(<HoldToActuateButton label="Freeze" durationMs={50} onActuate={onActuate} disabled />);
    fireEvent.pointerDown(screen.getByRole("button"), { button: 0, pointerType: "mouse" });
    rerender(<HoldToActuateButton label="Freeze" durationMs={50} onActuate={onActuate} loading />);
    fireEvent.pointerDown(screen.getByRole("button"), { button: 0, pointerType: "mouse" });
    await sleep(200);
    expect(onActuate).not.toHaveBeenCalled();
  });
});
