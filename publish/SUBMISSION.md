# Railyard submission: copy-paste values

Form: https://github.com/Subway-Builder-Modded/The-Railyard/issues/new/choose → **Publish a New Map**

| Field | Value |
|---|---|
| Map ID | `bucharest-ilfov` |
| City Name | `București + Ilfov` |
| Additional Cities | `Voluntari, Popești-Leordeni, Chiajna, Bragadiru, Pantelimon, Otopeni, Buftea, Măgurele` |
| City Code | `BUH` |
| Country Code | `RO` |
| Data Source | `INS RPL2021, INS employee statistics, OSM, Overture` |
| Special Demand | ☑ airports ☑ entertainment ☑ hospitals ☑ parks ☑ universities |
| Gallery Images | drag in 1–3 in-game screenshots |
| Source URL | `https://github.com/naealexandru95-del/sb-bucharest-ilfov` |
| Update Type | GitHub Releases |
| GitHub Repository | `naealexandru95-del/sb-bucharest-ilfov` |
| Terms | tick both |

## Description

```
Bucharest and all of Ilfov County: the 6 sectors plus 40 towns and communes (~2.26M residents, 2021 census), ~1.71M daily trips across ~3,900 demand points.

- Residents from the 2021 census per sector/commune, placed on Overture building footprints by residential floor area
- Jobs placed by building type (offices, retail, industry, schools, hospitals), with hand-tuned business districts (Pipera, Floreasca, Băneasa, A1/DN2 logistics)
- Special demand: Henri Coandă airport, 7 universities, major malls, Arena Națională, Romexpo, parks, hospitals (estimated visitor figures)
- Real driving times from OSRM

Data: © OpenStreetMap contributors, Overture Maps, INS Romania. Built with depot.
```

## Methodology (single line field)

```
Residents: INS 2021 census total population per UAT (6 Bucharest sectors + 40 Ilfov towns/communes), spread over Overture building footprints typed with OSM building/landuse tags, weighted by residential floor area (footprint × OSM levels/height, generic floor defaults otherwise). Jobs: no per-area workplace data; trip destinations = 62% of residents, split 83% Bucharest / 17% Ilfov from INS county employee counts, placed by building-type floor area with generic job densities plus OSM shop/office POIs, then adjusted with hand-tuned zone multipliers for known business districts. Flows: doubly-constrained gravity model (exponential decay, calibrated to 9.5 km mean trip) against these resident/destination totals; no measured O/D. Driving times from OSRM. Special demand added with depot add_points using estimated visitor/student figures. Vintages: census 2021, employee totals 2025-26, OSM/Overture 2026.
```

## Data-quality questions

| # | Question | Answer |
|---|---|---|
| 1 | Where do your job numbers come from? | Estimated from population or other indirect statistics |
| 2 | Smallest area for job numbers | Counties or larger regions |
| 3 | How were jobs placed? | Building footprints, split by workplace type using priors |
| 4 | What do population numbers count? | Total population, including children and retirees |
| 5 | Smallest area for population numbers | Whole cities or municipalities |
| 6 | How were people placed? | Building footprints, with homes identified and weighted using priors |
| 7 | Commute flow data? | No — flows are fully estimated |
| 8 | Smallest area of flow data | (leave blank) |
