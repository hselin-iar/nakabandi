/**
 * useMediaQuery.ts — subscribe to a CSS media query. Returns false where matchMedia is
 * unavailable (jsdom, very old browsers) so callers fall back to their default layout.
 */

import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const supported = typeof window !== "undefined" && typeof window.matchMedia === "function";
  const [matches, setMatches] = useState(() => (supported ? window.matchMedia(query).matches : false));

  useEffect(() => {
    if (!supported) return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query, supported]);

  return matches;
}
