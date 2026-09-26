/**
 * Icon.tsx — the one small icon set (stroke SVG, inherits the text colour) used in place of
 * emoji glyphs, which render differently on every platform and read as decoration.
 */

import React from "react";

const PATHS = {
  lock: (
    <>
      <rect x="4" y="9" width="12" height="8" rx="2" />
      <path d="M7 9V6.5a3 3 0 0 1 6 0V9" />
    </>
  ),
  shield: <path d="M10 2.5 16 5v4.5c0 3.6-2.4 6.3-6 8-3.6-1.7-6-4.4-6-8V5l6-2.5Z" />,
  radar: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <circle cx="10" cy="10" r="3.5" />
      <path d="M10 10 15.2 4.8" />
    </>
  ),
  bell: (
    <>
      <path d="M10 2.5a5.5 5.5 0 0 1 5.5 5.5c0 3.2 1.4 4.6 1.4 4.6H3.1S4.5 11.2 4.5 8A5.5 5.5 0 0 1 10 2.5Z" />
      <path d="M8.3 16.2a1.8 1.8 0 0 0 3.4 0" />
    </>
  ),
  bellOff: (
    <>
      <path d="M10 2.5a5.5 5.5 0 0 1 5.5 5.5c0 3.2 1.4 4.6 1.4 4.6H3.1S4.5 11.2 4.5 8A5.5 5.5 0 0 1 10 2.5Z" />
      <path d="M3 3l14 14" />
    </>
  ),
  pin: (
    <>
      <path d="M10 18s5.5-5 5.5-9.2a5.5 5.5 0 0 0-11 0C4.5 13 10 18 10 18Z" />
      <circle cx="10" cy="8.6" r="1.9" />
    </>
  ),
  file: (
    <>
      <path d="M5 2.5h6.5L15.5 6.5v11H5v-15Z" />
      <path d="M11.5 2.5v4h4M7.5 10h5M7.5 13h5" />
    </>
  ),
  check: <path d="m4.5 10.5 3.5 3.5 7.5-8" />,
  cross: <path d="M5 5l10 10M15 5 5 15" />,
  flask: (
    <>
      <path d="M8 2.5h4M8.8 2.5v5.2L4.5 15a1.5 1.5 0 0 0 1.3 2.3h8.4a1.5 1.5 0 0 0 1.3-2.3l-4.3-7.3V2.5" />
      <path d="M6.5 12.5h7" />
    </>
  ),
  scale: (
    <>
      <path d="M10 3v14M6 17h8M4 6h12" />
      <path d="M4 6 2 11a2.5 2.5 0 0 0 4 0L4 6ZM16 6l-2 5a2.5 2.5 0 0 0 4 0l-2-5Z" />
    </>
  ),
  link: (
    <>
      <path d="M8.5 11.5a3 3 0 0 0 4.2 0l2.6-2.6a3 3 0 0 0-4.2-4.2l-1 1" />
      <path d="M11.5 8.5a3 3 0 0 0-4.2 0L4.7 11.1a3 3 0 0 0 4.2 4.2l1-1" />
    </>
  ),
  hourglass: <path d="M5.5 2.5h9M5.5 17.5h9M6.5 2.5c0 4 3.5 4.5 3.5 7.5s-3.5 3.5-3.5 7.5M13.5 2.5c0 4-3.5 4.5-3.5 7.5s3.5 3.5 3.5 7.5" />,
  bolt: <path d="M11 2.5 4.5 11H10l-1 6.5L15.5 9H10l1-6.5Z" />,
  map: (
    <>
      <path d="M2.5 4.5 7 3l6 2 4.5-1.5v12L13 17l-6-2-4.5 1.5v-12Z" />
      <path d="M7 3v12M13 5v12" />
    </>
  ),
  table: (
    <>
      <rect x="3" y="4" width="14" height="12" rx="2" />
      <path d="M3 8.5h14M8 8.5V16" />
    </>
  ),
  refresh: (
    <>
      <path d="M16 10a6 6 0 1 1-1.8-4.3" />
      <path d="M16 3.5V6.5h-3" />
    </>
  ),
  pause: <path d="M7 4.5v11M13 4.5v11" />,
  alert: (
    <>
      <path d="M10 3 17.5 16h-15L10 3Z" />
      <path d="M10 8v3.5M10 14v.01" />
    </>
  ),
  copy: (
    <>
      <rect x="7" y="7" width="9" height="9" rx="2" />
      <path d="M13 7V5.5A1.5 1.5 0 0 0 11.5 4h-6A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H7" />
    </>
  ),
  broadcast: (
    <>
      <circle cx="10" cy="10" r="1.6" />
      <path d="M6.5 6.5a5 5 0 0 0 0 7M13.5 6.5a5 5 0 0 1 0 7M4 4a8.5 8.5 0 0 0 0 12M16 4a8.5 8.5 0 0 1 0 12" />
    </>
  ),
  network: (
    <>
      <circle cx="10" cy="10" r="2.2" />
      <circle cx="4" cy="4.5" r="1.7" />
      <circle cx="16" cy="4.5" r="1.7" />
      <circle cx="4" cy="15.5" r="1.7" />
      <circle cx="16" cy="15.5" r="1.7" />
      <path d="M5.3 5.7 8.3 8.5M14.7 5.7l-3 2.8M5.3 14.3l3-2.8M14.7 14.3l-3-2.8" />
    </>
  ),
  flow: (
    <>
      <path d="M2.5 5h6a3 3 0 0 1 3 3v4a3 3 0 0 0 3 3h3" />
      <path d="M14.5 12.5 17.5 15l-3 2.5" />
      <path d="M2.5 15h4" />
    </>
  ),
  unit: (
    <>
      <path d="M3 12.5V9l2-3.5h10L17 9v3.5" />
      <path d="M2.5 12.5h15v2.5h-15z" />
      <path d="M5.5 15v1.5M14.5 15v1.5" />
    </>
  ),
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 14, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={`nk-icon${className ? ` ${className}` : ""}`}
      viewBox="0 0 20 20"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
