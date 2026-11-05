#!/usr/bin/env bash
# Step 06: local OSRM car-routing server (Docker) for Bucharest + Ilfov.
# Needs Docker Desktop with WSL integration enabled. Stop later with: docker stop buh-osrm
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(python - <<'EOF'
import config as C
b = C.BBOX; p = 0.1
print(f'PBF="{C.OSM_PBF}"; OUT="{C.WORK}/osrm"; PORT={C.OSRM_PORT}; '
      f'BBOX="{b[0]-p},{b[1]-p},{b[2]+p},{b[3]+p}"')
EOF
)"
IMG=ghcr.io/project-osrm/osrm-backend
mkdir -p "$OUT"
if [ ! -f "$OUT/buh.osrm.mldgr" ]; then
  osmium extract --strategy complete_ways -b "$BBOX" "$PBF" -o "$OUT/buh.osm.pbf" --overwrite
  docker run --rm -t -v "$OUT:/data" $IMG osrm-extract -p /opt/car.lua /data/buh.osm.pbf
  docker run --rm -t -v "$OUT:/data" $IMG osrm-partition /data/buh.osrm
  docker run --rm -t -v "$OUT:/data" $IMG osrm-customize /data/buh.osrm
fi
docker rm -f buh-osrm >/dev/null 2>&1 || true
docker run -d --name buh-osrm -p "$PORT:5000" -v "$OUT:/data" $IMG \
  osrm-routed --algorithm mld --max-table-size 10000 /data/buh.osrm
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/route/v1/driving/26.1025,44.4355;26.085,44.5711" >/dev/null; then
    echo "OSRM is up on port $PORT"; exit 0
  fi
  sleep 2
done
echo "OSRM did not answer; check: docker logs buh-osrm"; exit 1
