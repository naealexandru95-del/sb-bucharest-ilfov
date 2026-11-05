"""
Step 04: base commuter demand for Bucuresti + Ilfov.

Method
  1. Residents: 2021 census totals per UAT (6 sectors + 40 Ilfov towns/communes)
     spread over residential floor area (footprint × floors) of every building
     (Overture footprints from step 02, typed with OSM building/land-use tags).
  2. Destinations: TRIP_SHARE × residents, split between Bucharest and Ilfov by
     DEST_SHARE, spread over job-weighted floor area (offices, retail, industry,
     schools, hospitals…) plus OSM shop/office/amenity points.
  3. Everything is binned into CELL_M grid cells; each cell becomes a demand point.
  4. A doubly-constrained gravity model (exponential distance decay, calibrated
     to TARGET_MEAN_TRIP_KM) links homes to destinations; flows are sampled into
     pops of POP_UNIT people (max MAXPOPSIZE).

Output: work/demand/demand_data.json (+ QA files in work/demand/qa/)
"""
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import config as C
from buhlib import UTM, read_geojsonseq, norm_name, parse_number, write_json

QA = os.path.join(C.DEMAND_DIR, "qa")
os.makedirs(QA, exist_ok=True)
rng = np.random.default_rng(C.SEED)


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ inputs
def load_buildings():
    pkl = os.path.join(C.MAP_DIR, "buildings.pkl")
    osm = read_geojsonseq(os.path.join(C.OSM_DIR, "buildings.geojsonseq"))
    osm = osm[osm.geometry.notna()]
    osm = osm[osm.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    for col in ("building", "building:levels", "height", "shop", "amenity",
                "office", "tourism"):
        if col not in osm.columns:
            osm[col] = None
    osm["o_levels"] = osm["building:levels"].map(parse_number)
    osm["o_height"] = osm["height"].map(parse_number)
    osm = osm[["geometry", "building", "o_levels", "o_height", "shop",
               "amenity", "office", "tourism"]]

    if os.path.exists(pkl):
        df = pd.read_pickle(pkl)
        ov = gpd.GeoDataFrame(df[["geometry", "height"]].copy(),
                              geometry="geometry", crs="EPSG:4326")
        ov = ov[ov.geometry.notna()]
        ov["ov_height"] = pd.to_numeric(ov["height"], errors="coerce")
        log(f"Overture buildings: {len(ov):,}   OSM buildings: {len(osm):,}")
        # attach OSM tags to Overture footprints via representative point
        pts = gpd.GeoDataFrame(geometry=ov.geometry.representative_point(),
                               crs="EPSG:4326")
        j = gpd.sjoin(pts, osm, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        b = ov.join(j.drop(columns=["geometry", "index_right"]))
        log(f"  Overture footprints with OSM tags: {b['building'].notna().mean():.0%}")
    else:
        log("No Overture buildings.pkl (run step 02 first for best results); "
            "using OSM buildings only.")
        b = osm.copy()
        b["ov_height"] = np.nan
    b = b.reset_index(drop=True)
    b = gpd.GeoDataFrame(b, geometry="geometry", crs="EPSG:4326")
    return b


LANDUSE_MAP = {
    "residential": "residential",
    "commercial": "commercial", "retail": "retail",
    "industrial": "industrial", "port": "industrial", "railway": "industrial",
    "education": "education", "school": "education", "university": "education",
    "college": "education", "kindergarten": "education", "hospital": "health",
    "aerodrome": "airport", "military": "military",
    "farmyard": "farm", "farmland": "farm", "allotments": "garden",
    "orchard": "farm", "vineyard": "farm", "greenhouse_horticulture": "farm",
    "cemetery": "cemetery", "religious": "religious", "garages": "garages",
    "construction": "construction", "brownfield": "construction",
    "park": "park", "recreation_ground": "park", "stadium": "sport",
    "mall": "retail",
}


def load_landuse():
    lu = read_geojsonseq(os.path.join(C.OSM_DIR, "landuse.geojsonseq"))
    if lu.empty:
        return lu
    def cat(r):
        for k in ("amenity", "aeroway", "shop", "leisure", "landuse"):
            v = r.get(k)
            if isinstance(v, str) and v in LANDUSE_MAP:
                return LANDUSE_MAP[v]
        if isinstance(r.get("military"), str):
            return "military"
        return None
    lu["lu"] = lu.apply(cat, axis=1)
    lu = lu[lu["lu"].notna() & lu.geom_type.isin(["Polygon", "MultiPolygon"])]
    lu["lu_area"] = lu.to_crs(UTM).area
    return lu[["geometry", "lu", "lu_area"]]


def load_admin(census):
    """Match census UATs to OSM admin polygons. Returns (uat_gdf, county_gdf)."""
    adm = read_geojsonseq(os.path.join(C.OSM_DIR, "admin.geojsonseq"))
    adm = adm[adm.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    adm["key"] = adm["name"].map(norm_name)
    adm["lvl"] = pd.to_numeric(adm.get("admin_level"), errors="coerce")

    counties = {}
    for code, names in (("B", {"bucuresti"}), ("IF", {"ilfov"})):
        m = adm[adm["key"].isin(names) & (adm["lvl"] <= 6)]
        if len(m):
            counties[code] = m.sort_values("lvl").geometry.iloc[0]
        else:
            log(f"WARNING: county polygon for {code} not found in OSM admin data")
    county_gdf = gpd.GeoDataFrame({"county": list(counties)},
                                  geometry=list(counties.values()), crs="EPSG:4326")

    rows = []
    for _, r in census.iterrows():
        key = norm_name(r["uat"])
        cand = adm[(adm["key"] == key) & (adm["lvl"] >= 5)]
        if r["county"] in counties and len(cand):
            cp = counties[r["county"]]
            inside = cand[cand.geometry.representative_point().within(cp.buffer(0.002))]
            cand = inside if len(inside) else cand.iloc[0:0]
        if len(cand):
            g = cand.sort_values("lvl", ascending=False).geometry.iloc[0]
            rows.append({"uat": r["uat"], "county": r["county"], "geometry": g})
        else:
            log(f"WARNING: no OSM boundary for {r['uat']} ({r['county']}); its "
                "population goes to the unmatched part of the county")
    uat_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    log(f"Matched {len(uat_gdf)}/{len(census)} census UATs to OSM boundaries")
    return uat_gdf, county_gdf


# ------------------------------------------------------------------ typing
HOUSE = {"house", "detached", "semidetached_house", "terrace", "bungalow",
         "villa", "farm", "cabin", "static_caravan"}
APART = {"apartments", "dormitory", "residential"}
SKIP = {"garage", "garages", "shed", "roof", "hut", "carport", "greenhouse",
        "barn", "cowshed", "stable", "sty", "service", "transformer_tower",
        "construction", "ruins", "container", "toilets", "parking", "bunker",
        "kiosk_roof", "boathouse", "silo", "storage_tank", "water_tower",
        "tent", "farm_auxiliary", "allotment_house", "collapsed", "no"}
TAG_CLASS = {
    "commercial": "office", "office": "office",
    "retail": "retail", "supermarket": "retail", "kiosk": "retail",
    "industrial": "industrial", "factory": "industrial", "manufacture": "industrial",
    "warehouse": "warehouse", "hangar": "warehouse",
    "school": "education", "university": "education", "college": "education",
    "kindergarten": "education",
    "hospital": "health", "clinic": "health",
    "public": "public", "government": "public", "civic": "public",
    "townhall": "public", "fire_station": "public", "police": "public",
    "train_station": "public", "transportation": "public",
    "hotel": "hotel",
    "church": "other", "chapel": "other", "cathedral": "other",
    "mosque": "other", "monastery": "other", "religious": "other",
    "sports_hall": "other", "sports_centre": "other", "stadium": "other",
}


def classify(btag, lu, area, shop, amenity, office):
    if isinstance(shop, str) and shop == "mall":
        return "mall"
    if isinstance(office, str):
        return "office"
    btag = btag if isinstance(btag, str) else "yes"
    if btag in SKIP:
        return None
    if btag in HOUSE:
        return "house"
    if btag in APART:
        if btag == "residential" and area < 200:
            return "house"
        return "apartments_large" if area > 600 else "apartments"
    if btag in TAG_CLASS:
        return TAG_CLASS[btag]
    # generic building=yes (or unknown): use land use + footprint size
    if area < 30:
        return None
    if lu == "residential":
        if area < 250:
            return "house"
        return "apartments_large" if area > 600 else "apartments"
    if lu in ("commercial",):
        return "mall" if area > 8000 else "office"
    if lu == "retail":
        return "mall" if area > 8000 else "retail"
    if lu == "industrial":
        return "warehouse" if area > 5000 else "industrial"
    if lu == "education":
        return "education"
    if lu == "health":
        return "health"
    if lu in ("airport", "military"):
        return "public"
    if lu in ("farm", "garden", "cemetery", "garages", "park", "construction",
              "religious", "sport"):
        return None if area < 150 else "other"
    if isinstance(amenity, str):
        return "public"
    if isinstance(shop, str):
        return "retail"
    return "house" if area < 250 else "mixed"


def floors(cls, area, levels, oh, ovh):
    if levels == levels and levels > 0:
        f = levels
    elif oh == oh and oh > 0:
        f = oh / 3.0
    elif ovh == ovh and ovh > 0:
        f = ovh / 3.0
    else:
        key = "apartments_large" if cls == "apartments" and area > 600 else cls
        f = C.DEFAULT_LEVELS.get(key, 1)
    return float(np.clip(f, 1, 45))


def zone_factor(x, y, key):
    """Multiplier per location from config.ZONES (circles with a soft edge).
    Full effect inside radius_m, fading linearly to none at radius_m * 1.5.
    Overlapping zones multiply."""
    import pyproj
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    f = np.ones(len(x))
    for z in getattr(C, "ZONES", []):
        mult = z.get(key, 1.0)
        if mult == 1.0:
            continue
        cx, cy = to_utm.transform(*z["center"])
        r = float(z["radius_m"])
        d = np.hypot(x - cx, y - cy)
        w = np.clip((1.5 * r - d) / (0.5 * r), 0, 1)
        f *= 1 + (mult - 1) * w
        log(f"  zone {z['name']}: {key} ×{mult} on {(w > 0).sum():,} items")
    return f


# ------------------------------------------------------------------ main
def main():
    census = pd.read_csv(C.CENSUS_CSV)
    census["target"] = census.apply(
        lambda r: r["population_2021"] * C.GROWTH.get(r["county"], 1.0), axis=1)
    log(f"Census target population: {census['target'].sum():,.0f} "
        f"({census.groupby('county')['target'].sum().round().to_dict()})")

    b = load_buildings()
    lu = load_landuse()
    uats, counties = load_admin(census)

    b_utm = b.to_crs(UTM)
    b["area"] = b_utm.area.values
    cent = b_utm.geometry.representative_point()
    b["x"], b["y"] = cent.x.values, cent.y.values
    pts = gpd.GeoDataFrame(geometry=cent.to_crs("EPSG:4326").values, crs="EPSG:4326")

    # land use at the building (smallest containing polygon wins)
    if len(lu):
        j = gpd.sjoin(pts, lu, how="left", predicate="within")
        j = j.sort_values("lu_area").groupby(level=0).first()
        b["lu"] = j["lu"].reindex(b.index).values
    else:
        b["lu"] = None
    # UAT / county
    if len(uats):
        j = gpd.sjoin(pts, uats, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        b["uat"] = j["uat"].reindex(b.index).values
        b["county"] = j["county"].reindex(b.index).values
    else:
        b["uat"], b["county"] = None, None
    if len(counties):
        j = gpd.sjoin(pts, counties, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        cty = j["county"].reindex(b.index).values
        b["county"] = np.where(pd.isna(b["county"]), cty, b["county"])
    outside = b["county"].isna()
    log(f"Buildings inside Bucharest/Ilfov: {(~outside).sum():,} "
        f"(dropping {outside.sum():,} outside)")
    b = b[~outside].reset_index(drop=True)
    pts = None

    log("Classifying buildings...")
    b["cls"] = [classify(*t) for t in zip(b["building"], b["lu"], b["area"],
                                           b["shop"], b["amenity"], b["office"])]
    b = b[b["cls"].notna()].reset_index(drop=True)
    b["floors"] = [floors(*t) for t in zip(b["cls"], b["area"], b["o_levels"],
                                           b["o_height"], b["ov_height"])]
    b["floor_area"] = b["area"] * b["floors"]
    b["rw"] = b["floor_area"] * b["cls"].map(C.RES_WEIGHT).fillna(0)
    b["jw"] = b["floor_area"] * b["cls"].map(C.JOB_WEIGHT).fillna(0)
    b.groupby("cls")[["floor_area", "rw", "jw"]].sum().round(0).to_csv(
        os.path.join(QA, "building_classes.csv"))
    log(b["cls"].value_counts().to_string())

    # ---- hand-painted zone multipliers (config.ZONES)
    b["rw"] *= zone_factor(b["x"].values, b["y"].values, "res")

    # ---- residents calibrated per UAT
    b["res"] = 0.0
    check = []
    cal = census
    if getattr(C, "RES_CALIBRATION", "uat") == "county":
        # only county totals are fixed: zones can move people between sectors
        cal = census.groupby("county", as_index=False)["target"].sum()
        cal["uat"] = cal["county"]
        b["uat"] = b["county"]
    matched = set(b["uat"].dropna())
    for _, r in cal.iterrows():
        if r["uat"] in matched:
            m = b["uat"] == r["uat"]
            w = b.loc[m, "rw"].sum()
            if w > 0:
                b.loc[m, "res"] = r["target"] * b.loc[m, "rw"] / w
                check.append((r["uat"], r["target"], int(m.sum())))
                continue
            log(f"WARNING: {r['uat']} has no residential buildings")
        # unmatched → spread over buildings of the county without a matched UAT
        m = (b["county"] == r["county"]) & ~b["uat"].isin(matched)
        if b.loc[m, "rw"].sum() == 0:
            m = b["county"] == r["county"]
        w = b.loc[m, "rw"].sum()
        if w > 0:
            b.loc[m, "res"] += r["target"] * b.loc[m, "rw"] / w
        check.append((r["uat"] + " (spread)", r["target"], int(m.sum())))
    pd.DataFrame(check, columns=["uat", "residents", "buildings"]).to_csv(
        os.path.join(QA, "uat_check.csv"), index=False)

    trips_total = b["res"].sum() * C.TRIP_SHARE

    # ---- POIs add job weight at their location
    poi_path = os.path.join(C.OSM_DIR, "pois.geojsonseq")
    poi_rows = []
    if os.path.exists(poi_path):
        poi = read_geojsonseq(poi_path)
        if len(poi):
            w = np.zeros(len(poi))
            for k, v in C.POI_JOBS.items():
                if k in poi.columns:
                    w = np.where(poi[k].notna() & (w == 0), v, w)
            poi["jw"] = w
            poi = poi[poi["jw"] > 0]
            pj = gpd.sjoin(poi[["geometry", "jw"]], counties, how="inner",
                           predicate="within")
            pu = pj.to_crs(UTM)
            poi_rows = pd.DataFrame({"x": pu.geometry.x, "y": pu.geometry.y,
                                     "jw": pj["jw"].values,
                                     "county": pj["county"].values})
            log(f"POIs adding job weight: {len(poi_rows):,}")

    jobs_src = b[["x", "y", "jw", "county"]]
    if len(poi_rows):
        jobs_src = pd.concat([jobs_src, poi_rows], ignore_index=True)
    jobs_src = jobs_src.copy()
    jobs_src["jw"] *= zone_factor(jobs_src["x"].values, jobs_src["y"].values, "jobs")
    jobs_src["jobs"] = 0.0
    for cty, share in C.DEST_SHARE.items():
        m = jobs_src["county"] == cty
        w = jobs_src.loc[m, "jw"].sum()
        if w > 0:
            jobs_src.loc[m, "jobs"] = trips_total * share * jobs_src.loc[m, "jw"] / w

    # ---- grid cells
    def cell_of(df):
        return (np.floor(df["x"] / C.CELL_M).astype(np.int64) * 1_000_000 +
                np.floor(df["y"] / C.CELL_M).astype(np.int64))
    res_df = b[["x", "y", "res", "county"]].copy()
    res_df["cell"] = cell_of(res_df)
    jobs_src["cell"] = cell_of(jobs_src)
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0, defaultdict(float)])
    for df, col in ((res_df, "res"), (jobs_src, "jobs")):
        g = df.assign(wx=df["x"] * df[col], wy=df["y"] * df[col]).groupby("cell")
        s = g[[col, "wx", "wy"]].sum()
        cty = df.groupby(["cell", "county"])[col].sum()
        for cell, row in s.iterrows():
            a = agg[cell]
            a[0 if col == "res" else 1] += row[col]
            a[2] += row["wx"]; a[3] += row["wy"]; a[4] += row[col]
        for (cell, c), v in cty.items():
            agg[cell][5][c] += v
    cells = []
    for cell, (r, jb, wx, wy, wt, cty) in agg.items():
        if r + jb < C.MIN_POINT_SIZE or wt <= 0:
            continue
        cells.append((cell, r, jb, wx / wt, wy / wt, max(cty, key=cty.get)))
    cells = pd.DataFrame(cells, columns=["cell", "res", "jobs", "x", "y", "county"])
    # restore totals lost to dropped tiny cells
    for col, tot in (("res", b["res"].sum()), ("jobs", jobs_src["jobs"].sum())):
        cells[col] *= tot / cells[col].sum()
    log(f"Grid cells (demand points): {len(cells):,}  "
        f"residents {cells['res'].sum():,.0f}  destinations {cells['jobs'].sum():,.0f}")

    # ---- gravity model
    O = (cells["res"].values * C.TRIP_SHARE).astype(np.float64)
    D = cells["jobs"].values.astype(np.float64)
    oi = np.where(O > 0)[0]; di = np.where(D > 0)[0]
    O_, D_ = O[oi], D[di]
    log(f"Gravity matrix: {len(oi):,} origins × {len(di):,} destinations")
    if len(oi) * len(di) > 150e6:
        log("WARNING: very large matrix; raise CELL_M in config.py if you run out of memory")
    X, Y = cells["x"].values, cells["y"].values
    dist = np.empty((len(oi), len(di)), dtype=np.float32)
    for s in range(0, len(oi), 2000):
        e = min(s + 2000, len(oi))
        dist[s:e] = (np.hypot(X[oi[s:e], None] - X[None, di],
                              Y[oi[s:e], None] - Y[None, di]) * C.DETOUR)
    short = dist < C.MIN_TRIP_M

    f32 = np.float32
    O32, D32 = O_.astype(f32), D_.astype(f32)

    def solve(beta):
        F = np.exp(dist * f32(-beta / 1000.0))
        F[short] *= f32(0.15)
        A = np.ones(len(oi), f32); B = np.ones(len(di), f32)
        for _ in range(C.FURNESS_ITERS):
            A = (1.0 / np.maximum(F @ (B * D32), 1e-30)).astype(f32)
            B = (1.0 / np.maximum(F.T @ (A * O32), 1e-30)).astype(f32)
        Fd = F * dist
        flow_d = float((A * O32).astype(np.float64) @ (Fd @ (B * D32)).astype(np.float64))
        del Fd
        mean_km = flow_d / O_.sum() / 1000.0
        return F, A, B, mean_km

    lo, hi = 0.0005, 2.0
    for _ in range(26):
        mid = (lo * hi) ** 0.5
        _, _, _, m = solve(mid)
        if m > C.TARGET_MEAN_TRIP_KM:
            lo = mid
        else:
            hi = mid
    beta = (lo * hi) ** 0.5
    F, A, B, mean_km = solve(beta)
    log(f"Calibrated beta = {beta:.4f}/km → mean trip {mean_km:.2f} km "
        f"(target {C.TARGET_MEAN_TRIP_KM})")
    if abs(mean_km - C.TARGET_MEAN_TRIP_KM) > 0.5:
        log("WARNING: target mean trip length not reachable with this geography; "
            "check TARGET_MEAN_TRIP_KM / DETOUR")

    # ---- sample pops
    cell_ids = [f"p{i}" for i in range(len(cells))]
    pops = []
    BD = B.astype(np.float64) * D_
    for r in range(len(oi)):
        k_float = O_[r] / C.POP_UNIT
        k = int(np.floor(k_float) + (rng.random() < (k_float % 1)))
        if k == 0:
            continue
        p = F[r].astype(np.float64) * BD
        p = p / p.sum()
        counts = rng.multinomial(k, p)
        for c in np.nonzero(counts)[0]:
            size = int(counts[c] * C.POP_UNIT)
            dm = float(dist[r, c])
            while size > 0:
                s = min(size, C.MAXPOPSIZE)
                size -= s
                pops.append({"id": f"q{len(pops)}",
                             "residenceId": cell_ids[oi[r]],
                             "jobId": cell_ids[di[c]],
                             "size": s, "drivingSeconds": 0, "drivingDistance": 0,
                             "_d": dm})
    log(f"Pops: {len(pops):,}  total size {sum(p['size'] for p in pops):,}")

    # ---- points (only those used by a pop)
    used = defaultdict(lambda: {"popIds": [], "jobs": 0, "residents": 0})
    for p in pops:
        used[p["residenceId"]]["popIds"].append(p["id"])
        used[p["residenceId"]]["residents"] += p["size"]
        used[p["jobId"]]["popIds"].append(p["id"])
        used[p["jobId"]]["jobs"] += p["size"]
    import pyproj
    to_ll = pyproj.Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform(cells["x"].values, cells["y"].values)
    points = []
    for i, pid in enumerate(cell_ids):
        if pid in used:
            u = used[pid]
            points.append({"id": pid, "location": [round(lon[i], 6), round(lat[i], 6)],
                           "jobs": u["jobs"], "residents": u["residents"],
                           "popIds": u["popIds"]})

    # ---- QA
    county_of = dict(zip(cell_ids, cells["county"]))
    flows = defaultdict(int)
    for p in pops:
        flows[(county_of[p["residenceId"]], county_of[p["jobId"]])] += p["size"]
    tot = sum(flows.values())
    log("Flows (home county → destination county):")
    for (a, c), v in sorted(flows.items()):
        log(f"  {a:>2} → {c:<2} {v:>10,}  {v / tot:6.1%}")
    d = np.array([p.pop("_d") for p in pops]); w = np.array([p["size"] for p in pops])
    log(f"Mean pop trip {np.average(d, weights=w) / 1000:.2f} km, "
        f"median {np.median(np.repeat(d, (w // C.POP_UNIT).clip(1))) / 1000:.2f} km")
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": p["location"]},
              "properties": {"id": p["id"], "residents": p["residents"], "jobs": p["jobs"]}}
             for p in points]
    write_json(os.path.join(QA, "points.geojson"),
               {"type": "FeatureCollection", "features": feats})
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(16, 8))
        for a, key, title in ((ax[0], "residents", "Residents"), (ax[1], "jobs", "Destinations")):
            v = np.array([p[key] for p in points], float)
            xy = np.array([p["location"] for p in points])
            sc = a.scatter(xy[:, 0], xy[:, 1], s=4, c=np.log10(v + 1), cmap="magma")
            a.set_title(title); a.set_aspect(1 / np.cos(np.radians(44.45)))
            fig.colorbar(sc, ax=a, label="log10(people)")
        fig.tight_layout(); fig.savefig(os.path.join(QA, "demand_map.png"), dpi=120)
    except Exception as e:  # QA only
        log("(skipped QA plot:", e, ")")

    out = os.path.join(C.DEMAND_DIR, "demand_data.json")
    write_json(out, {"points": points, "pops": pops})
    # step 05 always starts from this copy, so it must be refreshed here
    write_json(os.path.join(C.DEMAND_DIR, "demand_data_base.json"),
               {"points": points, "pops": pops})
    log(f"Wrote {out}: {len(points):,} points, {len(pops):,} pops")


if __name__ == "__main__":
    main()
