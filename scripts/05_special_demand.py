"""
Step 05: add airport, university, mall, stadium, park and hospital demand
(data/special_demand.json) with depot's add_points.
Input/output: work/demand/demand_data.json (the base file is kept as demand_data_base.json)
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import config as C
from depot.demand import DemandData

fdemand = os.path.join(C.DEMAND_DIR, "demand_data.json")
fbase = os.path.join(C.DEMAND_DIR, "demand_data_base.json")
if not os.path.exists(fbase):         # step 04 writes it; this is a fallback
    shutil.copy(fdemand, fbase)
shutil.copy(fbase, fdemand)            # re-runs of step 05 start from the base

spec = json.load(open(C.SPECIAL_DEMAND_JSON, encoding="utf-8"))
dd = DemandData(fdemand, C.CODE, bbox=C.BBOX, outputdir=C.DEMAND_DIR)

items = []
for a in spec.get("airports", []):
    items.append({k: v for k, v in a.items()})
for u in spec.get("universities", []):
    on = u["students"] * u["perc_oncampus"] * 0.3
    off = u["students"] * (1 - u["perc_oncampus"]) * 0.9
    it = {k: v for k, v in u.items() if k not in ("students", "perc_oncampus")}
    it["total_capacity"] = on + off
    it["residential_split"] = on / (on + off)
    items.append(it)
items += spec.get("other", [])

known = set(dd.special_demand_codes) if hasattr(dd, "special_demand_codes") else set()
for it in items:
    if known and it["type"] not in known:
        sys.exit(f"Unknown special demand type {it['type']!r} for {it['name']}. "
                 f"Valid: {sorted(known)}")
    dd.add_points(it)

dd.enforce_max_pop_size(C.MAXPOPSIZE)
dd.print_stats()
dd.save(fdemand)
print("Saved", fdemand)
