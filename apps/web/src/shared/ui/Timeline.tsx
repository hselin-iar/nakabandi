/**
 * Timeline.tsx — vertical timeline for audit events and delivery history.
 * DOC 3 Web App Shell: shared/ui — Timeline
 */

import React from "react";
import { formatSimTime } from "../lib/format";

export interface TimelineEntry {
  id: string;
  timestamp: string; // ISO sim time
  title: string;
  description?: React.ReactNode;
  /** Optional accent class for the dot (e.g. "nk-timeline__dot--success"). */
  dotClass?: string;
}

interface TimelineProps {
  entries: TimelineEntry[];
  className?: string;
}

export function Timeline({ entries, className = "" }: TimelineProps) {
  if (entries.length === 0) {
    return (
      <p className={`nk-timeline-empty ${className}`}>No timeline entries.</p>
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
