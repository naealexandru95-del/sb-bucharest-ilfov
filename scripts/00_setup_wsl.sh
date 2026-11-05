#!/usr/bin/env bash
# One-time toolchain setup inside WSL (Ubuntu 24.04).
# Installs: osmium, gdal (ogr2ogr), sqlite3, jq, Java 21, node + mapshaper,
# tippecanoe/tile-join, pmtiles, planetiler.jar, Miniforge + the "depot" env.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN" "$HOME/src"

echo "==> apt packages"
sudo apt-get update
sudo apt-get install -y build-essential git curl wget unzip ca-certificates \
  osmium-tool gdal-bin sqlite3 libsqlite3-dev zlib1g-dev jq \
  openjdk-21-jre-headless nodejs npm

echo "==> mapshaper"
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"
npm install -g mapshaper
ln -sf "$HOME/.npm-global/bin/mapshaper" "$BIN/mapshaper"

echo "==> tippecanoe + tile-join (build from source)"
if ! command -v tippecanoe >/dev/null; then
  rm -rf "$HOME/src/tippecanoe"
  git clone --depth 1 https://github.com/felt/tippecanoe.git "$HOME/src/tippecanoe"
  make -C "$HOME/src/tippecanoe" -j"$(nproc)"
  cp "$HOME/src/tippecanoe/tippecanoe" "$HOME/src/tippecanoe/tile-join" "$BIN/"
fi

echo "==> pmtiles CLI"
if ! command -v pmtiles >/dev/null; then
  URL=$(curl -s https://api.github.com/repos/protomaps/go-pmtiles/releases/latest \
        | jq -r '.assets[].browser_download_url' | grep -i 'linux_x86_64.tar.gz' | head -1)
  curl -L "$URL" | tar -xz -C "$BIN" pmtiles
  chmod +x "$BIN/pmtiles"
fi

echo "==> planetiler.jar"
if [ ! -f "$BIN/planetiler.jar" ]; then
  curl -L -o "$BIN/planetiler.jar" \
    https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar
fi

echo "==> Miniforge"
if [ ! -d "$HOME/miniforge3" ]; then
  curl -L -o /tmp/miniforge.sh \
    https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
  bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
fi
# shellcheck disable=SC1091
source "$HOME/miniforge3/etc/profile.d/conda.sh"

echo "==> depot conda env"
if [ ! -d "$HOME/src/depot" ]; then
  git clone --depth 1 https://github.com/Subway-Builder-Modded/depot.git "$HOME/src/depot"
fi
if ! conda env list | grep -q '^depot '; then
  conda env create -f "$HOME/src/depot/environment.yml"
fi
conda activate depot
# depot's demand module also needs these (not in its environment.yml)
conda install -y -c conda-forge scikit-learn requests h2 pyogrio networkx
pip install "$HOME/src/depot"

grep -q 'BUH toolchain' "$HOME/.bashrc" || cat >> "$HOME/.bashrc" <<EOF

# BUH toolchain
export PATH="$BIN:\$HOME/.npm-global/bin:\$PATH"
source "\$HOME/miniforge3/etc/profile.d/conda.sh"
EOF

echo
echo "Done. Open a new WSL terminal (or 'source ~/.bashrc'), then:"
echo "  conda activate depot && cd \"$HERE\" && ./run_all.sh"
