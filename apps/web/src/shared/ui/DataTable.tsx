/**
 * DataTable.tsx — generic data table with column definitions.
 * DOC 3 Web App Shell: shared/ui — DataTable
 *
 * Virtualises above 200 rows (window slice approach — no external dep).
 * Responsive: collapses to single column at 360 px via CSS.
 */

import React, { useState, useMemo } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Column<T> {
  /** Unique column key. */
  key: string;
  /** Column header label. */
  header: string;
  /** Render a cell for a row. */
  cell: (row: T, index: number) => React.ReactNode;
  /** Enable sorting on this column (optional). */
  sortable?: boolean;
  /** CSS width hint (e.g. "8rem"). */
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  /** Unique key extractor. */
  getRowKey: (row: T, index: number) => string | number;
  /** Empty state element. */
  emptyState?: React.ReactNode;
  /** Optional row click handler. */
  onRowClick?: (row: T) => void;
  /** Optional extra CSS class(es) per row. */
  rowClassName?: (row: T, index: number) => string;
  className?: string;
  /** Caption for accessibility. */
  caption?: string;
}

type SortDir = "asc" | "desc" | null;

// ---------------------------------------------------------------------------
// DataTable
// ---------------------------------------------------------------------------

const VIRTUAL_THRESHOLD = 200;

export function DataTable<T>({
  columns,
  data,
  getRowKey,
  emptyState,
  onRowClick,
  rowClassName,
  className = "",
  caption,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  function toggleSort(key: string) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortKey(null);
      setSortDir(null);
    }
  }

  // Virtualise: only render a sliding window when data is large.
  const [windowStart, setWindowStart] = useState(0);
  const windowSize = 200;

  const visible = useMemo(() => {
    if (data.length > VIRTUAL_THRESHOLD) {
      return data.slice(windowStart, windowStart + windowSize);
    }
    return data;
  }, [data, windowStart]);

  if (data.length === 0) {
    return (
      <div className={`nk-table-empty ${className}`}>{emptyState}</div>
    );
  }

  return (
    <div className={`nk-table-wrapper ${className}`}>
      <table className="nk-table">
        {caption && <caption className="nk-table__caption">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`nk-table__th${col.sortable ? " nk-table__th--sortable" : ""}`}
                style={col.width ? { width: col.width } : undefined}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
                onClick={col.sortable ? () => toggleSort(col.key) : undefined}
              >
                {col.header}
                {col.sortable && (
                  <span className="nk-table__sort-icon" aria-hidden="true">
                    {sortKey === col.key
                      ? sortDir === "asc"
                        ? " ↑"
                        : " ↓"
                      : " ↕"}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => {
            const globalIndex = data.length > VIRTUAL_THRESHOLD ? windowStart + i : i;
            return (
              <tr
                key={getRowKey(row, globalIndex)}
                className={`nk-table__row${onRowClick ? " nk-table__row--clickable" : ""}${rowClassName ? " " + rowClassName(row, globalIndex) : ""}`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
              >
                {columns.map((col) => (
                  <td key={col.key} className="nk-table__td">
                    {col.cell(row, globalIndex)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {data.length > VIRTUAL_THRESHOLD && (
        <div className="nk-table-pagination">
          <button
            className="nk-btn nk-btn--ghost nk-btn--sm"
            onClick={() => setWindowStart(Math.max(0, windowStart - windowSize))}
            disabled={windowStart === 0}
            aria-label="Previous page"
          >
            ← Prev
          </button>
          <span className="nk-table-pagination__info">
            {windowStart + 1}–{Math.min(windowStart + windowSize, data.length)} of {data.length}
          </span>
          <button
            className="nk-btn nk-btn--ghost nk-btn--sm"
            onClick={() =>
              setWindowStart(
                Math.min(windowStart + windowSize, data.length - windowSize),
              )
            }
            disabled={windowStart + windowSize >= data.length}
            aria-label="Next page"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
