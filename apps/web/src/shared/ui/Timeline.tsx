/**
 * Timeline.tsx — vertical or horizontal timeline for audit events and delivery history.
 * DOC 3 Web App Shell: shared/ui — Timeline
 *
 * `orientation="horizontal"` renders the same entries as a scrubbable left-to-right
 * sequence instead of a vertical bullet list — makes a fast, single-request pipeline
 * (ingest -> resolve -> forecast -> assess -> alert -> action) visibly fast, not just
 * asserted (Frontend Strategy §5.3). Defaults to "vertical" so existing callers are unchanged.
 */

import React from "react";
import { formatSimTime } from "../lib/format";

export interface TimelineEntry {
  id: string;
  timestamp: string; // ISO sim time
  title: string;
  description?: React.ReactNode;
  /** Optional accent class for the vertical dot (e.g. "nk-timeline__dot--success"); the
   *  horizontal renderer maps this to its own "nk-timeline-h__dot--*" equivalent. */
  dotClass?: string;
}

interface TimelineProps {
  entries: TimelineEntry[];
  className?: string;
  orientation?: "vertical" | "horizontal";
}

export function Timeline({ entries, className = "", orientation = "vertical" }: TimelineProps) {
  if (entries.length === 0) {
    return (
      <p className={`nk-timeline-empty ${className}`}>No timeline entries.</p>
    );
  }

  if (orientation === "horizontal") {
    return (
      <ol className={`nk-timeline-h ${className}`}>
        {entries.map((entry) => (
          <li key={entry.id} className="nk-timeline-h__item">
            <time className="nk-timeline-h__time" dateTime={entry.timestamp}>
              {formatSimTime(entry.timestamp, { includeSeconds: true })}
            </time>
            <span
              className={`nk-timeline-h__dot ${(entry.dotClass ?? "").replace("nk-timeline__dot", "nk-timeline-h__dot")}`}
              aria-hidden="true"
            />
            <p className="nk-timeline-h__title">{entry.title}</p>
            {entry.description && (
              <div className="nk-timeline-h__desc">{entry.description}</div>
            )}
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ol className={`nk-timeline ${className}`}>
      {entries.map((entry) => (
        <li key={entry.id} className="nk-timeline__item">
          <span className={`nk-timeline__dot ${entry.dotClass ?? ""}`} aria-hidden="true" />
          <div className="nk-timeline__content">
            <time
              className="nk-timeline__time"
              dateTime={entry.timestamp}
            >
              {formatSimTime(entry.timestamp, { includeSeconds: true })}
            </time>
            <p className="nk-timeline__title">{entry.title}</p>
            {entry.description && (
              <div className="nk-timeline__desc">{entry.description}</div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
