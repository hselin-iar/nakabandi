// cytoscape-cose-bilkent ships no type definitions; cytoscape-dagre and react-cytoscapejs are
// covered by their @types packages. Ambient declaration so the extension can be registered.
declare module "cytoscape-cose-bilkent" {
  import type cytoscape from "cytoscape";
  const ext: cytoscape.Ext;
  export default ext;
}
