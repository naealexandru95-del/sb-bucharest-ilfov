# București + Ilfov for Subway Builder

A complete build pipeline for a custom Subway Builder map of Bucharest and all of
Ilfov County (code **BUH**). It produces a zip you import with
[Railyard](https://github.com/j4lambert/railyard), the community map/mod manager.

| Piece | How it's made |
|---|---|
| Map tiles, buildings (collision `.bin`), roads, airport runways, water depth | [depot](https://github.com/Subway-Builder-Modded/depot) `MapGen` from the Geofabrik Romania extract + Overture building footprints |
| Residents | 2021 census per UAT (6 sectors + 40 Ilfov towns/communes, `data/census_2021.csv`) spread over residential floor area of every building |
| Jobs / destinations | Bucharest ≈ 83 %, Ilfov ≈ 17 % of trips (INS employee counts), spread over offices, retail, industry, schools, hospitals and OSM shop/office points |
| Commutes | Doubly-constrained gravity model, calibrated to a 9.5 km mean trip, sampled into pops ≤ 200 people |
| Special demand | Henri Coandă airport, 7 universities, 9 malls, Arena Națională, Romexpo, 4 parks, 3 hospitals (`data/special_demand.json`) |
| Driving times | Local OSRM server in Docker |

## 1. One-time setup (Windows)

Run in **PowerShell as admin**:

```powershell
wsl --install -d Ubuntu-24.04
```

Give WSL enough memory: create `%UserProfile%\.wslconfig` with

```ini
[wsl2]
memory=24GB
processors=12
```

then `wsl --shutdown`. (depot's tile step runs Java with 16 GB.)

Install **Docker Desktop** and enable *Settings → Resources → WSL integration → Ubuntu-24.04* (needed for step 6).

Copy this folder into WSL (e.g. `\\wsl$\Ubuntu-24.04\home\<you>\bucharest-subwaybuilder`), then in an Ubuntu terminal:

```bash
cd ~/bucharest-subwaybuilder
chmod +x run_all.sh scripts/*.sh
bash scripts/00_setup_wsl.sh      # 15–30 min: osmium, gdal, tippecanoe, pmtiles, planetiler, conda env "depot"
source ~/.bashrc
conda activate depot
python tests/selftest.py          # optional: checks the demand model on synthetic data
```

## 2. Build

```bash
conda activate depot
./run_all.sh                      # all 8 steps, roughly 1–2 h
```

or step by step:

| Step | Command | Output |
|---|---|---|
| 1 | `bash scripts/01_download.sh` | `work/romania-latest.osm.pbf` |
| 2 | `python scripts/02_build_map.py` | `work/BUH/` tiles, buildings index, roads |
| 3 | `bash scripts/03_extract_osm.sh` | `work/osm/` building tags, land use, POIs, boundaries |
| 4 | `python scripts/04_build_demand.py` | `work/demand/demand_data.json` + QA in `work/demand/qa/` |
| 5 | `python scripts/05_special_demand.py` | airport/university/mall… demand added |
| 6 | `bash scripts/06_osrm.sh` | OSRM routing server on port 5000 |
| 7 | `python scripts/07_routes.py` | driving time/distance/path for each pop |
| 8 | `python scripts/08_package.py` | **`release/BUH-0.1.0.zip`** |

## 3. Play

1. Install Railyard and point it at your Subway Builder install.
2. Use Railyard's local map import and pick `release/BUH-0.1.0.zip` (from Windows it's at `\\wsl$\Ubuntu-24.04\home\<you>\bucharest-subwaybuilder\release\`).
3. Launch the game from Railyard; the city appears under the modded cities.

## 4. Check and tune

After step 4, look at:
- `work/demand/qa/demand_map.png`: residents and destinations density
- `work/demand/qa/uat_check.csv`: census population assigned per sector/commune
- `work/demand/qa/points.geojson`: open in QGIS or geojson.io
- the console summary of flows (e.g. share of Ilfov residents commuting into Bucharest)

Knobs in `config.py` (re-run from step 4):

| Setting | Effect |
|---|---|
| `TRIP_SHARE` | 0.62 = workers + students. Raise toward 1.0 for a busier game |
| `GROWTH` | Bump Ilfov above 1.0 to account for growth since 2021 |
| `DEST_SHARE` | Bucharest vs Ilfov share of destinations |
| `TARGET_MEAN_TRIP_KM` | Longer/shorter commutes |
| `CELL_M` | Demand point spacing (smaller = more points, slower game) |
| `POP_UNIT` | People per pop sample (smaller = more pops) |
| `BBOX` | Map extent |

Special demand sizes and coordinates are in `data/special_demand.json`. The coordinates are approximate; each point absorbs base points within `merge_within` metres, so a ~100 m error doesn't matter. Edit and re-run steps 5, 7, 8.

## Troubleshooting

- **`Missing required CLI tools`** (step 2): open a new terminal after setup, or `source ~/.bashrc`.
- **mapshaper heap errors**: raise `MAPGEN["RAM"]` in `config.py`.
- **Java out of memory**: raise `memory=` in `.wslconfig`.
- **Overture download fails** (step 2): DuckDB needs internet access to `overturemaps-us-west-2` on S3. Retry, or re-run `python scripts/02_build_map.py buildings`.
- **Labels look sparse or crowded**: `python scripts/02_build_map.py check_labels`, adjust `cities/suburbs/neighborhoods` in `config.py`, then re-run `tiles labels`.
- **OSRM won't start**: check that Docker Desktop is running and WSL integration is on; see `docker logs buh-osrm`.

## Data & licences
OpenStreetMap contributors (ODbL) · Overture Maps Foundation · INS Romania, 2021 census (via citypopulation.de) · depot (GPLv3).
