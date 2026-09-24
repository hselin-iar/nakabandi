# NAKABANDI - Geodata Source Research: District Boundary Polygons

**Date:** 23 September 2026 (all "last-verified" dates below are 2026-09-23 unless marked otherwise)
**Scope:** Track D, Step D5 (data curation). District boundary polygons for MH / UP / HR / JH so the dashboard can render offline choropleth heatmaps from a public GitHub repo.
**Out of scope (per spec):** ATM/branch/agent points (already committed under ODbL), census population/area stats.

**Note on this version:** this merges two independently generated research passes against the same brief. A parallel pass also produced a Part B on bank/ATM point sources (OSM/Geofabrik, RBI DBIE, data.gov.in) - that duplicates work already committed and is explicitly on the brief's "DO NOT RESEARCH" list, so it is dropped here entirely. That pass's one genuinely new contribution to Part A - proposing OpenStreetMap as a fifth boundary source - is folded into Q1 below, but checked rather than taken at face value (see the OSM entry and the ledger).

Every claim is marked **[VERIFIED]** (read on the primary source page, tested by executing the pipeline, or confirmed via a live search run for this merge) or **[UNVERIFIED]**.

---

## Bottom line

Use **DataMeet `maps` repo, `Districts/Census_2011/2011_Dist.shp`** (CC BY 2.5 India). Of every source evaluated, it's the only one that's actually been pulled, filtered, measured and licence-checked end to end rather than estimated. Among the four sources the brief named, it's the only one whose licence explicitly permits bundling in a public GitHub repo. It matches the project's Census 2011 district naming, and the 4-state extract is 2.13 MB at full fidelity and ~0.1-0.3 MB after simplification. GADM (no redistribution) and Bhuvan (no redistribution) are licence-blocked. Survey of India is the official and most current fallback but publishes no redistribution licence on its portal. OpenStreetMap surfaced as a fifth candidate (Q1.5) - it would remove the fold-back step in Q2 entirely if its district coverage for these four states checks out, but that's unverified; don't switch to it under deadline pressure without first counting features against the real district list.

---

## Q1 - Source evaluation

### 1. DataMeet `maps` (GitHub) - RECOMMENDED

- **Download URL:** https://github.com/datameet/maps/tree/master/Districts/Census_2011 (raw: `https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/2011_Dist.{shp,shx,dbf,prj,sbn,sbx}`) **[VERIFIED, downloaded and inspected]**
- **Format:** ESRI Shapefile. `2011_Dist.shp` = 10,220,732 bytes (10.2 MB); full sidecar set ~10.3 MB. No per-state split; one national file. **[VERIFIED, GitHub API file listing]**
- **CRS:** WGS 84 geographic, EPSG:4326 (read from `2011_Dist.prj`). **[VERIFIED]**
- **Content:** 641 polygon records, all India. Attribute fields: `DISTRICT`, `ST_NM`, `ST_CEN_CD`, `DT_CEN_CD`, `censuscode`. **[VERIFIED, `mapshaper -info`]**
- **Derived from:** Census of India, Administrative Atlas of India 2011 (names and extent), per the folder README. **[VERIFIED, https://github.com/datameet/maps/blob/master/Districts/README.md]**
- **Licence:** **Creative Commons Attribution 2.5 India (CC BY 2.5 IN)** - stated explicitly in `Districts/README.md`, which overrides the repo-wide default of CC BY 4.0 stated in the root README. Both allow commercial use and redistribution; attribution required. **[VERIFIED, both READMEs read]**
  - Districts README: https://github.com/datameet/maps/blob/master/Districts/README.md
  - Root README (default licence + attribution example): https://github.com/datameet/maps/blob/master/README.md
- **Last update:** 2014-05-22 (last commit touching `Districts/Census_2011`). The dataset is intentionally Census-2011 vintage, not a bug. **[VERIFIED, GitHub commits API]**

### 2. GADM (Global Administrative Areas) - EXCLUDED (licence)

- **Download URL:** https://gadm.org/download_country.html (India, GADM version 4.1). **[VERIFIED]**
- **Formats / CRS:** GeoJSON, Shapefile, Geopackage, KML; EPSG:4326. Sizes observed via HTTP HEAD: level-2 (district) GeoJSON zip 1.49 MB; full shapefile zip 24.7 MB; geopackage 52.0 MB. **[VERIFIED]** - a parallel pass estimated ~50-80 MB across formats without stating a method; the measured, per-level figures above are the ones to trust.
- **Version/date:** GADM 4.1; the India level-2 file is dated 2022-07-19. **[VERIFIED]**
- **Licence (https://gadm.org/license.html):** "The data are freely available for academic use and other non-commercial use. **Redistribution or commercial use is not allowed without prior permission.**" Committing GADM polygons to a public GitHub repo is redistribution - not permitted. Attribution string if it were ever cleared for use: `GADM (version 4.1), www.gadm.org`. **[VERIFIED, licence page read]**
- **Boundary quality issues found by direct inspection of `gadm41_IND_2.json` (676 level-2 features):** **[VERIFIED]**
  - Haryana still has 21 districts: **Charkhi Dadri (2016) is missing** - known staleness.
  - Maharashtra has 36 (includes Palghar, 2014).
  - `NAME_1` strings are concatenated without spaces (`UttarPradesh`); the `UttarPradesh` list also **contains 91 features polluted with Uttarakhand districts and duplicates** - Chamoli, Pithoragarh and Uttarkashi each appear twice under "UttarPradesh" while an "Uttarakhand" state also exists.
  - District names use old spellings (Allahabad, Faizabad, Gurgaon, Mewat, Bid) and concatenations (PashchimiSinghbhum, MumbaiCity).

### 3. Survey of India Open Portal - official fallback, licence UNVERIFIED

- **URL:** https://onlinemaps.surveyofindia.gov.in/ (product catalog: https://onlinemaps.surveyofindia.gov.in/Digital_Product_Show.aspx). **[VERIFIED]**
- **Product:** "Administrative Boundary Database" - state + district (+ taluk, village) boundaries with HQs, Shapefile format, national or per-state coverage. Current boundaries (this is the authoritative source other datasets lag). **[VERIFIED, portal About/Product pages read]**
- **Access/licence:** the portal references the SoI pricing list for these products and requires registration; **no licence text granting redistribution was found on the public pages read**. A parallel pass characterised the checkout terms as barring resale and sharing with foreign entities, which is consistent with what a pricing/registration-gated government geodata portal typically imposes, but no public licence page states this outright - treat the *substance* (registration-gated, redistribution unclear at best) as right, and the specific checkout clause text as unconfirmed. The data.gov.in "Admin Boundaries" catalog (National Water Informatics Centre, released under NDSAP, updated 2022-09-28) currently lists **no downloadable resources** ("No Result Found" on the resource panel). **[VERIFIED, https://www.data.gov.in/catalog/admin-boundaries read]**; redistribution terms **[UNVERIFIED]**.
- Verdict: not bundleable as-is; only worth pursuing (written licence confirmation from SoI) if post-2011 bifurcated boundaries become a hard requirement.

### 4. Bhuvan (ISRO/NRSC) - EXCLUDED (licence)

- **URL:** https://bhuvan.nrsc.gov.in/ (administrative boundaries via thematic services/geoserver after login).
- **Licence (https://bhuvan.nrsc.gov.in/terms.php):** non-exclusive, **non-transferable** licence; users "must not ... **Redistribute, sublicense, rent, publish, sell**, assign, lease, market, transfer, or otherwise make the content available to third parties" without prior written authorization from DOS/ISRO/NRSC. Attribution string if it were ever cleared: `© Bhuvan:ISRO/NRSC`. Bundling in a public repo is not permitted. **[VERIFIED, terms page read]**

### 5. OpenStreetMap / Overpass / Geofabrik - CONSIDERED, NOT ADOPTED

The parallel pass proposed pulling district boundaries via Overpass (`admin_level=5` relations, `ISO3166-2` filters) or Geofabrik's zonal shapefile extracts, under ODbL 1.0.

- **What's genuinely right about it [VERIFIED]:** ODbL does permit redistribution and commercial use, with attribution and share-alike applying to the raw database extract, not to rendered "Produced Works" like a choropleth heatmap - that's a correct read of ODbL §4.3/4.4, and it's the same licence the project's already-committed ATM/branch data is under. If OSM's district relations for these four states are complete and current, they'd already include Palghar, Charkhi Dadri and the four newer UP districts natively - which would remove the fold-back step in Q2 entirely, a real advantage over DataMeet if true.
- **What's asserted but not demonstrated [UNVERIFIED]:** the claim that OSM is "the most accurate, current, and legally redistributable source" for Indian district boundaries specifically. No Overpass query was actually run against MH/UP/HR/JH in that pass - its sizes ("~4-8 MB") and "all 75 UP districts present" claim are estimates, not measurements, unlike DataMeet's pipeline in Q3 below, which is a real executed run with real byte and feature counts.
- **Independent check run for this merge [VERIFIED via live search, 2026-09-23]:** OSM's own community has a long, documented history of incomplete and inconsistent `admin_level=5` coverage in India. A 2018 talk-in mailing-list thread ("Missing al5-boundaries in India") shows large tracts of the country with no district relation at all at that time, and the community was still closing gaps state-by-state through mid-to-late 2018 (https://wiki.openstreetmap.org/wiki/Districts_in_India tracks this per state); a separate 2018 thread on the same list notes the project didn't even have a clearly licensed source dataset for districts at that point, which is a different (import-provenance) concern from the ODbL redistribution point above. None of this proves today's coverage is bad for these specific four states - only that "OSM has this, fully and cleanly" is a claim that needs checking per state, not assumed.
- **Recommendation:** don't adopt this as the Track D5 deliverable. If the fold-back-free upgrade is worth chasing later, the correct next step is to run the actual Overpass query, diff the resulting district names against `data/seed/districts.csv` state by state, and decide from that - not from an unverified claim. Treat it as a backlog item, not a blocker for shipping D5.

---

## Q2 - Census 2011 alignment and bifurcations

**The DataMeet layer reflects Census 2011 boundaries, not recent bifurcations** - which is exactly what the project's `data/seed/districts.csv` naming assumes. Empirical counts from the layer (2026-09-23): **Maharashtra 35, Uttar Pradesh 71, Haryana 21, Jharkhand 24 = 151 polygons** **[VERIFIED]**.

Post-2011 districts in these four states have no polygon in a Census-2011 layer. Fold them back into their 2011 parent for the heatmap (one-way mapping in the join code):

| Current district | 2011 parent polygon | Year | Source |
|---|---|---|---|
| Palghar (MH) | Thane | 2014 | https://palghar.gov.in/en/about-district/ (official) **[VERIFIED]** |
| Charkhi Dadri (HR) | Bhiwani | 2016 | Jaacks Research Group district-changes tracker **[VERIFIED vs secondary source]** |
| Amethi (UP) | Sultanpur | 2010 (as Chhatrapati Shahuji Maharaj Nagar) | same tracker **[VERIFIED vs secondary source]** |
| Hapur (UP) | Ghaziabad | 2011 (as Panchsheel Nagar) | same tracker **[VERIFIED vs secondary source]** |
| Shamli (UP) | Muzaffarnagar | 2011 (as Prabuddha Nagar) | same tracker **[VERIFIED vs secondary source]** |
| Sambhal (UP) | Moradabad | 2011 (as Bheem Nagar) | same tracker **[VERIFIED vs secondary source]** |

(Tracker: https://github.com/Jaacks-Research-Group/india-district-changes-tracker - cross-consistent with indiastatestory.in district-change summary. Hansi, HR's 2024 23rd district from Hisar, is out of scope per the project spec fixing HR at 22.)

**Catalog count doesn't reconcile with this table - check before wiring the join [flagged during this merge, UNVERIFIED against the actual file]:** the original brief states the reference catalog has **159** districts across these four states. Current official counts, confirmed by live search for this merge (2026-09-23): Maharashtra 36, Uttar Pradesh 75, Haryana 22 (with Hansi excluded per spec), Jharkhand 24 - **157**, not 159. That figure matches the fold-back table above exactly: 151 (DataMeet's 2011 baseline) + 6 (the rows above) = 157. Neither research pass reconciles the extra 2. Before building the join, get the actual row count from `data/seed/districts.csv` - if it really is 159, those 2 rows need to be identified (duplicate row, a not-yet-notified district, something else) and given a fold-back parent of their own, or 2 districts will silently render with no boundary at demo time.

**Property mapping for the join** (strings read directly from the data) **[VERIFIED]**:
- Filter states on `ST_NM` with exact values: `Maharashtra`, `Uttar Pradesh`, `Haryana`, `Jharkhand`.
- Join districts on `DISTRICT` (title case) or, better, on census codes: `ST_CEN_CD` + `DT_CEN_CD`, or the combined `censuscode`. Codes are immune to renames; prefer them if `districts.csv` carries census codes.
- 2011-era names in the layer that differ from current official names: `Allahabad` (Prayagraj), `Faizabad` (Ayodhya), `Kansiram Nagar` (Kasganj), `Mahamaya Nagar` (Hathras), `Jyotiba Phule Nagar` (Amroha), `Kheri` (Lakhimpur Kheri), `Bara Banki` (Barabanki), `Shrawasti` (Shravasti), `Sant Ravi Das Nagar(bhadohi)` (Bhadohi), `Gurgaon` (Gurugram), `Mewat` (Nuh), `Ahmadnagar` (Ahilyanagar), `Aurangabad` (Chhatrapati Sambhajinagar), `Bid` (Beed), `Osmanabad` (Dharashiv). **[VERIFIED for the layer's strings; rename years from the tracker above]**
- If a bifurcated-district polygon set is ever required instead of fold-back: GADM has Palghar/Hapur/Shamli/Sambhal but not Charkhi Dadri and is licence-blocked; SoI is the only current official source (licence UNVERIFIED); OSM is the only candidate that could plausibly have all of them natively, contingent on the Q1.5 verification above. Fold-back is the practical strategy today.

---

## Q3 - GeoJSON size and simplification (measured, not estimated)

Pipeline executed on 2026-09-23 (mapshaper 0.6.x via npx, from the DataMeet shapefile): **[VERIFIED]**

| Output | Size |
|---|---|
| 4-state extract, full-fidelity GeoJSON (precision 1e-7) | 2.13 MB (2,230,595 B) |
| Simplified GeoJSON, visvalingam keep-shapes 15%, precision 1e-4 | 0.28 MB (291,935 B) |
| Simplified GeoJSON, visvalingam keep-shapes 8%, precision 1e-4 | 0.17 MB (176,424 B) |
| TopoJSON, simplify 12% + quantization=100000 | 0.10 MB (109,153 B) |

The simplified outputs keep all 151 features and all 5 attribute fields (verified by parsing the output). **Yes: the 4-state file lands far under 2 MB** even at full fidelity; ~10-15% simplification is visually lossless at choropleth zoom levels and leaves ~0.1-0.3 MB. Exact commands:

```bash
mkdir -p /tmp/dm && cd /tmp/dm
base="https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011"
for ext in shp shx dbf prj sbn sbx; do curl -sL -o "2011_Dist.$ext" "$base/2011_Dist.$ext"; done

npx mapshaper 2011_Dist.shp \
  -filter "['Maharashtra','Uttar Pradesh','Haryana','Jharkhand'].includes(ST_NM)" \
  -o format=geojson precision=0.0000001 districts_4st_full.geojson

npx mapshaper districts_4st_full.geojson \
  -simplify visvalingam keep-shapes 12% \
  -o format=geojson precision=0.0001 districts_4st.geojson
# or, smallest: -o format=topojson quantization=100000 districts_4st.topojson
```

Commit `districts_4st.geojson` (or `.topojson`) to `data/geo/`. Keep the full-fidelity extract out of the repo (reproducible with the commands above).

---

## Q4 - Attribution (exact clauses)

Required by CC BY 2.5 India: credit + licence link + indication of changes. Sources: licence text https://creativecommons.org/licenses/by/2.5/in/; attribution style per repo README example. **[VERIFIED]**

**README.md:**

> District boundary polygons (Census 2011, filtered to Maharashtra, Uttar Pradesh, Haryana and Jharkhand, geometry simplified) by the [DataMeet India community](http://datameet.org/) - source: [datameet/maps, Districts/Census_2011](https://github.com/datameet/maps/tree/master/Districts/Census_2011) - licensed under [CC BY 2.5 India](https://creativecommons.org/licenses/by/2.5/in/). Boundaries simplified with mapshaper; the district set reflects Census 2011 (no post-2011 bifurcations).

**Web UI footer (short form):**

> District boundaries (c) DataMeet community, CC BY 2.5 India - Census 2011

Keep this separate from the existing ODbL attribution for the OSM-derived ATM/branch/agent points - the two layers have different licences and both attribution lines must stay. (This stays true even if OSM boundaries are adopted later - it would just mean both layers share one ODbL notice instead of two different ones.)

---

## Verification ledger

- VERIFIED by reading the primary page: DataMeet licence (CC BY 2.5 IN, Districts README), GADM licence text, Bhuvan terms of service, SoI product catalog and data.gov.in catalog state.
- VERIFIED by executing the pipeline: shapefile contents, CRS, attribute keys and exact state strings, 151-feature 4-state extract, all output sizes, simplification outputs, GADM 4.1 India staleness/quality issues.
- VERIFIED by live search for this merge: current official district counts (MH 36, UP 75, HR 22, JH 24 = 157, sourced against current 2026 state-wise district references); OSM `admin_level=5` India coverage has a documented history of gaps and provenance concerns (2018 talk-in mailing-list threads; the OSM wiki's per-state district-mapping pages are the way to check current status, not checked here for these 4 states specifically).
- UNVERIFIED: SoI redistribution terms (no public licence text found; portal points to a pricing list and registration - the "no foreign resale" characterisation is plausible but unconfirmed on a public page). Bifurcation fold-back pairs are verified against the secondary sources cited above, not against state gazette notifications - sufficient for a demo heatmap join, re-check against gazette only if the mapping becomes load-bearing. OSM's actual current per-district coverage for MH/UP/HR/JH - nobody has run the query yet. The 159 vs. 157 catalog discrepancy - nobody has opened `data/seed/districts.csv` to check yet.

---

## Dropped from this merge

The parallel pass's Part B (bank/ATM/branch point sources - OSM/Overpass, Geofabrik zonal extracts, RBI DBIE, data.gov.in) is not included above. It re-does work the brief explicitly says is already complete and committed (`data/geo/atm_branch_agent_locations.csv`, OSM ODbL) and was on the brief's "DO NOT RESEARCH" list. If that existing file ever needs a refresh, it's a separate task, not part of D5.
