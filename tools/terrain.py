"""Build the map's relief and waters from real elevation data.

    python tools/terrain.py

1. Downloads the elevation tiles that cover the map (Mapzen Terrain Tiles, "terrarium" encoding, open data
   on AWS: https://registry.opendata.aws/terrain-tiles/) into build/cache/terrarium.
2. Resamples them into the map's projection (crowns/geo.py) and writes
   crowns/data/map/height.png: 16-bit greyscale, metres + 12000 (so the sea floor stays positive).
3. Downloads Natural Earth's coastlines, rivers and lakes (public domain) and writes
   crowns/data/map/rivers.json and lakes.json in map pixels.
"""

import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crowns import geo  # noqa: E402

ZOOM = 7
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{name}.geojson"
CACHE = ROOT / "build" / "cache"
OUT = ROOT / "crowns" / "data" / "map"
HEIGHT_OFFSET = 12000  # stored value = metres + offset


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _get(url, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
    return path.read_bytes()


def mosaic():
    """The tiles around the map stitched together: (metres array, tile x0, tile y0)."""
    x0, y1 = _tile_xy(geo.LON0, geo.LAT0, ZOOM)
    x1, y0 = _tile_xy(geo.LON1, geo.LAT1, ZOOM)
    tx = range(int(x0), int(x1) + 1)
    ty = range(int(y0), int(y1) + 1)
    out = np.zeros((len(ty) * 256, len(tx) * 256), dtype=np.float32)
    for j, y in enumerate(ty):
        for i, x in enumerate(tx):
            raw = _get(TILE_URL.format(z=ZOOM, x=x, y=y), CACHE / "terrarium" / f"{ZOOM}_{x}_{y}.png")
            rgb = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.float32)
            out[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
        print(f"  row {j + 1}/{len(ty)}")
    return out, tx.start, ty.start


def resample(mos, tx0, ty0):
    """The mosaic in the map's projection (bilinear)."""
    xs = np.arange(geo.WIDTH) + 0.5
    ys = np.arange(geo.HEIGHT) + 0.5
    lon = geo.LON0 + xs * geo.KM_PER_PX / geo.KM_PER_DEG_LON
    lat = geo.LAT1 - ys * geo.KM_PER_PX / geo.KM_PER_DEG_LAT
    n = 2 ** ZOOM
    px = ((lon + 180) / 360 * n - tx0) * 256 - 0.5
    lat_r = np.radians(lat)
    py = ((1 - np.log(np.tan(lat_r) + 1 / np.cos(lat_r)) / np.pi) / 2 * n - ty0) * 256 - 0.5
    PX, PY = np.meshgrid(px, py)
    x0 = np.clip(np.floor(PX).astype(int), 0, mos.shape[1] - 2)
    y0 = np.clip(np.floor(PY).astype(int), 0, mos.shape[0] - 2)
    fx, fy = PX - x0, PY - y0
    top = mos[y0, x0] * (1 - fx) + mos[y0, x0 + 1] * fx
    bottom = mos[y0 + 1, x0] * (1 - fx) + mos[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bottom * fy


def natural_earth(name):
    raw = _get(NE_URL.format(name=name), CACHE / "naturalearth" / f"{name}.geojson")
    return json.loads(raw)


def _lines(geometry):
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "LineString":
        return [coords]
    if kind == "MultiLineString":
        return coords
    if kind == "Polygon":
        return coords
    if kind == "MultiPolygon":
        return [ring for poly in coords for ring in poly]
    return []


def _inside(line):
    return any(geo.LON0 - 1 <= lon <= geo.LON1 + 1 and geo.LAT0 - 1 <= lat <= geo.LAT1 + 1 for lon, lat in line)


def _project(line):
    return [[round(v, 1) for v in geo.to_map(lon, lat)] for lon, lat in line]


def waters():
    rivers = []
    for f in natural_earth("ne_10m_rivers_lake_centerlines")["features"]:
        props = f["properties"]
        for line in _lines(f["geometry"]):
            if _inside(line):
                rivers.append({"name": props.get("name") or "", "rank": props.get("scalerank", 9),
                               "points": _project(line)})
    lakes = []
    for f in natural_earth("ne_10m_lakes")["features"]:
        for ring in _lines(f["geometry"]):
            if _inside(ring):
                lakes.append({"name": f["properties"].get("name") or "", "points": _project(ring)})
    return rivers, lakes


def main():
    print("Elevation tiles ...")
    mos, tx0, ty0 = mosaic()
    height = resample(mos, tx0, ty0)
    OUT.mkdir(parents=True, exist_ok=True)
    stored = np.clip(np.round(height + HEIGHT_OFFSET), 0, 65535).astype(np.uint16)
    Image.fromarray(stored).save(OUT / "height.png")
    print(f"height.png {geo.WIDTH}x{geo.HEIGHT}, {height.min():.0f} .. {height.max():.0f} m")
    print("Natural Earth ...")
    rivers, lakes = waters()
    (OUT / "rivers.json").write_text(json.dumps(rivers, separators=(",", ":")), encoding="utf-8")
    (OUT / "lakes.json").write_text(json.dumps(lakes, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rivers)} river lines, {len(lakes)} lakes")


if __name__ == "__main__":
    main()
