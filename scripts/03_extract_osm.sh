#!/usr/bin/env bash
# Step 03: OSM layers for the demand model (building types/levels, land use,
# POIs, administrative boundaries). Output: work/osm/*.geojsonseq
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(python - <<'EOF'
import config as C
print(f'PBF="{C.OSM_PBF}"; OUT="{C.OSM_DIR}"; BBOX="{",".join(map(str, C.BBOX))}"')
EOF
)"
mkdir -p "$OUT"
AREA="$OUT/area.osm.pbf"

echo "==> clip Romania to $BBOX"
osmium extract --strategy smart -b "$BBOX" "$PBF" -o "$AREA" --overwrite

export_layer () {  # name, geometry types, filters...
  local name=$1 geom=$2; shift 2
  osmium tags-filter "$AREA" "$@" -o "$OUT/$name.osm.pbf" --overwrite
  osmium export "$OUT/$name.osm.pbf" -f geojsonseq --geometry-types="$geom" \
    -a type,id -o "$OUT/$name.geojsonseq" --overwrite
  echo "   $name: $(wc -l < "$OUT/$name.geojsonseq") features"
}

echo "==> buildings (types + levels)"
export_layer buildings polygon wr/building
echo "==> land use"
export_layer landuse polygon wr/landuse wr/amenity=university,college,school,hospital,kindergarten \
  wr/aeroway=aerodrome wr/leisure=park,stadium wr/shop=mall wr/military
echo "==> POIs"
export_layer pois point n/shop n/office n/amenity n/craft n/tourism n/healthcare

echo "==> administrative boundaries (from the full Romania file so relations are complete)"
osmium tags-filter "$PBF" r/boundary=administrative -o "$OUT/admin.osm.pbf" --overwrite
osmium export "$OUT/admin.osm.pbf" -f geojsonseq --geometry-types=polygon -a type,id \
  -o "$OUT/admin_all.geojsonseq" --overwrite
python - "$OUT/admin_all.geojsonseq" "$OUT/admin.geojsonseq" <<'EOF'
import json, sys
sys.path.insert(0, ".")
import config as C
from shapely.geometry import shape, box
area = box(*C.BBOX)
n = 0
with open(sys.argv[1]) as fi, open(sys.argv[2], "w") as fo:
    for line in fi:
        line = line.strip().lstrip("\x1e")
        if not line:
            continue
        f = json.loads(line)
        lvl = f["properties"].get("admin_level")
        if lvl not in ("4", "5", "6", "7", "8", "9", "10"):
            continue
        if shape(f["geometry"]).intersects(area):
            fo.write(json.dumps(f, ensure_ascii=False) + "\n"); n += 1
print(f"   admin: {n} boundaries in the map area")
EOF
rm -f "$OUT/admin_all.geojsonseq"
