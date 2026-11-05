#!/usr/bin/env bash
# Full build. Each step can also be run on its own (see README.md).
# Usage: ./run_all.sh            all steps
#        ./run_all.sh 4 5 8      only some steps
set -euo pipefail
cd "$(dirname "$0")"
STEPS=("$@"); [ ${#STEPS[@]} -eq 0 ] && STEPS=(1 2 3 4 5 6 7 8)
for s in "${STEPS[@]}"; do
  echo; echo "================ step $s ================"
  case $s in
    1) bash scripts/01_download.sh ;;
    2) python scripts/02_build_map.py ;;
    3) bash scripts/03_extract_osm.sh ;;
    4) python scripts/04_build_demand.py ;;
    5) python scripts/05_special_demand.py ;;
    6) bash scripts/06_osrm.sh ;;
    7) python scripts/07_routes.py ;;
    8) python scripts/08_package.py ;;
    *) echo "unknown step $s"; exit 1 ;;
  esac
done
