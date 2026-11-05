"""
Offline self-test: builds a small synthetic Bucharest-like dataset (fake OSM
extracts + fake Overture buildings) in tests/_work, runs step 04 and step 08 on
it and checks the demand file against the game's schema rules.

    python tests/selftest.py
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon, box, mapping
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "tests", "_work")
shutil.rmtree(WORK, ignore_errors=True)
OSM = os.path.join(WORK, "osm"); MAP = os.path.join(WORK, "BUH")
os.makedirs(OSM); os.makedirs(MAP)
rng = np.random.default_rng(1)
CX, CY = 26.10, 44.435          # city centre
KX, KY = 1 / 78_500, 1 / 111_000  # deg per metre (approx)


def write_seq(name, feats):
    with open(os.path.join(OSM, name), "w") as f:
        for i, (geom, props) in enumerate(feats):
            props = {"@type": "way", "@id": i + 1, **props}
            f.write("\x1e" + json.dumps({"type": "Feature", "geometry": mapping(geom),
                                         "properties": props}) + "\n")


# --- admin: Bucharest = 10 km circle split in 6 wedges; Ilfov = box minus circle
city = Point(CX, CY).buffer(10_000 * KX, 64)
city = Polygon([(CX + (x - CX), CY + (y - CY) * KY / KX) for x, y in city.exterior.coords])
ilfov = box(CX - 0.35, CY - 0.22, CX + 0.35, CY + 0.25).difference(city)
admin = [(city, {"boundary": "administrative", "admin_level": "4", "name": "Municipiul București"}),
         (ilfov, {"boundary": "administrative", "admin_level": "4", "name": "Ilfov"})]
for s in range(6):
    a0, a1 = s * np.pi / 3, (s + 1) * np.pi / 3
    wedge = Polygon([(CX, CY)] + [(CX + 0.5 * np.cos(t), CY + 0.5 * np.sin(t))
                                  for t in np.linspace(a0, a1, 20)])
    admin.append((wedge.intersection(city), {"boundary": "administrative",
                  "admin_level": "9", "name": f"Sectorul {s + 1}"}))
towns = {"Voluntari": (CX + 0.17, CY + 0.07), "Chiajna": (CX - 0.18, CY + 0.0),
         "Popești-Leordeni": (CX + 0.09, CY - 0.12)}
for n, (x, y) in towns.items():
    admin.append((box(x - 0.04, y - 0.03, x + 0.04, y + 0.03).intersection(ilfov),
                  {"boundary": "administrative", "admin_level": "8", "name": n}))
write_seq("admin.geojsonseq", admin)

census = pd.DataFrame(
    [("B", f"Sector {i}", "sector", v) for i, v in
     enumerate([217367, 291557, 374737, 268018, 240288, 324994], 1)] +
    [("IF", "Voluntari", "oras", 47366), ("IF", "Chiajna", "comuna", 43588),
     ("IF", "Popești-Leordeni", "oras", 53434), ("IF", "Otopeni", "oras", 21750)],
    columns=["county", "uat", "type", "population_2021"])
census.to_csv(os.path.join(WORK, "census.csv"), index=False)

# --- buildings
feats, ov = [], []
def add_bldg(x, y, w, h, tags, height=None):
    g = box(x, y, x + w * KX, y + h * KY)
    feats.append((g, tags)); ov.append({"id": f"o{len(ov)}", "geometry": g, "name": None,
                                        "height": height})
n_city = 6000
r = np.abs(rng.normal(0, 4500, n_city)); t = rng.uniform(0, 2 * np.pi, n_city)
for ri, ti in zip(r, t):
    x, y = CX + ri * np.cos(ti) * KX, CY + ri * np.sin(ti) * KY
    if ri < 1500 and rng.random() < 0.5:
        add_bldg(x, y, 40, 30, {"building": "office", "building:levels": "8"})
    elif rng.random() < 0.7:
        add_bldg(x, y, 60, 14, {"building": "yes"}, height=rng.choice([12.0, 27.0, None]))
    else:
        add_bldg(x, y, 12, 10, {"building": "house"})
for n, (tx, ty) in towns.items():
    for _ in range(900):
        add_bldg(tx + rng.normal(0, 0.012), ty + rng.normal(0, 0.009), 12, 11, {"building": "yes"})
    for _ in range(60):
        add_bldg(tx + rng.normal(0, 0.02), ty + rng.normal(0, 0.015), 90, 60, {"building": "warehouse"})
add_bldg(26.0850, 44.5711, 300, 80, {"building": "yes", "aeroway": "terminal"})
for _ in range(50):
    add_bldg(CX + rng.uniform(-0.1, 0.1), CY + rng.uniform(-0.1, 0.1), 3, 4, {"building": "shed"})
write_seq("buildings.geojsonseq", feats)
import geopandas as gpd
pd.to_pickle(pd.DataFrame(ov), os.path.join(MAP, "buildings.pkl"))

# --- land use: residential everywhere in the city, a commercial core
write_seq("landuse.geojsonseq", [
    (city, {"landuse": "residential"}),
    (Point(CX, CY).buffer(0.012), {"landuse": "commercial"}),
    (box(26.075, 44.560, 26.095, 44.580), {"aeroway": "aerodrome"}),
])
write_seq("pois.geojsonseq", [(Point(CX + rng.normal(0, 0.03), CY + rng.normal(0, 0.02)),
                               {"shop": "convenience"}) for _ in range(800)])
for fn in ("BUH.pmtiles", "buildings_index.bin.gz", "roads.geojson"):
    open(os.path.join(MAP, fn), "w").write("{}")

# --- run step 04 and 08
env = {**os.environ, "BUH_WORKDIR": WORK, "BUH_CENSUS": os.path.join(WORK, "census.csv"),
       "MPLBACKEND": "Agg", "BUH_RELEASE": os.path.join(WORK, "release")}
py = sys.executable
subprocess.run([py, os.path.join(ROOT, "scripts", "04_build_demand.py")], env=env, check=True)

# --- schema checks (mirror of the game's DemandDataSchema)
dd = json.load(open(os.path.join(WORK, "demand", "demand_data.json")))
ids = {p["id"] for p in dd["points"]}
assert set(dd) == {"points", "pops"}
for p in dd["points"]:
    assert isinstance(p["id"], str) and len(p["location"]) == 2
    assert isinstance(p["jobs"], int) and isinstance(p["residents"], int)
    assert isinstance(p["popIds"], list) and p["popIds"]
for q in dd["pops"]:
    assert q["residenceId"] in ids and q["jobId"] in ids
    assert 0 < q["size"] <= 200
    assert set(q) >= {"id", "size", "residenceId", "jobId", "drivingSeconds", "drivingDistance"}
res = sum(p["residents"] for p in dd["points"]); jobs = sum(p["jobs"] for p in dd["points"])
assert res == jobs == sum(q["size"] for q in dd["pops"])
target = census["population_2021"].sum() * 0.62
assert abs(res - target) / target < 0.02, (res, target)
print(f"\nSchema OK: {len(dd['points'])} points, {len(dd['pops'])} pops, {res:,} trips "
      f"(target {target:,.0f})")

subprocess.run([py, os.path.join(ROOT, "scripts", "08_package.py")], env=env, check=True)
print("\nSELFTEST PASSED")
