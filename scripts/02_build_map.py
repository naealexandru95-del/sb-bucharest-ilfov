"""
Step 02: map files with depot MapGen.
Produces in work/BUH/: BUH.pmtiles, BUH_foundations.pmtiles, buildings_index.bin(.gz),
roads.geojson, runways_taxiways.geojson, ocean_depth_index.json.gz, buildings.pkl.

Usage:  python scripts/02_build_map.py            # everything
        python scripts/02_build_map.py buildings  # one stage (extract|buildings|roads|tiles|labels|check_labels)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config as C
from depot.maps import MapGen

os.makedirs(C.WORK, exist_ok=True)
gen = MapGen(city=C.CODE, bbox=C.BBOX, osmpbf=C.OSM_PBF, outputdir=C.WORK,
             create_ocean_foundations=True, **C.MAPGEN)

stages = {
    "extract": gen.extract_base_data,
    "buildings": gen.process_buildings,
    "roads": gen.process_roads_and_aeroways,
    "tiles": gen.generate_pmtiles,
    "labels": gen.add_labels,
    "check_labels": gen.check_labels,
}
wanted = sys.argv[1:] or ["extract", "buildings", "roads", "tiles", "labels"]
for s in wanted:
    if s not in stages:
        sys.exit(f"Unknown stage {s!r}; choose from {list(stages)}")
    print(f"\n######## {s} ########", flush=True)
    stages[s]()
print("\nMap files are in", C.MAP_DIR)
