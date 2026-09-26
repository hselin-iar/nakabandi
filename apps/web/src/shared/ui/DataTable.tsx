/**
 * DataTable.tsx — generic data table with column definitions.
 * DOC 3 Web App Shell: shared/ui — DataTable
 *
 * Two render modes:
 *  - default: windows a 200-row slice above 200 rows (no external dependency).
 *  - `virtualized`: true windowing via @tanstack/react-virtual inside a fixed-height scroll
 *    container with fixed-height rows (overhaul plan §2.1). Opt in per table.
 *
 * Column sorting is functional: a column sorts by its `sortValue`, falling back to the row's
 * own `row[key]` when that is a string or number.
 *
 * Optional keyboard navigation: pass `onActiveChange` and drive the ref's `step()`/`activate()`
 * (the alerts inbox binds j/k to it). The active row is tracked by key, so it survives
 * re-sorts and live data updates.
 */

import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

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
  /** Value to sort by; defaults to row[key] when that is a string or number. */
  sortValue?: (row: T) => string | number | null | undefined;
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
  /** True windowing in a fixed-height scroll container. */
  virtualized?: boolean;
  /** Fixed row height in px (virtualized mode). */
  rowHeight?: number;
  /** CSS height of the scroll container (virtualized mode), e.g. "calc(100dvh - 22rem)". */
  height?: string;
  /** Called when the keyboard-active row changes. Enables active-row tracking. */
  onActiveChange?: (row: T | null) => void;
  /** Called when the scroll container leaves / returns to the top (virtualized mode). */
  onScrolledChange?: (scrolled: boolean) => void;
}

export interface DataTableHandle {
  /** Move the active row by delta (clamped). */
  step: (delta: number) => void;
  /** Make the nth visible row (0-based) active. */
  activate: (index: number) => void;
  /** Scroll the container back to the top (virtualized mode). */
  scrollToTop: () => void;
}

type SortDir = "asc" | "desc" | null;

const VIRTUAL_THRESHOLD = 200;
const DEFAULT_ROW_HEIGHT = 64;
const SCROLLED_PX = 24;

function compareValues(a: unknown, b: unknown): number {
  const aNil = a === null || a === undefined;
  const bNil = b === null || b === undefined;
  if (aNil || bNil) return aNil === bNil ? 0 : aNil ? 1 : -1; // empties always last
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

function DataTableInner<T>(
  {
    columns,
    data,
    getRowKey,
    emptyState,
    onRowClick,
    rowClassName,
    className = "",
    caption,
    virtualized = false,
    rowHeight = DEFAULT_ROW_HEIGHT,
    height = "calc(100dvh - 24rem)",
    onActiveChange,
    onScrolledChange,
  }: DataTableProps<T>,
  ref: React.ForwardedRef<DataTableHandle>,
) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [activeKey, setActiveKey] = useState<string | number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrolledRef = useRef(false);

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

  // Apply the sort. Array.prototype.sort is stable, so ties keep the server's order.
  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return data;
    const valueOf = (row: T): unknown => {
      if (col.sortValue) return col.sortValue(row);
      const v = (row as Record<string, unknown>)[col.key];
      return typeof v === "string" || typeof v === "number" ? v : null;
    };
    const dir = sortDir === "asc" ? 1 : -1;
    return [...data].sort((a, b) => {
      const av = valueOf(a);
      const bv = valueOf(b);
      const aNil = av === null || av === undefined;
      const bNil = bv === null || bv === undefined;
      if (aNil || bNil) return compareValues(av, bv); // keep empties last in both directions
      return dir * compareValues(av, bv);
    });
  }, [data, columns, sortKey, sortDir]);

  // Default (non-virtualised) mode: slide a 200-row window.
  const [windowStart, setWindowStart] = useState(0);
  const windowSize = 200;
  const windowed = !virtualized && sorted.length > VIRTUAL_THRESHOLD;
  const visible = useMemo(
    () => (windowed ? sorted.slice(windowStart, windowStart + windowSize) : sorted),
    [sorted, windowed, windowStart],
  );

  const virtualizer = useVirtualizer({
    count: virtualized ? visible.length : 0,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 8,
    // jsdom has no layout; give the virtualizer a sane first window (real browsers observe the element).
    initialRect: { width: 1024, height: 640 },
  });

  const activeIndex = useMemo(
    () => (activeKey === null ? -1 : visible.findIndex((r, i) => getRowKey(r, i) === activeKey)),
    [visible, activeKey, getRowKey],
  );

  // Notify the owner when the active row changes (including when it leaves the data).
  const onActiveChangeRef = useRef(onActiveChange);
  onActiveChangeRef.current = onActiveChange;
  const lastNotifiedKey = useRef<string | number | null>(null);
  useEffect(() => {
    const row = activeIndex >= 0 ? visible[activeIndex] : null;
    const key = row ? getRowKey(row, activeIndex) : null;
    if (key === lastNotifiedKey.current) return;
    lastNotifiedKey.current = key;
    onActiveChangeRef.current?.(row);
  }, [activeIndex, visible, getRowKey]);

  // Keep the active row scrolled into view.
  useEffect(() => {
    if (virtualized && activeIndex >= 0) virtualizer.scrollToIndex(activeIndex, { align: "auto" });
  }, [activeIndex, virtualized]);

  useImperativeHandle(
    ref,
    () => ({
      step(delta: number) {
        if (visible.length === 0) return;
        const from = activeIndex < 0 ? (delta > 0 ? -1 : visible.length) : activeIndex;
        const next = Math.min(visible.length - 1, Math.max(0, from + delta));
        setActiveKey(getRowKey(visible[next]!, next));
      },
      activate(index: number) {
        if (index < 0 || index >= visible.length) return;
        setActiveKey(getRowKey(visible[index]!, index));
      },
      scrollToTop() {
        scrollRef.current?.scrollTo({ top: 0 });
      },
    }),
    [visible, activeIndex, getRowKey],
  );

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const scrolled = e.currentTarget.scrollTop > SCROLLED_PX;
    if (scrolled !== scrolledRef.current) {
      scrolledRef.current = scrolled;
      onScrolledChange?.(scrolled);
    }
  }

  if (data.length === 0) {
    return <div className={`nk-table-empty ${className}`}>{emptyState}</div>;
  }

  const virtualItems = virtualized ? virtualizer.getVirtualItems() : [];
  const padTop = virtualItems.length > 0 ? virtualItems[0]!.start : 0;
  const padBottom =
    virtualItems.length > 0 ? virtualizer.getTotalSize() - virtualItems[virtualItems.length - 1]!.end : 0;
  // A scroll container with no measurable height (jsdom, a hidden tab) yields no virtual items;
  // render a first page rather than an empty table.
  const fallbackCount = virtualized && virtualItems.length === 0 ? Math.min(visible.length, 30) : 0;

  const renderRow = (row: T, index: number) => {
    const key = getRowKey(row, index);
    const isActive = activeKey !== null && key === activeKey;
    return (
      <tr
        key={key}
        data-row-key={key}
        aria-selected={onActiveChange ? isActive : undefined}
        className={`nk-table__row${onRowClick ? " nk-table__row--clickable" : ""}${virtualized ? " nk-table__row--virtual" : ""}${isActive ? " nk-table__row--active" : ""}${rowClassName ? " " + rowClassName(row, index) : ""}`}
        onClick={
          onRowClick
            ? () => {
                if (onActiveChange) setActiveKey(key);
                onRowClick(row);
              }
            : undefined
        }
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
            {col.cell(row, index)}
          </td>
        ))}
      </tr>
    );
  };

  const rows = virtualized
    ? virtualItems.length > 0
      ? virtualItems.map((v) => renderRow(visible[v.index]!, v.index))
      : visible.slice(0, fallbackCount).map((row, i) => renderRow(row, i))
    : visible.map((row, i) => renderRow(row, windowed ? windowStart + i : i));

  return (
    <div
      ref={scrollRef}
      className={`nk-table-wrapper${virtualized ? " nk-table-wrapper--virtual" : ""} ${className}`}
      style={
        virtualized
          ? ({ height, "--nk-row-h": `${rowHeight}px` } as React.CSSProperties)
          : undefined
      }
      onScroll={virtualized ? handleScroll : undefined}
    >
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
                    {sortKey === col.key ? (sortDir === "asc" ? " ↑" : " ↓") : " ↕"}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {virtualized && padTop > 0 && (
            <tr className="nk-table__spacer" aria-hidden="true">
              <td colSpan={columns.length} style={{ height: padTop }} />
            </tr>
          )}
          {rows}
          {virtualized && padBottom > 0 && (
            <tr className="nk-table__spacer" aria-hidden="true">
              <td colSpan={columns.length} style={{ height: padBottom }} />
            </tr>
          )}
        </tbody>
      </table>
      {windowed && (
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
            {windowStart + 1}–{Math.min(windowStart + windowSize, sorted.length)} of {sorted.length}
          </span>
          <button
            className="nk-btn nk-btn--ghost nk-btn--sm"
            onClick={() => setWindowStart(Math.min(windowStart + windowSize, sorted.length - windowSize))}
            disabled={windowStart + windowSize >= sorted.length}
            aria-label="Next page"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

/** Generic forwardRef: the cast keeps <DataTable<Row> …> inference for callers. */
export const DataTable = forwardRef(DataTableInner) as <T>(
  props: DataTableProps<T> & { ref?: React.Ref<DataTableHandle> },
) => React.ReactElement | null;
