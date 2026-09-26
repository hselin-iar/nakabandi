/**
 * LayerPanel.tsx — toggleable map layers, each with a hotkey hint and a live count.
 *
 * The OSIRIS pattern (overhaul plan §2.3): one row per layer, switch + name + count. Toggling
 * goes through MapAdapter.setLayerVisibility; counts come from data MapPage already holds,
 * so the panel triggers no fetch of its own.
 */

export type LayerKey = "heat" | "locations" | "alerts" | "route" | "boundaries";

export interface LayerRowSpec {
  key: LayerKey;
  name: string;
  hotkey: string;
  /** Live count, or null when a count has no meaning for the layer. */
  count: number | null;
  /** Muted trailing note, e.g. "+3 suppressed". */
  note?: string;
}

interface LayerPanelProps {
  rows: LayerRowSpec[];
  on: Record<LayerKey, boolean>;
  onToggle: (key: LayerKey) => void;
}

export function LayerPanel({ rows, on, onToggle }: LayerPanelProps) {
  return (
    <div className="nk-layer-panel" role="group" aria-label="Map layers">
      <div className="nk-layer-panel__title">Layers</div>
      {rows.map((r) => (
        <button
          key={r.key}
          type="button"
          className="nk-layer-row"
          aria-pressed={on[r.key]}
          onClick={() => onToggle(r.key)}
        >
          <span className="nk-layer-row__switch" aria-hidden="true" />
          <span className="nk-layer-row__name">{r.name}</span>
          {r.note && <span className="nk-layer-row__muted">{r.note}</span>}
          {r.count !== null && <span className="nk-layer-row__count">{r.count}</span>}
          <kbd className="nk-kbd">{r.hotkey}</kbd>
        </button>
      ))}
    </div>
  );
}
