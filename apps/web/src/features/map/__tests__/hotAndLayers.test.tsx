import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { hotCellsToGeoJSON, pickHotCells, MAX_HOT_RADARS } from "../layers/radarIconLayer";
import { LayerPanel, type LayerKey } from "../LayerPanel";
import type { HeatCell } from "../types";

afterEach(cleanup);

const cell = (id: string, value: number): HeatCell => ({ id, kind: "cell", name: id, lat: 19, lon: 73, value, alert_count: 0 });

describe("pickHotCells", () => {
  it("animates at most the top few, hottest first", () => {
    const cells = ["a", "b", "c", "d", "e"].map((id, i) => cell(id, 0.6 + i * 0.05));
    const hot = pickHotCells(cells);
    expect(hot).toHaveLength(MAX_HOT_RADARS);
    expect(hot.map((c) => c.id)).toEqual(["e", "d", "c"]);
  });

  it("ignores cells that are not genuinely elevated", () => {
    expect(pickHotCells([cell("x", 0.2), cell("y", 0.49)])).toHaveLength(0);
    expect(hotCellsToGeoJSON([cell("x", 0.2)]).features).toHaveLength(0);
  });

  it("emits point features at [lon, lat]", () => {
    const f = hotCellsToGeoJSON([cell("x", 0.9)]).features[0]!;
    expect((f.geometry as GeoJSON.Point).coordinates).toEqual([73, 19]);
  });
});

describe("LayerPanel", () => {
  const on: Record<LayerKey, boolean> = { heat: true, locations: false, alerts: true, route: true, boundaries: true };

  it("shows each layer with its live count and hotkey, and reports toggles", () => {
    const onToggle = vi.fn();
    render(
      <LayerPanel
        rows={[
          { key: "heat", name: "Risk heat", hotkey: "H", count: 12, note: "+3 hidden" },
          { key: "locations", name: "Locations", hotkey: "L", count: 40 },
          { key: "boundaries", name: "Boundaries", hotkey: "B", count: null },
        ]}
        on={on}
        onToggle={onToggle}
      />,
    );
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("+3 hidden")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Locations/ }).getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: /Risk heat/ }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: /Locations/ }));
    expect(onToggle).toHaveBeenCalledWith("locations");
  });
});
