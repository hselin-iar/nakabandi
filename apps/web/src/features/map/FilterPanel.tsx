/**
 * FilterPanel.tsx — Accessible filter controls for the risk heatmap dashboard.
 * DOC 3 M3: "Filters: { layer: live|potential, level: district|cell|location, state?, district?, category?... }"
 */

import React from "react";
import type { HeatmapFilters, HeatmapLevel, Region } from "./types";

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
          ⚡ Live Forecast
        </button>
        <button
          type="button"
          className={`nk-btn nk-btn--sm ${filters.layer === "potential" ? "nk-btn--primary" : "nk-btn--outline"}`}
          onClick={() => onChange({ layer: "potential" })}
          aria-pressed={filters.layer === "potential"}
        >
          ⏳ Decayed Potential (72h)
        </button>
      </div>

      {/* 2. Level / Resolution Select */}
      <div className="nk-filter-field">
        <label htmlFor="filter-level" className="nk-filter-label">
          Resolution
        </label>
        <select
          id="filter-level"
          aria-label="Resolution level"
          className="nk-select nk-select--sm"
          value={filters.level}
          onChange={(e) => onChange({ level: e.target.value as HeatmapLevel })}
        >
          <option value="district">District Rollup</option>
          <option value="cell">Equirectangular Cell (~27km)</option>
          <option value="location">Bank Infrastructure Point</option>
        </select>
      </div>

      {/* 3. State Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-state" className="nk-filter-label">
          State
        </label>
        <select
          id="filter-state"
          aria-label="Filter by state"
          className="nk-select nk-select--sm"
          value={filters.state ?? "all"}
          onChange={(e) =>
            onChange({
              state: e.target.value === "all" ? undefined : e.target.value,
              district: undefined, // Reset district when state changes
            })
          }
        >
          <option value="all">All 4 Demo States</option>
          {states.map((st) => (
            <option key={st.id} value={st.id}>
              {st.name} ({st.id})
            </option>
          ))}
        </select>
      </div>

      {/* 4. District Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-district" className="nk-filter-label">
          District
        </label>
        <select
          id="filter-district"
          aria-label="Filter by district"
          className="nk-select nk-select--sm"
          value={filters.district ?? "all"}
          onChange={(e) =>
            onChange({
              district: e.target.value === "all" ? undefined : e.target.value,
            })
          }
          disabled={availableDistricts.length === 0}
        >
          <option value="all">All Districts</option>
          {availableDistricts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.id})
            </option>
          ))}
        </select>
      </div>

      {/* 5. Category Selector */}
      <div className="nk-filter-field">
        <label htmlFor="filter-category" className="nk-filter-label">
          Scam Modus
        </label>
        <select
          id="filter-category"
          aria-label="Filter by category"
          className="nk-select nk-select--sm"
          value={filters.category ?? "all"}
          onChange={(e) =>
            onChange({
              category: e.target.value === "all" ? undefined : e.target.value,
            })
          }
        >
          <option value="all">All Modalities</option>
          <option value="digital_arrest">Digital Arrest</option>
          <option value="investment_scam">Investment Scam</option>
          <option value="upi_phishing">UPI Phishing</option>
          <option value="task_job_scam">Task / Job Scam</option>
        </select>
      </div>

      {/* 6. Min Confidence Threshold */}
      <div className="nk-filter-field">
        <label htmlFor="filter-confidence" className="nk-filter-label">
          Min Confidence
        </label>
        <select
          id="filter-confidence"
          aria-label="Filter by min confidence"
          className="nk-select nk-select--sm"
          value={filters.min_confidence?.toString() ?? "0"}
          onChange={(e) => {
            const val = parseFloat(e.target.value);
            onChange({ min_confidence: val > 0 ? val : undefined });
          }}
        >
          <option value="0">All Probabilities</option>
          <option value="0.5">≥ 50% Confidence</option>
          <option value="0.75">≥ 75% Confidence</option>
          <option value="0.9">≥ 90% Critical Only</option>
        </select>
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
