import { describe, expect, it } from "vitest";
import { distanceKm, threatLevel, toDms } from "../IntelPopup";

describe("IntelPopup helpers", () => {
  it("bands a 0..1 risk value into threat levels", () => {
    expect(threatLevel(0)).toBe("NEGLIGIBLE");
    expect(threatLevel(0.2)).toBe("ELEVATED");
    expect(threatLevel(0.5)).toBe("HIGH");
    expect(threatLevel(0.85)).toBe("SEVERE");
  });

  it("formats degrees-minutes-seconds with the right hemisphere", () => {
    expect(toDms(28.6139, "N", "S")).toBe("28°36′50″N");
    expect(toDms(-33.8688, "N", "S")).toBe("33°52′08″S");
    expect(toDms(77.209, "E", "W")).toBe("77°12′32″E");
  });

  it("measures great-circle distance in km", () => {
    expect(distanceKm(28.6139, 77.209, 28.6139, 77.209)).toBe(0);
    // Delhi to Mumbai is about 1,150 km
    expect(distanceKm(28.6139, 77.209, 19.076, 72.8777)).toBeGreaterThan(1100);
    expect(distanceKm(28.6139, 77.209, 19.076, 72.8777)).toBeLessThan(1200);
  });
});
