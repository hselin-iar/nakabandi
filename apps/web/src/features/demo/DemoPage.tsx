/**
 * DemoPage.tsx — World Simulator Control & Demo Console Page.
 * DOC 3 M1 · LC-8 · DOC 2 §2.7 · DOC 4 Step C8
 *
 * Gated by RoleGuard on the route to demo_operator and admin roles.
 */

import React from "react";
import { DemoConsole } from "./DemoConsole";

export function DemoPage() {
  return (
    <div className="nk-page nk-demo-page" data-testid="demo-page">
      <div className="nk-page-header">
        <div>
          <h1 className="nk-page-title">World Simulator & Demo Console</h1>
          <p className="nk-page-subtitle">
            Control the background world-sim runner, adjust execution parameters, inject live mule clusters,
            and switch demonstration personas.
          </p>
        </div>
      </div>

      <DemoConsole />
    </div>
  );
}

export default DemoPage;
