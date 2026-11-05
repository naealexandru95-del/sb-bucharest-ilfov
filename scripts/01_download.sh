#!/usr/bin/env bash
# Downloads the Romania OSM extract from Geofabrik (~350 MB). Re-run to refresh.
set -euo pipefail
cd "$(dirname "$0")/.."
WORK=$(python -c 'import config; print(config.WORK)')
URL=$(python -c 'import config; print(config.GEOFABRIK_URL)')
PBF=$(python -c 'import config; print(config.OSM_PBF)')
mkdir -p "$WORK"
if [ -f "$PBF" ] && [ "${1:-}" != "--force" ]; then
  echo "Already have $PBF (pass --force to re-download)"
else
  curl -L --fail -o "$PBF.part" "$URL"
  mv "$PBF.part" "$PBF"
fi
osmium fileinfo "$PBF" | head -20
