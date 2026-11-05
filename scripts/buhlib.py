"""Shared helpers for the BUH pipeline."""
import gzip
import json
import math
import re
import unicodedata

import numpy as np

UTM = "EPSG:32635"  # UTM zone 35N, metres, covers Bucharest


def read_geojsonseq(path):
    """Read a GeoJSONSeq file (osmium export) into a GeoDataFrame (EPSG:4326)."""
    import geopandas as gpd
    feats = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if line:
                feats.append(json.loads(line))
    if not feats:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")


_PREFIXES = ("municipiul ", "judetul ", "comuna ", "orasul ", "oras ",
             "sectorul ", "sector ")


def norm_name(s):
    """'Sectorul 3' -> '3', 'Comuna Ștefăneștii de Jos' -> 'stefanestii de jos'."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().strip()
    for p in _PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
    s = re.sub(r"[-_]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_number(v):
    """'4', '4;5', '12.5 m', '3-4' -> first number as float, else nan."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return float("nan")
    m = re.search(r"\d+(?:[.,]\d+)?", str(v))
    return float(m.group(0).replace(",", ".")) if m else float("nan")


def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = (np.sin((lat2 - lat1) / 2) ** 2 +
         np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


def write_json(path, obj, gz=False):
    opener = gzip.open if gz else open
    with opener(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)


def read_json(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)
