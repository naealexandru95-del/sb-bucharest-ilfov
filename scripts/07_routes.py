"""
Step 07: driving time/distance (+ optional path) for every pop via the local
OSRM server from step 06. Only pops with drivingSeconds == 0 are routed unless
--all is passed. Falls back to straight-line ×1.3 at 30 km/h if OSRM has no route.
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from shapely.geometry import LineString

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import config as C
from buhlib import haversine_m, read_json, write_json

BASE = f"http://localhost:{C.OSRM_PORT}"
_local = threading.local()


def session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s


def nearest(loc):
    try:
        r = session().get(f"{BASE}/nearest/v1/driving/{loc[0]},{loc[1]}", timeout=30)
        if r.ok and r.json().get("code") == "Ok":
            return r.json()["waypoints"][0]["location"]
    except requests.RequestException:
        pass
    return loc


def route(a, b):
    ov = "full&geometries=geojson" if C.INCLUDE_DRIVING_PATHS else "false"
    try:
        r = session().get(f"{BASE}/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}"
                          f"?overview={ov}", timeout=60)
        j = r.json()
        if r.ok and j.get("code") == "Ok":
            rt = j["routes"][0]
            path = None
            if C.INCLUDE_DRIVING_PATHS:
                line = LineString(rt["geometry"]["coordinates"])
                if line.length > 0:
                    line = line.simplify(C.PATH_SIMPLIFY_TOL, preserve_topology=True)
                path = [[round(x, 5), round(y, 5)] for x, y in line.coords]
            return int(round(rt["duration"])), int(round(rt["distance"])), path, True
    except (requests.RequestException, ValueError):
        pass
    d = float(haversine_m(a[0], a[1], b[0], b[1])) * 1.3
    return int(d / (30 / 3.6)), int(d), None, False


def main():
    try:
        requests.get(f"{BASE}/nearest/v1/driving/26.1,44.43", timeout=5)
    except requests.RequestException:
        sys.exit(f"OSRM is not reachable on {BASE}. Run scripts/06_osrm.sh first.")
    fdemand = os.path.join(C.DEMAND_DIR, "demand_data.json")
    dd = read_json(fdemand)
    redo = "--all" in sys.argv
    pts = {p["id"]: p for p in dd["points"]}
    todo = [p for p in dd["pops"] if redo or not p.get("drivingSeconds")]
    print(f"Routing {len(todo):,} of {len(dd['pops']):,} pops", flush=True)

    need = sorted({p["residenceId"] for p in todo} | {p["jobId"] for p in todo})
    snapped = {}
    with ThreadPoolExecutor(C.ROUTE_THREADS) as ex:
        futs = {ex.submit(nearest, pts[i]["location"]): i for i in need}
        for f in as_completed(futs):
            snapped[futs[f]] = f.result()

    pairs = sorted({(p["residenceId"], p["jobId"]) for p in todo})
    results, fails = {}, 0
    with ThreadPoolExecutor(C.ROUTE_THREADS) as ex:
        futs = {ex.submit(route, snapped[a], snapped[b]): (a, b) for a, b in pairs}
        for n, f in enumerate(as_completed(futs), 1):
            results[futs[f]] = f.result()
            fails += not results[futs[f]][3]
            if n % 2000 == 0:
                print(f"  {n:,}/{len(pairs):,} routes", end="\r", flush=True)
    print(f"\n{len(pairs):,} unique routes, {fails:,} fell back to straight line")

    for p in todo:
        sec, dist, path, _ = results[(p["residenceId"], p["jobId"])]
        p["drivingSeconds"] = max(sec, 1)
        p["drivingDistance"] = max(dist, 1)
        if path:
            p["drivingPath"] = path
        else:
            p.pop("drivingPath", None)
    write_json(fdemand, dd)
    secs = [p["drivingSeconds"] for p in dd["pops"]]
    print(f"Saved {fdemand}. Mean drive {sum(secs) / len(secs) / 60:.1f} min")


if __name__ == "__main__":
    main()
