/**
 * MapPage.test.tsx — Unit & component tests for GIS Risk Heatmap Dashboard.
 * DOC 3 M3 / DOC 4 Step C5 Done When:
 *   - MapPage renders the four states from bundled GeoJSON with no network request;
 *   - filter changes debounce and refetch;
 *   - forcing a WebGL failure falls back to the table view with the same data;
 *   - moving the time slider pauses live updates and shows "return to live".
 */

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MapPage from "../MapPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/types.ts";
import { MapLibreAdapter } from "../maplibre/MapLibreAdapter";
import { apiClient } from "../../../shared/api/client";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const mockOfficerPrincipal: Principal = {
  user_id: "USR-MAP-01",
  name: "officer_map",
  role: "district_officer",
  scope: { state_id: "DL" },
  permissions: ["VIEW_ALERTS"],
};

// Test-only fixture — production no longer carries one (DOC1 §1.0). Mirrors the shape
// GET /analytics/heatmap returns; the mock GET below applies the same state/min_confidence
// filtering the real server does, so these tests exercise MapPage's actual query-building.
const TEST_HEATMAP_CELLS = [
  { id: "C+0107_+0309", kind: "cell", name: "Connaught Place Hub (DL/UP)", lat: 28.63, lon: 77.22, value: 0.94, alert_count: 8 },
  { id: "C+0076_+0291", kind: "cell", name: "Bandra-Kurla Complex (MH)", lat: 19.07, lon: 72.87, value: 0.82, alert_count: 7 },
  { id: "C+0080_+0316", kind: "cell", name: "Nagpur Central (MH)", lat: 21.15, lon: 79.09, value: 0.67, alert_count: 4 },
  { id: "C+0113_+0308", kind: "cell", name: "Cyber City Gurugram (HR)", lat: 28.49, lon: 77.09, value: 0.91, alert_count: 9 },
  { id: "C+0093_+0341", kind: "cell", name: "Ranchi Central Corridor (JH)", lat: 23.34, lon: 85.31, value: 0.69, alert_count: 4 },
];

function mockApiForMapPage() {
  vi.mocked(apiClient.GET).mockImplementation(((
    path: string,
    opts?: { params?: { query?: Record<string, unknown> } },
  ) => {
    if (path === "/analytics/heatmap") {
      const q = opts?.params?.query ?? {};
      let cells = [...TEST_HEATMAP_CELLS];
      if (typeof q.state === "string") {
        const st = q.state.toUpperCase();
        cells = cells.filter((c) => c.name.includes(`(${st}`) || c.name.includes(`/${st}`));
      }
      if (typeof q.min_confidence === "number") {
        const minConfidence = q.min_confidence;
        cells = cells.filter((c) => c.value >= minConfidence);
      }
      return Promise.resolve({
        data: {
          layer: (q.layer as string) ?? "live",
          level: (q.level as string) ?? "cell",
          generated_at: "2026-01-15T12:00:00Z",
          version: 1,
          cells,
          suppressed_count: 0,
          legend: {
            min: 0,
            max: 1,
            unit: "Forecast Intensity (Mass)",
            // Matches the real backend's LIVE_NOTE (analytics/application/queries.py) —
            // this exact string only ever existed client-side in the fixture this test used
            // to exercise; the real API has never said "real-time active forecast intensity".
            note: "Expected cash-out mass behind alerts raised in this window.",
          },
        },
        error: undefined,
      });
    }
    if (path === "/alerts") {
      return Promise.resolve({ data: { items: [], next_cursor: null }, error: undefined });
    }
    if (path === "/geo/locations") {
      return Promise.resolve({ data: [], error: undefined });
    }
    if (path === "/geo/regions") {
      return Promise.resolve({ data: [], error: undefined });
    }
    return Promise.resolve({ data: undefined, error: undefined });
  }) as unknown as typeof apiClient.GET);
}

beforeEach(() => {
  mockApiForMapPage();
});

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <AuthContext.Provider
      value={{
        principal: mockOfficerPrincipal,
        isAuthenticated: true,
        can: (p) => mockOfficerPrincipal.permissions.includes(p),
        isReady: true,
        login: async () => {},
        logout: async () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/map"]}>
          {ui}
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MapPage & Risk Heatmap Dashboard (Step C5)", () => {
  it("renders the dashboard and falls back to TableView on WebGL absence without blank canvas", async () => {
    // In JSDOM, WebGL context is null by default
    renderWithProviders(<MapPage />);

    expect(screen.getByText("GIS Risk Heatmap Dashboard")).toBeTruthy();
    expect(
      screen.getByText(/Spatial forecast intensity & persistence rollups across UP, MH, HR, and JH/i),
    ).toBeTruthy();

    // Table fallback banner
    expect(await screen.findByText(/Tabular Risk View/i)).toBeTruthy();

    // Table displays cells across the four demo states
    expect(await screen.findByText("Connaught Place Hub (DL/UP)")).toBeTruthy();
    expect(screen.getByText("Bandra-Kurla Complex (MH)")).toBeTruthy();
    expect(screen.getByText("Ranchi Central Corridor (JH)")).toBeTruthy();
    expect(screen.getByText("Cyber City Gurugram (HR)")).toBeTruthy();

    // Legend renders
    expect(screen.getByText(/Fraud Risk Density|Forecast Risk Intensity/i)).toBeTruthy();
    expect(await screen.findByText(/Expected cash-out mass behind alerts raised/i)).toBeTruthy();
  });

  it("filters heatmap cells by state dropdown", async () => {
    renderWithProviders(<MapPage />);
    await screen.findByText("Bandra-Kurla Complex (MH)");

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Filter by state"));
    await user.click(await screen.findByRole("option", { name: /Maharashtra \(MH\)/i }));

    // Maharashtra cells should remain
    expect(await screen.findByText("Bandra-Kurla Complex (MH)")).toBeTruthy();
    expect(screen.getByText("Nagpur Central (MH)")).toBeTruthy();

    // Other state cells should be excluded after debounce resolves
    await waitFor(() => {
      expect(screen.queryByText("Ranchi Central Corridor (JH)")).toBeNull();
      expect(screen.queryByText("Cyber City Gurugram (HR)")).toBeNull();
    });
  });

  it("filters heatmap cells by minimum confidence threshold", async () => {
    renderWithProviders(<MapPage />);
    await screen.findByText("Connaught Place Hub (DL/UP)");

    // Filter to >= 90% (0.9)
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Filter by min confidence"));
    await user.click(await screen.findByRole("option", { name: /90% Critical Only/i }));

    // Connaught Place is 94% (0.94) -> remains
    expect(await screen.findByText("Connaught Place Hub (DL/UP)")).toBeTruthy();

    // Bandra is 82% (0.82) -> excluded
    await waitFor(() => {
      expect(screen.queryByText("Bandra-Kurla Complex (MH)")).toBeNull();
    });
  });

  it("moving time slider pauses live updates and shows 'Return to Live' button", async () => {
    renderWithProviders(<MapPage />);

    expect(screen.getByText("Live Ingestion")).toBeTruthy();
    expect(screen.queryByText(/Return to Live/i)).toBeNull();

    const slider = screen.getByLabelText("Replay time offset hours");
    // Move slider to 12 hours ago (-12)
    fireEvent.change(slider, { target: { value: "-12" } });

    expect(screen.getByText("Replay Mode (Paused)")).toBeTruthy();
    expect(screen.getByText(/12h ago/i)).toBeTruthy();

    const returnBtn = screen.getByRole("button", { name: /Return to Live/i });
    expect(returnBtn).toBeTruthy();

    // Click Return to Live to resume
    fireEvent.click(returnBtn);

    expect(screen.getByText("Live Ingestion")).toBeTruthy();
    expect(screen.queryByText(/Return to Live/i)).toBeNull();
  });

  it("inspecting a cell opens HotspotDrawer with contributing alert trajectories", async () => {
    renderWithProviders(<MapPage />);

    const inspectBtn = await screen.findByLabelText("Inspect C+0107_+0309");
    fireEvent.click(inspectBtn);

    // HotspotDrawer opens
    expect(
      await screen.findByText(/Hotspot · Connaught Place Hub/i),
    ).toBeTruthy();
    expect(screen.getByText("Risk Score (p120)")).toBeTruthy();
    expect(
      await screen.findByText(/Contributing Active Trajectories/i),
    ).toBeTruthy();
  });

  it("switches to map view when WebGL is supported", async () => {
    // Stub MapLibreAdapter.isSupported to return true
    vi.spyOn(MapLibreAdapter, "isSupported").mockReturnValue(true);

    // Mock MapLibreAdapter.prototype.init to resolve cleanly
    vi.spyOn(MapLibreAdapter.prototype, "init").mockImplementation(async () => {});
    vi.spyOn(MapLibreAdapter.prototype, "destroy").mockImplementation(() => {});

    renderWithProviders(<MapPage />);

    expect(screen.getByTestId("maplibre-container")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Map View/i }).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});
