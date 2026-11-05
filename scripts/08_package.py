"""
Step 08: validate everything and build the Railyard import zip:
release/BUH-<version>.zip  (flat: config.json, BUH.pmtiles, demand_data.json.gz,
buildings_index.bin.gz, roads.geojson.gz, runways_taxiways.geojson.gz,
ocean_depth_index*.json.gz, .railyard_map/ special-demand schemas)
"""
import gzip
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import config as C
from buhlib import haversine_m, read_json, write_json

errors, warns = [], []
M, D = C.MAP_DIR, C.DEMAND_DIR
fdemand = os.path.join(D, "demand_data.json")

# ---------------------------------------------------------------- demand checks
dd = read_json(fdemand)
pts = {p["id"]: p for p in dd["points"]}
unrouted = 0
for p in dd["pops"]:
    if p["residenceId"] not in pts or p["jobId"] not in pts:
        errors.append(f"pop {p['id']} references a missing point")
    if not (0 < p["size"] <= C.MAXPOPSIZE):
        errors.append(f"pop {p['id']} has size {p['size']}")
    if not p.get("drivingSeconds"):
        a, b = pts[p["residenceId"]]["location"], pts[p["jobId"]]["location"]
        d = float(haversine_m(a[0], a[1], b[0], b[1])) * 1.3
        p["drivingDistance"], p["drivingSeconds"] = max(int(d), 1), max(int(d / 8.33), 1)
        unrouted += 1
if unrouted:
    warns.append(f"{unrouted:,} pops had no OSRM route; used straight-line estimates "
                 "(run steps 06-07 for real driving times)")
for p in dd["points"]:
    lon, lat = p["location"]
    if not (C.BBOX[0] <= lon <= C.BBOX[2] and C.BBOX[1] <= lat <= C.BBOX[3]):
        warns.append(f"point {p['id']} lies outside BBOX")
total = sum(p["size"] for p in dd["pops"])
print(f"Demand: {len(dd['points']):,} points, {len(dd['pops']):,} pops, {total:,} people")

# ---------------------------------------------------------------- config.json
try:
    from depot.demand import DemandData
    obj = DemandData(fdemand, C.CODE, bbox=C.BBOX, outputdir=D, verb=False)
    obj.create_config(name=C.NAME, bbox=C.BBOX, description=C.DESCRIPTION,
                      creator=C.CREATOR, version=C.VERSION, country=C.COUNTRY,
                      initial_view_state=C.INITIAL_VIEW)
    cfg = read_json(os.path.join(D, "config.json"))
    cfg["initialViewState"]["zoom"] = C.INITIAL_ZOOM
except ImportError:  # depot not installed: write the same structure ourselves
    cfg = {"code": C.CODE, "name": C.NAME, "bbox": C.BBOX,
           "description": C.DESCRIPTION, "population": total,
           "initialViewState": {"latitude": C.INITIAL_VIEW[1], "longitude": C.INITIAL_VIEW[0],
                                "zoom": C.INITIAL_ZOOM, "bearing": 0},
           "creator": C.CREATOR, "version": C.VERSION, "country": C.COUNTRY}
import json
with open(os.path.join(D, "config.json"), "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False)

# ---------------------------------------------------------------- assemble
out = os.path.join(C.RELEASE_DIR, C.CODE)
if os.path.exists(out):
    shutil.rmtree(out)
os.makedirs(out)


def gz(src, dst):
    with open(src, "rb") as fi, gzip.open(dst, "wb", compresslevel=9) as fo:
        shutil.copyfileobj(fi, fo)


write_json(os.path.join(out, "demand_data.json.gz"), dd, gz=True)
shutil.copy(os.path.join(D, "config.json"), out)
files = {
    f"{C.CODE}.pmtiles": ("copy", True),
    "buildings_index.bin.gz": ("copy", True),
    "roads.geojson": ("gz", True),
    "runways_taxiways.geojson": ("gz", False),
    "ocean_depth_index.json.gz": ("copy", False),
    "ocean_depth_index_contours.json.gz": ("copy", False),
}
for name, (how, required) in files.items():
    src = os.path.join(M, name)
    if not os.path.exists(src):
        (errors if required else warns).append(f"missing {src}")
        continue
    if how == "gz":
        gz(src, os.path.join(out, name + ".gz"))
    else:
        shutil.copy(src, out)
schema_dir = os.path.join(D, ".railyard_map")
if os.path.isdir(schema_dir):
    shutil.copytree(schema_dir, os.path.join(out, ".railyard_map"))

for w in warns:
    print("WARNING:", w)
if errors:
    for e in errors[:20]:
        print("ERROR:", e)
    sys.exit(f"{len(errors)} error(s); zip not built.")

zpath = os.path.join(C.RELEASE_DIR, f"{C.CODE}-{C.VERSION}.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, fs in os.walk(out):
        for fn in fs:
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, out))
size = os.path.getsize(zpath) / 1e6
print(f"\nBuilt {zpath} ({size:.0f} MB). Import it in Railyard (local map import).")
