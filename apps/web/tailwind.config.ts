import type { Config } from "tailwindcss";
import nkPreset from "./src/shared/tokens/tailwind.preset";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  presets: [nkPreset],
  // The app ships its own reset in tokens.css; Tailwind's preflight would change
  // element defaults under ~4,000 lines of existing nk-* styles.
  corePlugins: { preflight: false },
} satisfies Config;
