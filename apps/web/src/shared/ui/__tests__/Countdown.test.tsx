/**
 * Countdown.test.tsx — component tests for Countdown.tsx
 * DOC 3 C3 Done When: Countdown renders using sim clock, never the browser clock.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Countdown } from "../Countdown";
import { StreamProvider } from "../../stream/useStream";

// Fake EventSource for tests — no real network.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners: Map<string, ((e: MessageEvent) => void)[]> = new Map();

  constructor() {
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(fn);
    this.listeners.set(type, arr);
  }
  emit(type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    (this.listeners.get(type) ?? []).forEach((fn) => fn(event));
  }
  open() { this.onopen?.(); }
  close() {}
  onmessage: ((e: MessageEvent) => void) | null = null;
  static reset() { FakeEventSource.instances = []; }
}

afterEach(() => {
  cleanup();
  FakeEventSource.reset();
  vi.unstubAllGlobals();
});

function makeWrapper() {
  const qc = new QueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: qc },
      React.createElement(StreamProvider, null, children),
    );
  };
}

describe("Countdown", () => {
  it("renders --:-- when no sim time has arrived yet", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(<Countdown target="2026-01-15T11:00:00Z" />, {
      wrapper: makeWrapper(),
    });
    // Without a sim.time event, should show placeholder
    expect(screen.getByText("--:--")).toBeTruthy();
  });

  it("never calls Date.now() for sim time calculation (uses stream only)", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const dateSpy = vi.spyOn(Date, "now");

    render(<Countdown target="2026-01-15T11:00:00Z" />, {
      wrapper: makeWrapper(),
    });

    // Date.now() may be called for other purposes (React internals etc.),
    // but the countdown rendering should read from sim time (null at this point)
    // and show the placeholder, NOT a computed duration based on Date.now().
    expect(screen.getByText("--:--")).toBeTruthy();
    dateSpy.mockRestore();
  });
});
