"""Draw the provinces on the real relief and describe them.

    python tools/provinces.py

Every province grows out of its main town (tools/history_1402.py) across the land, and the land
resists: mountains and big rivers are expensive to cross and the sea more so, so the borders settle
on ridges and rivers, the way real borders do. Writes:

  crowns/data/map/provinces.png   province of every map pixel: id = R + 256 G (0 = water)
  crowns/data/map/provinces.json  name, owner, culture, religion, town, label point, area, terrain,
                                  coast, neighbours
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from crowns import geo  # noqa: E402
from crowns.mapdata import Ground, blur, smoothstep  # noqa: E402
from history_1402 import CITIES, FORTS, GOODS, MARSHES, PROVINCES  # noqa: E402

# people per km² in 1400 by terrain, and the share of that a region had (densities from the
# estimates for late medieval Europe: Italy and Bohemia crowded, the steppe nearly empty)
DENSITY = {"plains": 9, "hills": 8, "forest": 6, "mountains": 4, "steppe": 2, "desert": 1.2, "marsh": 3}
REGION = {
    "venice": 2.2, "papal": 2.2, "naples": 2.0, "sicily": 2.0, "bohemia": 1.6, "moravia": 1.6, "austria": 1.5,
    "bavaria": 1.6, "salzburg": 1.2, "aquileia": 1.8, "celje": 1.2, "hungary": 1.1, "frankopan": 0.9,
    "poland": 1.0, "lithuania": 0.45, "horde": 0.15, "circassia": 0.4, "wallachia": 0.7, "moldavia": 0.45,
    "georgia": 0.7, "trebizond": 1.0, "mamluks": 0.8, "timurids": 0.5, "akkoyunlu": 0.6, "cyprus": 1.2,
    "genoa": 1.5, "knights": 1.2, "lesbos": 1.2, "naxos": 0.9, "ragusa": 1.5,
}
GOOD_OF_TERRAIN = {"plains": "grain", "hills": "wine", "forest": "timber", "mountains": "livestock",
                   "steppe": "livestock", "desert": "livestock", "marsh": "fish"}

OUT = ROOT / "crowns" / "data" / "map"
CELL = 2           # map pixels per grid cell while the provinces grow
SEA_COST = 14.0    # crossing the sea (so islands find their province, but coasts rarely jump straits)
RIVER_COST = 18.0  # crossing a big river
BIG_RIVERS = 5     # Natural Earth scale ranks counted as big rivers
STRAIT_COST = 400.0
# Straits narrower than the grid: lines no province may cross (lon, lat)
STRAITS = [
    [(29.13, 41.25), (29.05, 41.10), (29.00, 41.03), (28.99, 40.97)],   # Bosporus
    [(26.65, 40.45), (26.40, 40.25), (26.20, 40.05)],                    # Dardanelles
    [(36.45, 45.45), (36.55, 45.30), (36.62, 45.10)],                    # Kerch
    [(15.62, 38.30), (15.65, 38.20), (15.58, 38.05)],                    # Messina
]


def cost_grid(ground):
    h = ground.height[::CELL, ::CELL]
    land = ground.land[::CELL, ::CELL]
    gy, gx = np.gradient(h)
    slope = np.hypot(gx, gy) / (CELL * geo.KM_PER_PX * 1000)
    cost = 1 + 25 * np.clip(slope, 0, 0.2) + 3 * smoothstep(700, 2200, h)
    rivers = Image.new("L", (land.shape[1], land.shape[0]), 0)
    draw = ImageDraw.Draw(rivers)
    for r in ground.rivers:
        if r["rank"] <= BIG_RIVERS:
            draw.line([(x / CELL, y / CELL) for x, y in r["points"]], fill=255, width=1)
    cost = np.where(np.asarray(rivers) > 0, cost + RIVER_COST, cost)
    cost = np.where(land, cost, SEA_COST)
    walls = Image.new("L", (land.shape[1], land.shape[0]), 0)
    draw = ImageDraw.Draw(walls)
    for line in STRAITS:
        draw.line([tuple(v / CELL for v in geo.to_map(lon, lat)) for lon, lat in line], fill=255, width=2)
    cost = np.where(np.asarray(walls) > 0, STRAIT_COST, cost)
    return cost.astype(np.float32), land


def grow(cost, land, seeds):
    """Shortest-path regions on the grid (Bellman-Ford sweeps with numpy): label of every cell."""
    h, w = cost.shape
    dist = np.full((h, w), np.inf, np.float32)
    label = np.zeros((h, w), np.int32)
    for i, (r, c) in enumerate(seeds, start=1):
        dist[r, c] = 0
        label[r, c] = i
    steps = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
             (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    for sweep in range(5000):
        changed = 0
        for dr, dc, length in steps:
            src = (slice(max(0, -dr), h - max(0, dr)), slice(max(0, -dc), w - max(0, dc)))
            dst = (slice(max(0, dr), h - max(0, -dr)), slice(max(0, dc), w - max(0, -dc)))
            cand = dist[src] + (cost[src] + cost[dst]) * 0.5 * length
            better = cand < dist[dst]
            n = int(better.sum())
            if n:
                changed += n
                dist[dst] = np.where(better, cand, dist[dst])
                label[dst] = np.where(better, label[src], label[dst])
        if not changed:
            break
    print(f"  grown in {sweep} sweeps")
    return label


def snap(land, r, c):
    """The nearest land cell to (r, c)."""
    if land[r, c]:
        return r, c
    rows, cols = np.nonzero(land)
    k = np.argmin((rows - r) ** 2 + (cols - c) ** 2)
    return int(rows[k]), int(cols[k])


def majority(labels, land, passes=2):
    """Smooth the stair-stepped borders: each pixel takes the most common label around it."""
    for _ in range(passes):
        padded = np.pad(labels, 1, mode="edge")
        stack = np.stack([padded[1 + dr:labels.shape[0] + 1 + dr, 1 + dc:labels.shape[1] + 1 + dc]
                          for dr in (-1, 0, 1) for dc in (-1, 0, 1)])
        best = labels.copy()
        best_count = np.zeros(labels.shape, np.int32)
        for k in range(9):
            count = (stack == stack[k]).sum(axis=0)
            better = count > best_count
            best = np.where(better, stack[k], best)
            best_count = np.where(better, count, best_count)
        labels = np.where(land, best, 0)
    return labels


def default_good(terrain, lat):
    """What a province without a famous product lives on: vineyards only where the grape ripens."""
    if terrain == "hills" and lat > 47.3:
        return "livestock"
    return GOOD_OF_TERRAIN[terrain]


def terrain_of(stats):
    """The province's ground, from its relief and climate (see the thresholds' reasons in the README)."""
    high, slope, woods, arid = stats["high"], stats["slope"], stats["woods"], stats["arid"]
    if slope > 0.07 and (high > 0.35 or slope > 0.09):
        return "mountains"
    if arid > 0.7 and slope < 0.04:
        return "desert"
    if arid > 0.25 and slope < 0.04:
        return "steppe"
    if woods > 0.55:
        return "forest"
    if slope > 0.04:
        return "hills"
    return "plains"


def main():
    ground = Ground(scale=1)
    print("Cost of the land ...")
    cost, land = cost_grid(ground)
    seeds = []
    for pid, name, lon, lat, owner, culture, religion in PROVINCES:
        x, y = geo.to_map(lon, lat)
        seeds.append(snap(land, int(y / CELL), int(x / CELL)))
    print(f"Growing {len(seeds)} provinces ...")
    grid = grow(cost, land, seeds)
    labels = np.repeat(np.repeat(grid, CELL, axis=0), CELL, axis=1)[:geo.HEIGHT, :geo.WIDTH]
    labels = majority(np.where(ground.land, labels, 0), ground.land)
    rgb = np.zeros(labels.shape + (3,), np.uint8)
    rgb[..., 0] = labels & 255
    rgb[..., 1] = labels >> 8
    Image.fromarray(rgb).save(OUT / "provinces.png")

    print("Describing them ...")
    climate = ground.climate()
    sea = ~ground.land
    out = []
    for i, (pid, name, lon, lat, owner, culture, religion) in enumerate(PROVINCES, start=1):
        mask = labels == i
        area = int(mask.sum())
        if not area:
            print(f"  ! {pid} has no land")
            continue
        rows, cols = np.nonzero(mask)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        sub = mask[r0:r1, c0:c1]
        # the label goes where the province is thickest
        inner = blur(sub.astype(np.float32), 6, passes=2) * sub
        lr, lc = np.unravel_index(np.argmax(inner), inner.shape)
        grown = np.zeros_like(mask)
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        touching = np.unique(labels[grown & ~mask])
        neighbors = sorted(PROVINCES[k - 1][0] for k in touching if k > 0)
        stats = {"high": float((climate["h"][mask] > 1000).mean()), "slope": float(climate["slope"][mask].mean()),
                 "woods": float(climate["woods"][mask].mean()), "arid": float(climate["arid"][mask].mean())}
        terrain = "marsh" if pid in MARSHES else terrain_of(stats)
        km2 = area * geo.KM_PER_PX ** 2
        people = km2 * DENSITY[terrain] * REGION.get(owner, 0.8) / 1000 + CITIES.get(pid, 0)
        x, y = geo.to_map(lon, lat)
        out.append({
            "id": pid, "index": i, "name": name, "owner": owner, "culture": culture, "religion": religion,
            "town": [round(x, 1), round(y, 1)], "label": [int(c0 + lc), int(r0 + lr)],
            "area": round(km2), "terrain": terrain, "woods": round(stats["woods"], 2),
            "arid": round(stats["arid"], 2), "population": round(people, 1), "city": CITIES.get(pid, 0),
            "good": GOODS.get(pid, default_good(terrain, lat)), "fort": FORTS.get(pid, 1 if CITIES.get(pid) else 0),
            "coastal": bool((grown & sea).any()), "neighbors": neighbors,
        })
    (OUT / "provinces.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} provinces written")


if __name__ == "__main__":
    main()
