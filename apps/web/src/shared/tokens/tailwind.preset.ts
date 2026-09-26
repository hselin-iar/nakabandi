/**
 * tailwind.preset.ts — Tailwind configuration preset.
 * DOC 3 Web App Shell: shared/tokens/tailwind.preset.ts
 *
 * Maps design token CSS variables into Tailwind utility classes so components
 * can use e.g. `bg-nk-surface-raised` instead of arbitrary CSS.
 * Track D Step D1 will update token values in tokens.css; this preset stays stable.
 *
 * Frontend overhaul (docs/plans/frontend_overhaul_plan.md §1.2): adds the tactical-command
 * tokens (elevated surface, tertiary text, single non-severity accent, severity/live glows)
 * and the three-tier weight scale. Existing token names are unchanged.
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
            elevated: "var(--nk-surface-elevated)",
          },
          text: {
            primary: "var(--nk-text-primary)",
            secondary: "var(--nk-text-secondary)",
            tertiary: "var(--nk-text-tertiary)",
            inverse: "var(--nk-text-inverse)",
          },
          accent: "var(--nk-accent)",
          canvas: "var(--nk-canvas-bg)",
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
      fontWeight: {
        read: "var(--nk-weight-read)",
        ui: "var(--nk-weight-ui)",
        strong: "var(--nk-weight-strong)",
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
        "glow-critical": "var(--nk-glow-critical)",
        "glow-high": "var(--nk-glow-high)",
        "glow-live": "var(--nk-glow-live)",
      },
    },
  },
  plugins: [],
};

export default preset;
