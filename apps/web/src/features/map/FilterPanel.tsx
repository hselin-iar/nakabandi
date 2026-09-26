/**
 * FilterPanel.tsx — Accessible filter controls for the risk heatmap dashboard.
 * DOC 3 M3: "Filters: { layer: live|potential, level: district|cell|location, state?, district?, category?... }"
 */

import React from "react";
import { Select } from "../../shared/ui/Select";
import type { HeatmapFilters, HeatmapLevel, Region } from "./types";
import { Icon } from "../../shared/ui/Icon";

interface FilterPanelProps {
  filters: HeatmapFilters;
  regions: Region[];
  onChange: (updated: Partial<HeatmapFilters>) => void;
  onReset: () => void;
}

export function FilterPanel({
  filters,
  regions,
  onChange,
  onReset,
}: FilterPanelProps) {
  const states = regions.filter((r) => r.level === "state");
  const availableDistricts = regions.filter(
    (r) => r.level === "district" && (!filters.state || r.parent_id === filters.state),
  );

  return (
    <div className="nk-map-filters" role="search" aria-label="Heatmap filters">
      {/* 1. Layer Toggle: Live vs Potential */}
      <div className="nk-filter-group nk-layer-toggle" role="group" aria-label="Forecast layer">
        <button
          type="button"
          className={`nk-btn nk-btn--sm ${filters.layer === "live" ? "nk-btn--primary" : "nk-btn--outline"}`}
          onClick={() => onChange({ layer: "live" })}
          aria-pressed={filters.layer === "live"}
        >
          <Icon name="bolt" /> Live Forecast
        </button>
        <button
          type="button"
          className={`nk-btn nk-btn--sm ${filters.layer === "potential" ? "nk-btn--primary" : "nk-btn--outline"}`}
          onClick={() => onChange({ layer: "potential" })}
          aria-pressed={filters.layer === "potential"}
        >
          <Icon name="hourglass" /> Decayed Potential (72h)
        </button>
      </div>

      {/* 2. Level / Resolution Select — bound to map zoom (§7.3); picking one here also
          nudges the camera into that level's zoom band, so both stay in agreement. */}
      <div className="nk-filter-field">
        <label htmlFor="filter-level" className="nk-filter-label">
          Resolution <span className="nk-text-xs text-muted">(follows zoom)</span>
        </label>
        <Select
          id="filter-level"
          ariaLabel="Resolution level"
          size="sm"
          value={filters.level}
          onValueChange={(v) => onChange({ level: v as HeatmapLevel })}
          options={[
            { value: "district", label: "District Rollup" },
            { value: "cell", label: "Equirectangular Cell (~27km)" },
            { value: "location", label: "Bank Infrastructure Point" },
          ]}
        />
      </div>

      {/* 3. State Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-state" className="nk-filter-label">
          State
        </label>
        <Select
          id="filter-state"
          ariaLabel="Filter by state"
          size="sm"
          value={filters.state ?? "all"}
          onValueChange={(v) =>
            onChange({
              state: v === "all" ? undefined : v,
              district: undefined, // Reset district when state changes
            })
          }
          options={[
            { value: "all", label: "All 4 Demo States" },
            ...states.map((st) => ({ value: st.id, label: `${st.name} (${st.id})` })),
          ]}
        />
      </div>

      {/* 4. District Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-district" className="nk-filter-label">
          District
        </label>
        <Select
          id="filter-district"
          ariaLabel="Filter by district"
          size="sm"
          value={filters.district ?? "all"}
          onValueChange={(v) =>
            onChange({
              district: v === "all" ? undefined : v,
            })
          }
          disabled={availableDistricts.length === 0}
          options={[
            { value: "all", label: "All Districts" },
            ...availableDistricts.map((d) => ({ value: d.id, label: `${d.name} (${d.id})` })),
          ]}
        />
      </div>

      {/* 5. Category Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-category" className="nk-filter-label">
          Scam Modus
        </label>
        <Select
          id="filter-category"
          ariaLabel="Filter by category"
          size="sm"
          value={filters.category ?? "all"}
          onValueChange={(v) =>
            onChange({
              category: v === "all" ? undefined : v,
            })
          }
          options={[
            { value: "all", label: "All Modalities" },
            { value: "digital_arrest", label: "Digital Arrest" },
            { value: "investment_scam", label: "Investment Scam" },
            { value: "upi_phishing", label: "UPI Phishing" },
            { value: "task_job_scam", label: "Task / Job Scam" },
          ]}
        />
      </div>

      {/* 6. Min Confidence Threshold */}
      <div className="nk-filter-field">
        <label htmlFor="filter-confidence" className="nk-filter-label">
          Min Confidence
        </label>
        <Select
          id="filter-confidence"
          ariaLabel="Filter by min confidence"
          size="sm"
          value={filters.min_confidence?.toString() ?? "0"}
          onValueChange={(v) => {
            const val = parseFloat(v);
            onChange({ min_confidence: val > 0 ? val : undefined });
          }}
          options={[
            { value: "0", label: "All Probabilities" },
            { value: "0.5", label: "≥ 50% Confidence" },
            { value: "0.75", label: "≥ 75% Confidence" },
            { value: "0.9", label: "≥ 90% Critical Only" },
          ]}
        />
      </div>

      {/* 7. Reset Action */}
      <div className="nk-filter-actions">
        <button
          type="button"
          className="nk-btn nk-btn--ghost nk-btn--sm"
          onClick={onReset}
          aria-label="Reset all filters"
        >
          ↺ Reset
        </button>
      </div>
    </div>
  );
}
