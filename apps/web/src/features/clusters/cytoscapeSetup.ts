/**
 * cytoscapeSetup.ts — registers the layout extensions once.
 *  - dagre: layered left-to-right layout for money cascades (a DAG)
 *  - cose-bilkent: force-directed fallback for graphs with a ring, where dagre would silently
 *    reverse an edge to break the cycle and the "money flows left to right" reading would lie
 */

import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";
import coseBilkent from "cytoscape-cose-bilkent";

let registered = false;

export function ensureCytoscapeExtensions(): void {
  if (registered) return;
  registered = true;
  try {
    cytoscape.use(dagre);
    cytoscape.use(coseBilkent);
  } catch {
    // Already registered (hot reload): harmless.
  }
}
