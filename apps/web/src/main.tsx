/**
 * main.tsx — React 18 app entry point.
 * DOC 3 Web App Shell: app/main.tsx
 */

import React from "react";
import { createRoot } from "react-dom/client";
import { Providers } from "./app/providers";
import { AppRoutes } from "./app/routes";
import "./shared/tokens/tokens.css";
import "./shared/tokens/neo-utils.css";
import "maplibre-gl/dist/maplibre-gl.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found in index.html");

createRoot(rootEl).render(
  <React.StrictMode>
    <Providers>
      <AppRoutes />
    </Providers>
  </React.StrictMode>,
);
