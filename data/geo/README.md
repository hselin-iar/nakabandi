# Bundled GeoJSON Data — NAKABANDI

## Scope
Boundaries and centroids for the four demonstration states:
- **Uttar Pradesh (UP)**
- **Maharashtra (MH)**
- **Rajasthan (RJ)**
- **Haryana (HR)**

## Source & Licence
- **Source**: Public domain boundary approximations derived from Survey of India public state boundary outlines, simplified to polygon geometries suitable for offline, bundle-safe rendering (<50KB total footprint).
- **Licence**: ODC-By 1.0 / Open Government Data (OGD) Platform India compatible.
- **Coverage**: Four demo states only. District centroids reference synthetic registry placements in `apps/world-sim/src/worldsim/core/registry.py` and `apps/api/src/nakabandi/geo/`.

## NFR Compliance (DOC 2 §2.7)
- Zero external CDN or tile-server network requests at runtime.
- Offline-ready and bundled directly into client distributions.
