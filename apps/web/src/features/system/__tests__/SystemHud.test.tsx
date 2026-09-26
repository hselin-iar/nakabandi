import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import SystemHud from "../SystemHud";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import { HUD_BUFFER_MAX, brierTrend, pushSample, recordRun, type MetricsSample } from "../api/useSystemHud";
import type { Permission } from "../../../shared/api/enums.ts";

vi.mock("../../../shared/api/client", () => ({ apiClient: { GET: vi.fn(), POST: vi.fn() } }));

// The file exactly as scripts/evaluate.py writes it when samples are too small: bare NaN.
const EVAL_TEXT = `{"generated_at":"2026-09-26T09:00:00+00:00","as_of":"2026-01-17T10:00:00+00:00","scorer":"hgb_v1",
"metrics":{"n_complaints":17,
"hit_rate_at_1":{"value":NaN,"n":17},"precision_at_1":{"value":NaN,"n":17},
"hit_rate_at_3":{"value":NaN,"n":17},"precision_at_3":{"value":NaN,"n":17},
"hit_rate_at_5":{"value":0.25,"n":40},"precision_at_5":{"value":NaN,"n":17},
"brier_score":{"value":0.0082,"n":2047}}}`;

let verifyResponse: { ok: boolean; first_bad_seq: number | null; head_hash: string | null };

function mockApi() {
  vi.mocked(apiClient.GET).mockImplementation(((path: string) => {
    if (path === "/audit/verify") return Promise.resolve({ data: verifyResponse, error: undefined });
    if (path === "/system/metrics") {
      return Promise.resolve({
        data: {
          generated_at: "2026-09-26T10:00:00Z",
          uptime_s: 3700,
          events_per_second: 4.2,
          complaints_per_second: 1,
          stages: { forecast: { count: 5, p50_ms: 10, p95_ms: 40, max_ms: 90 } },
          http: { count: 50, p50_ms: 5, p95_ms: 22, max_ms: 80 },
          outbox: { pending: 3 },
          delivery_failures: 1,
          streams: {},
        },
        error: undefined,
      });
    }
    if (path === "/analytics/live-metrics") {
      return Promise.resolve({ data: { generated_at: "x", version: 1, window_hours: 24, alert_count: 7, expected_mass: 3.5, active_locations: 4 }, error: undefined });
    }
    return Promise.resolve({ data: undefined, error: new Error("unmocked") });
  }) as unknown as typeof apiClient.GET);
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(EVAL_TEXT, { status: 200 }))));
}

function renderHud(perms: Permission[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <AuthContext.Provider
      value={{
        principal: { user_id: "u", name: "n", role: "admin", scope: {}, permissions: perms },
        isAuthenticated: true,
        can: (p) => perms.includes(p),
        isReady: true,
        login: async () => {},
        logout: async () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <SystemHud />
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  verifyResponse = { ok: true, first_bad_seq: null, head_hash: "abcdef0123456789deadbeef" };
  mockApi();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("SystemHud", () => {
  it("shows the audit chain as intact", async () => {
    renderHud(["VIEW_AUDIT"]);
    const el = await screen.findByTestId("audit-chain-status");
    expect(el.getAttribute("data-ok")).toBe("true");
    expect(screen.getByText("Chain intact")).toBeTruthy();
    expect(screen.getByText(/abcdef0123456789/)).toBeTruthy();
  });

  it("shows a broken chain with the first bad entry", async () => {
    verifyResponse = { ok: false, first_bad_seq: 42, head_hash: null };
    renderHud(["VIEW_AUDIT"]);
    expect(await screen.findByText("Chain broken at entry #42")).toBeTruthy();
    expect(screen.getByTestId("audit-chain-status").getAttribute("data-ok")).toBe("false");
  });

  it("does not crash on an eval file with bare NaN; under-sampled metrics read 'insufficient sample'", async () => {
    renderHud(["VIEW_EVALUATION"]);
    // hit@5 has a real value; hit@1 was NaN
    expect(await screen.findByLabelText("Hit rate @5: 25.0%")).toBeTruthy();
    const hit1 = screen.getByTestId("gauge-Hit rate @1");
    expect(hit1.textContent).toContain("insufficient sample (n=17)");
    expect(hit1.textContent).not.toContain("0.0%");
    expect(screen.getByTestId("hud-brier").textContent).toContain("0.0082");
  });

  it("hides the sections a role may not see", async () => {
    renderHud(["VIEW_EVALUATION"]);
    await screen.findByLabelText("Hit rate @5: 25.0%");
    expect(screen.queryByLabelText("Audit chain integrity")).toBeNull();
    expect(screen.queryByLabelText("Latency and throughput")).toBeNull();
  });

  it("builds latency readouts from /system/metrics", async () => {
    renderHud(["SIM_CONTROL"]);
    await waitFor(() => expect(screen.getByText(/5 \/ 22 \/ 80 ms/)).toBeTruthy());
    expect(screen.getByText("forecast p95")).toBeTruthy();
  });
});

describe("HUD pure helpers", () => {
  const sample = (i: number): MetricsSample => ({ at: String(i), eps: i, httpP95: i, httpP50: i, httpMax: i, stageP95: {}, outboxPending: 0, deliveryFailures: 0, uptimeS: i, complaintsPerS: 0, stages: {}, outbox: {}, streams: { open: 0, max: 0 } });

  it("keeps only the newest HUD_BUFFER_MAX samples", () => {
    let buf: MetricsSample[] = [];
    for (let i = 0; i < HUD_BUFFER_MAX + 5; i++) buf = pushSample(buf, sample(i));
    expect(buf).toHaveLength(HUD_BUFFER_MAX);
    expect(buf[0]!.at).toBe("5");
  });

  it("brier trend: lower is better, needs two distinct runs", () => {
    expect(brierTrend([])).toBeNull();
    let h = recordRun([], { generated_at: "a", brier: 0.02 });
    expect(brierTrend(h)).toBeNull();
    h = recordRun(h, { generated_at: "b", brier: 0.01 });
    expect(brierTrend(h)).toBe("better");
    h = recordRun(h, { generated_at: "c", brier: 0.03 });
    expect(brierTrend(h)).toBe("worse");
    // the same run seen again is not a new run
    expect(recordRun(h, { generated_at: "c", brier: 0.03 })).toHaveLength(3);
  });
});
