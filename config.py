"""
Central configuration for the Bucuresti + Ilfov Subway Builder map.
Every script imports this file, so tune things here and re-run the step.
"""
import os

# ---------------------------------------------------------------- identity
CODE = "BUH"                       # IATA metro code for Bucharest; 2-4 chars
NAME = "București + Ilfov"
DESCRIPTION = ("Bucharest and Ilfov County: six sectors and 40 towns and "
               "communes, ~2.26M people (2021 census), Henri Coandă airport.")
CREATOR = "naealexandru95-del"
VERSION = "0.1.0"
COUNTRY = "RO"
INITIAL_VIEW = [26.1025, 44.4355]  # [lon, lat] Piața Universității
INITIAL_ZOOM = 12

# Map extent: Bucharest + all of Ilfov with a little margin.
# [min_lon, min_lat, max_lon, max_lat]
BBOX = [25.78, 44.19, 26.50, 44.79]

# ---------------------------------------------------------------- paths
ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("BUH_WORKDIR", os.path.join(ROOT, "work"))
DATA = os.path.join(ROOT, "data")
OSM_PBF = os.path.join(WORK, "romania-latest.osm.pbf")
GEOFABRIK_URL = "https://download.geofabrik.de/europe/romania-latest.osm.pbf"
MAP_DIR = os.path.join(WORK, CODE)          # depot MapGen output (WORK/BUH)
OSM_DIR = os.path.join(WORK, "osm")         # our own extracts for the demand model
DEMAND_DIR = os.path.join(WORK, "demand")
RELEASE_DIR = os.environ.get("BUH_RELEASE", os.path.join(ROOT, "release"))

# ---------------------------------------------------------------- depot MapGen
MAPGEN = dict(
    building_index_filter_size=40,   # m2; smaller buildings get no collision
    building_tile_filter_size=20,    # m2; smaller buildings not drawn
    building_index_simplification=1,
    building_tile_simplification=1,
    maxzoom=15,
    ncores=os.cpu_count(),           # must be an int (depot's bathymetry step needs it)
    RAM=8,                           # GB for mapshaper; raise on heap errors
    cleanup_files=True,
    cities=["city", "town"],
    suburbs=["suburb", "village"],
    neighborhoods=["quarter", "neighbourhood", "hamlet"],
)

# ---------------------------------------------------------------- demand model
CENSUS_CSV = os.environ.get("BUH_CENSUS", os.path.join(DATA, "census_2021.csv"))
# Population growth applied on top of the 2021 census, per county.
# Ilfov has grown fast since 2021; bump it here if you want (e.g. 1.10).
GROWTH = {"B": 1.00, "IF": 1.00}

# Share of residents that make a daily commute trip (workers + students).
# 0.5 ≈ employed only; 0.62 adds commuting students; 1.0 is what some
# community maps use (every resident becomes a pop) for a busier game.
TRIP_SHARE = 0.62

# Where the trips end. Bucharest holds ~1.10M employees vs ~0.22M in Ilfov
# (INS, 2025-26), so ~83% of destinations are in the city.
DEST_SHARE = {"B": 0.83, "IF": 0.17}

CELL_M = 400                 # grid cell size (m) that becomes one demand point
MIN_POINT_SIZE = 10          # drop cells with fewer residents+jobs than this
TARGET_MEAN_TRIP_KM = 9.5    # gravity model is calibrated to this mean (straight-line ×1.25)
DETOUR = 1.25                # straight-line → road distance factor
MIN_TRIP_M = 800             # trips shorter than this are suppressed ×0.15 (people walk)
POP_UNIT = 35                # people per sampling unit → controls pop count (~TRIP_TOTAL / POP_UNIT)
MAXPOPSIZE = 200             # keep ≤ train capacity
FURNESS_ITERS = 20
SEED = 42

# How residents are pinned to the census:
#  "uat"    – every sector/commune keeps its exact 2021 population; ZONES only
#             move people around *inside* a sector or commune (default)
#  "county" – only Bucharest and Ilfov totals are fixed; ZONES can move people
#             between sectors (e.g. make the south denser than the north)
RES_CALIBRATION = "uat"

# Hand-painted adjustments. Each zone is a circle (center [lon, lat], radius in
# metres) with a soft edge: full effect inside radius, fading to none at 1.5×.
# "res" multiplies residential weight, "jobs" multiplies job weight.
# Totals stay fixed, so boosting one place takes from the rest of the same
# sector/commune (residents) or county (jobs). Overlapping zones multiply.
# Re-run steps 4-8 after editing.
ZONES = [
    # --- north: business districts
    {"name": "Pipera offices (Dimitrie Pompeiu)", "center": [26.112, 44.480], "radius_m": 1500, "jobs": 3.0},
    {"name": "Pipera Voluntari",                  "center": [26.125, 44.500], "radius_m": 1200, "jobs": 2.0},
    {"name": "Floreasca / Barbu Văcărescu",       "center": [26.105, 44.465], "radius_m": 1000, "jobs": 2.5},
    {"name": "Băneasa",                           "center": [26.080, 44.505], "radius_m": 1500, "jobs": 2.5},
    # --- north: fewer residents (villas, parks, embassies)
    {"name": "Primăverii / Herăstrău / Băneasa",  "center": [26.085, 44.470], "radius_m": 2000, "res": 0.7},
    # --- south: dense housing estates
    {"name": "Berceni",                           "center": [26.115, 44.375], "radius_m": 2000, "res": 1.3},
    {"name": "Rahova / Ferentari",                "center": [26.070, 44.400], "radius_m": 1800, "res": 1.3},
    {"name": "Giurgiului",                        "center": [26.090, 44.383], "radius_m": 1500, "res": 1.3},
    # --- Ilfov
    {"name": "Militari Residence (Chiajna)",      "center": [25.975, 44.440], "radius_m": 1000, "res": 1.8},
    {"name": "Militari Shopping / Chiajna retail","center": [25.990, 44.432], "radius_m": 1200, "jobs": 1.8},
    {"name": "A1 logistics (CTPark West)",        "center": [25.925, 44.440], "radius_m": 1800, "jobs": 2.0},
    {"name": "Otopeni airport + DN1 industry",    "center": [26.070, 44.555], "radius_m": 1800, "jobs": 2.0},
    {"name": "Afumați / Ștefănești DN2 logistics","center": [26.240, 44.520], "radius_m": 1500, "jobs": 1.8},
    {"name": "Popești-Leordeni industrial",       "center": [26.155, 44.390], "radius_m": 1500, "jobs": 1.6},
    {"name": "Măgurele physics platform",         "center": [26.030, 44.350], "radius_m": 1200, "jobs": 2.0},
    # --- east Bucharest jobs
    {"name": "Arena Națională / Mega Mall",       "center": [26.153, 44.439], "radius_m": 900,  "jobs": 2.0},
    {"name": "Republica / Faur (Titan industry)", "center": [26.178, 44.437], "radius_m": 1300, "jobs": 2.0},
    {"name": "Pantelimon / Cora",                 "center": [26.205, 44.452], "radius_m": 1200, "jobs": 1.8},
    {"name": "Vitan / Timpuri Noi offices",       "center": [26.125, 44.415], "radius_m": 1200, "jobs": 2.0},
]

# Floors assumed when neither height nor building:levels is known.
DEFAULT_LEVELS = {
    "apartments_large": 8,   # bloc footprint > 600 m2 (Drumul Taberei, Titan, Berceni…)
    "apartments": 5,
    "house": 1.5,
    "office": 6, "retail": 1.5, "mall": 2, "industrial": 1, "warehouse": 1,
    "education": 3, "health": 4, "public": 3, "hotel": 6, "mixed": 4,
    "other": 1,
}
# Residents per m2 of floor area are calibrated to the census, so only the
# relative weight matters. Houses get a bit more per m2 (fewer common areas).
RES_WEIGHT = {"apartments_large": 1.0, "apartments": 1.0, "house": 1.15,
              "mixed": 0.6}
# Jobs per m2 of floor area (relative; rescaled to DEST_SHARE totals).
JOB_WEIGHT = {
    "office": 1 / 15, "retail": 1 / 35, "mall": 1 / 40, "industrial": 1 / 90,
    "warehouse": 1 / 180, "education": 1 / 25, "health": 1 / 30,
    "public": 1 / 25, "hotel": 1 / 80, "mixed": 1 / 120,
    "apartments_large": 1 / 1500, "apartments": 1 / 1500, "house": 1 / 3000,
    "other": 1 / 400,
}
# Extra jobs for OSM points (ground-floor shops, offices in mixed blocks).
POI_JOBS = {"shop": 4, "office": 12, "amenity": 3, "craft": 3, "tourism": 4,
            "healthcare": 6}

# ---------------------------------------------------------------- routing
OSRM_PORT = 5000
ROUTE_THREADS = 16
INCLUDE_DRIVING_PATHS = True
PATH_SIMPLIFY_TOL = 0.0002
SPECIAL_DEMAND_JSON = os.path.join(DATA, "special_demand.json")
