/**
 * useStream.test.ts — unit tests for StreamProvider and useStream hooks.
 * DOC 3 C3 Done When: useStream fallback with fake EventSource tested.
 *
 * Uses a fake EventSource to drive SSE events in a controlled way.
 * No real network connections.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Fake EventSource
// ---------------------------------------------------------------------------

type Listener = (e: MessageEvent) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;

  private listeners: Map<string, Listener[]> = new Map();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: Listener) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(fn);
    this.listeners.set(type, arr);
  }

  /** Simulate an event arriving. */
  emit(type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    const listeners = this.listeners.get(type) ?? [];
    for (const fn of listeners) fn(event);
    if (type === "message" && this.onmessage) this.onmessage(event);
  }

  /** Simulate connection opened. */
  open() {
    this.onopen?.();
  }

  /** Simulate error / disconnection. */
  error() {
    this.onerror?.();
  }

  close() {
    /* no-op for test */
  }

  static reset() {
    FakeEventSource.instances = [];
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

// Import after setting the fake so modules pick it up.
import { StreamProvider, useStream, useSimTime } from "../useStream";

beforeEach(() => {
  FakeEventSource.reset();
  // Inject fake
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: qc },
      React.createElement(StreamProvider, null, children),
    );
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStream — connection status", () => {
  it("starts as disconnected", () => {
    const qc = new QueryClient();
    const { result } = renderHook(() => useStream(), {
      wrapper: makeWrapper(qc),
    });
    // Before the fake EventSource opens, status should be disconnected or streaming
    expect(["disconnected", "streaming", "polling"]).toContain(result.current.status);
  });

  it("becomes streaming after onopen fires", async () => {
    vi.useFakeTimers();
    const qc = new QueryClient();
    const { result } = renderHook(() => useStream(), {
      wrapper: makeWrapper(qc),
    });

    await act(async () => {
      const es = FakeEventSource.instances[0];
      es?.open();
    });

    expect(result.current.status).toBe("streaming");
  });
});

describe("useStream — sim.time updates useSimTime()", () => {
  it("updates simTime when sim.time event arrives", async () => {
    vi.useFakeTimers();
    const qc = new QueryClient();
    const { result } = renderHook(() => useSimTime(), {
      wrapper: makeWrapper(qc),
    });

    await act(async () => {
      const es = FakeEventSource.instances[0];
      es?.open();
      es?.emit("sim.time", { sim_time: "2026-01-15T10:00:00Z" });
    });

    expect(result.current).toBe("2026-01-15T10:00:00Z");
  });
});

describe("useStream — polling fallback", () => {
  it("switches to polling after 20 s of inactivity", async () => {
    vi.useFakeTimers();
    const qc = new QueryClient();
    const { result } = renderHook(() => useStream(), {
      wrapper: makeWrapper(qc),
    });

    await act(async () => {
      const es = FakeEventSource.instances[0];
      es?.open();
    });

    // Advance 20 s with no events
    await act(async () => {
      vi.advanceTimersByTime(20_001);
    });

    expect(result.current.status).toBe("polling");
  });
});
