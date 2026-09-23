/**
 * tailwind.preset.ts — Tailwind configuration preset.
 * DOC 3 Web App Shell: shared/tokens/tailwind.preset.ts
 *
 * Maps design token CSS variables into Tailwind utility classes so components
 * can use e.g. `bg-nk-surface-raised` instead of arbitrary CSS.
 * Track D Step D1 will update token values in tokens.css; this preset stays stable.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const preset: Record<string, any> = {
  theme: {
    extend: {
      colors: {
        nk: {
          surface: {
            base: "var(--nk-surface-base)",
            raised: "var(--nk-surface-raised)",
            sunken: "var(--nk-surface-sunken)",
          },
          text: {
            primary: "var(--nk-text-primary)",
            secondary: "var(--nk-text-secondary)",
            inverse: "var(--nk-text-inverse)",
          },
          border: {
            subtle: "var(--nk-border-subtle)",
            strong: "var(--nk-border-strong)",
          },
          brand: {
            primary: "var(--nk-brand-primary)",
            accent: "var(--nk-brand-accent)",
          },
          severity: {
            low: "var(--nk-severity-low)",
            medium: "var(--nk-severity-medium)",
            high: "var(--nk-severity-high)",
            critical: "var(--nk-severity-critical)",
          },
          verdict: {
            good: "var(--nk-verdict-good)",
            warn: "var(--nk-verdict-warn)",
            bad: "var(--nk-verdict-bad)",
          },
          status: {
            open: "var(--nk-status-open)",
            ack: "var(--nk-status-ack)",
            actioned: "var(--nk-status-actioned)",
            expired: "var(--nk-status-expired)",
          },
        },
      },
      fontFamily: {
        sans: ["var(--nk-font-sans)"],
        mono: ["var(--nk-font-mono)"],
      },
      borderRadius: {
        sm: "var(--nk-radius-sm)",
        md: "var(--nk-radius-md)",
        lg: "var(--nk-radius-lg)",
      },
      boxShadow: {
        sm: "var(--nk-shadow-sm)",
        md: "var(--nk-shadow-md)",
      },
    },
  },
  plugins: [],
};

export default preset;
