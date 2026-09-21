// Placeholder for root scripts whose implementation lands in a later step (DOC 4).
// Exits 0 so `npm run <name>` is discoverable now; replace this file's callers as each step ships.
const name = process.argv[2] ?? "(unnamed)";
console.log(`npm run ${name}: not implemented yet; a later step in DOC 4 provides it.`);
