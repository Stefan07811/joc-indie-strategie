"""Paints the campaign map: a painted-atlas look made entirely in code.

Layers, bottom to top:
  1. an elevation field (terrain heights plus fractal noise, ridges in the mountains), lit from the
     north-west (hill-shading) and coloured by terrain, painted at grid resolution and smoothed up;
  2. a canvas grain;
  3. hills, marsh pools, ploughed fields, forests (tree by tree) and mountains (peak by peak);
  4. rivers and roads;
  5. towns, castles and the Heart's shrine;
  6. an old-map tone and a vignette.

Painting takes a second or two, so the result is kept in memory and in ~/.legendele/cache.
Province ownership, highlights, labels and armies are drawn on top every frame (map_view.py).
"""

import hashlib
import json
import math
import random

import pygame

from ..mapshape import CELL, WARP, _noise, land_mask
from . import figures, theme

PAINTER_VERSION = 4
HEIGHT = {"sea": 0.0, "marsh": 0.10, "plains": 0.22, "forest": 0.32, "hills": 0.52, "mountains": 0.86}
COLOR = {
    "plains": (166, 168, 104), "hills": (164, 148, 104), "forest": (92, 112, 70),
    "marsh": (104, 116, 96), "mountains": (150, 142, 130), "sea": (92, 124, 134),
}
SHALLOW, DEEP = (122, 152, 150), (58, 86, 104)
LAND, ABROAD, SEA = 0, 1, 2
LIGHT = (-0.7, -0.7)  # the sun stands in the north-west
SHADE_STRENGTH = 2.2

_memory = {}


def paint(data, grid, cache_dir=None):
    """The static map as a Surface (memory and disk cached)."""
    key = _key(data)
    if key in _memory:
        return _memory[key]
    path = cache_dir / f"map-{key}.png" if cache_dir else None
    if path and path.exists():
        try:
            image = pygame.image.load(str(path))
            _memory[key] = image.convert() if pygame.display.get_surface() else image
            return _memory[key]
        except pygame.error:
            pass
    image = _paint(data, grid)
    if path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(image, str(path))
        except (OSError, pygame.error):
            pass
    _memory[key] = image
    return image


def _key(data):
    blob = json.dumps({"provinces": data.provinces, "terrain": data.terrain, "v": PAINTER_VERSION,
                       **{k: data.map.get(k) for k in ("width", "height", "rivers", "ranges", "land", "sea", "foreign")}},
                      sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


# --- noise -----------------------------------------------------------------------------------

def _hash(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 982451653) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 0xFFFF


def _fbm_field(cols, rows, scale, seed, octaves=4):
    """Fractal value noise (0..1) at every cell, one lattice point every `scale` cells, halving
    for each octave; built from upscaled lattice images rather than cell by cell."""
    norm = sum(0.5 ** o for o in range(octaves))
    acc = pygame.Surface((cols, rows))
    acc.fill((0, 0, 0))
    for o in range(octaves):
        step = scale / 2 ** o  # cells between two lattice points
        w, h = int(cols / step) + 2, int(rows / step) + 2
        lattice = pygame.Surface((w, h))
        amp = 0.5 ** o / norm
        for y in range(h):
            for x in range(w):
                v = int(255 * amp * _hash(x, y, seed + o))
                lattice.set_at((x, y), (v, v, v))
        big = pygame.transform.smoothscale(lattice, (max(cols, round(w * step)), max(rows, round(h * step))))
        acc.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    return [v / 255 for v in pygame.image.tobytes(acc, "RGB")[::3]]


def _blur(field, cols, rows, radius):
    """Separable box blur of a flat list (rows x cols)."""
    out = field[:]
    for _ in range(2):
        tmp = [0.0] * len(out)
        for r in range(rows):
            base = r * cols
            acc = sum(out[base + min(cols - 1, max(0, c))] for c in range(-radius, radius + 1))
            for c in range(cols):
                tmp[base + c] = acc / (2 * radius + 1)
                acc += out[base + min(cols - 1, c + radius + 1)] - out[base + max(0, c - radius)]
        out2 = [0.0] * len(out)
        for c in range(cols):
            acc = sum(tmp[min(rows - 1, max(0, r)) * cols + c] for r in range(-radius, radius + 1))
            for r in range(rows):
                out2[r * cols + c] = acc / (2 * radius + 1)
                acc += tmp[min(rows - 1, r + radius + 1) * cols + c] - tmp[max(0, r - radius) * cols + c]
        out = out2
    return out


# --- the painting ----------------------------------------------------------------------------

def _ranges(data, cols, rows):
    """Per cell, how deep into a mountain chain it lies: 1 on the crest, 0 beyond its foothills."""
    layer = pygame.Surface((cols, rows))
    layer.fill((0, 0, 0))
    steps = 12
    for chain in data.map.get("ranges", []):
        points = [(x / CELL, y / CELL) for x, y in chain["points"]]
        for k in range(steps):
            width = max(1, round(2 * chain["width"] / CELL * (1 - k / steps)))
            v = round(255 * (k + 1) / steps)
            band = pygame.Surface((cols, rows))
            band.fill((0, 0, 0))
            pygame.draw.lines(band, (v, v, v), False, points, width)
            for x, y in points:
                pygame.draw.circle(band, (v, v, v), (x, y), width / 2)
            layer.blit(band, (0, 0), special_flags=pygame.BLEND_RGB_MAX)
    small = pygame.transform.smoothscale(pygame.transform.smoothscale(layer, (cols // 2, rows // 2)), (cols, rows))
    return [small.get_at((c, r))[0] / 255 for r in range(rows) for c in range(cols)]


def _regions(data, grid):
    """Per cell: the terrain as painted, how mountainous it is, and whether it is our land, a land
    beyond the border or the sea. The great chains are painted where they truly run, whatever the
    provinces' terrain says; a province of "mountains" off the chains is painted as high hills."""
    rows, cols = len(grid), len(grid[0])
    chains = _ranges(data, cols, rows)
    terrain_of = {p["id"]: p["terrain"] for p in data.provinces}
    sea = land_mask([tuple(p) for p in data.map["sea"]], cols, rows) if data.map.get("sea") else None
    abroad = [f for f in data.map.get("foreign", []) if f["terrain"] != "sea"]
    terrain, region = [], []
    for r, row in enumerate(grid):
        for c, pid in enumerate(row):
            if pid is not None:
                # the land's look wanders off the political borders
                wc = c + round(_noise(c * 2.3, r * 2.3) * 7)
                wr = r + round(_noise(r * 2.3 + 57, c * 2.3 + 13) * 7)
                other = grid[wr][wc] if 0 <= wr < rows and 0 <= wc < cols else None
                terrain.append(terrain_of[other if other is not None else pid])
                region.append(LAND)
            elif sea and sea[r][c]:
                terrain.append("sea")
                region.append(SEA)
            else:
                x, y = c * CELL, r * CELL
                wx, wy = x + _noise(x / 3, y / 3) * WARP * 6, y + _noise(y / 3 + 311, x / 3 + 97) * WARP * 6
                near = min(abroad, key=lambda f: (f["x"] - wx) ** 2 + (f["y"] - wy) ** 2) if abroad else None
                terrain.append(near["terrain"] if near else "plains")
                region.append(ABROAD)
    if chains and any(chains):
        for i, t in enumerate(terrain):
            if t == "sea":
                continue
            if chains[i] > 0.5:
                terrain[i] = "mountains"
            elif chains[i] > 0.2:
                terrain[i] = "forest" if t != "marsh" else t
            elif t == "mountains":
                terrain[i] = "hills"
    return terrain, region, chains


def _paint(data, grid):
    rows, cols = len(grid), len(grid[0])
    width, height = cols * CELL, rows * CELL
    cell_terrain, region, chains = _regions(data, grid)
    depth = _blur([1.0 if k == SEA else 0.0 for k in region], cols, rows, 6)

    # 1. elevation, light and colour at grid resolution
    relief, ridges = _fbm_field(cols, rows, 14, 11), _fbm_field(cols, rows, 7, 29)
    waves, moisture = _fbm_field(cols, rows, 9, 53), _fbm_field(cols, rows, 20, 41)
    raw = [HEIGHT[t] + 0.3 * k for t, k in zip(cell_terrain, chains)]
    elevation = _blur(raw, cols, rows, 3)
    for i, t in enumerate(cell_terrain):
        elevation[i] += (relief[i] - 0.5) * 0.16
        if t == "mountains":
            ridge = 1 - abs(ridges[i] * 2 - 1)
            elevation[i] += ridge * 0.35 * min(1.0, raw[i])
    small = pygame.Surface((cols, rows))
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if region[i] == SEA:
                k = min(1.0, max(0.0, (depth[i] - 0.5) * 2.2 + (waves[i] - 0.5) * 0.3))
                small.set_at((c, r), tuple(int(SHALLOW[j] + (DEEP[j] - SHALLOW[j]) * k) for j in range(3)))
                continue
            h = elevation[i]
            dx = elevation[i + 1 if c < cols - 1 else i] - elevation[i - 1 if c > 0 else i]
            dy = elevation[i + cols if r < rows - 1 else i] - elevation[i - cols if r > 0 else i]
            shade = 1.0 + SHADE_STRENGTH * (dx * LIGHT[0] + dy * LIGHT[1]) * -1
            shade = max(0.55, min(1.35, shade))
            base = COLOR[cell_terrain[i]]
            wet = moisture[i] - 0.5
            tint = (1 - 0.18 * wet, 1 + 0.10 * wet, 1 - 0.06 * wet)
            lift = 1 + (h - 0.4) * 0.25
            small.set_at((c, r), tuple(max(0, min(255, int(base[k] * tint[k] * lift * shade))) for k in range(3)))
    surface = pygame.transform.smoothscale(small, (width, height))
    surface = pygame.transform.smoothscale(pygame.transform.smoothscale(surface, (cols * 2, rows * 2)),
                                           (width, height))

    # 2. canvas grain
    surface.blit(_grain(width, height), (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    rng = random.Random(1400)
    centres = [(p["x"], p["y"]) for p in data.provinces]

    def terrain_at(x, y):
        c, r = int(x) // CELL, int(y) // CELL
        if 0 <= c < cols and 0 <= r < rows:
            return cell_terrain[r * cols + c]
        return None

    def near_centre(x, y, rx=46, ry=34, soft=0.0):
        """Inside the oval clearing around a settlement (with a ragged edge when `soft`)."""
        for cx, cy in centres:
            d = ((x - cx) / rx) ** 2 + ((y - cy + 6) / ry) ** 2
            if d < 1 + soft * (rng.random() - 0.5):
                return True
        return False

    # 3. the land's features
    _waves(surface, rng, terrain_at, width, height)
    _hills(surface, rng, terrain_at, near_centre, width, height)
    _marsh(surface, rng, terrain_at, near_centre, width, height)
    _fields(surface, rng, terrain_at, data.provinces)
    _rivers(surface, data.map.get("rivers", []))
    _roads(surface, data.provinces, rng)
    _forests(surface, rng, terrain_at, near_centre, width, height)
    _mountains(surface, rng, terrain_at, near_centre, width, height)

    # 4b. the lands beyond the border fade out; the coast and the border are inked in
    _frontiers(surface, grid, region, cols, rows)

    # 5. settlements
    capitals = {f["capital"] for f in data.factions.values() if f["capital"]}
    for p in sorted(data.provinces, key=lambda p: p["y"]):
        if p.get("special") == "heart":
            image = figures.shrine()
        elif p.get("walls") or p["id"] in capitals:
            image = figures.castle(rng.random())
        else:
            image = figures.village(rng.random(), p["terrain"])
        surface.blit(image, image.get_rect(midbottom=(p["x"], p["y"] - 14)))

    # 6. the names of the lands beyond, and an old-map tone
    for f in data.map.get("foreign", []):
        sea = f["terrain"] == "sea"
        _label(surface, f["name"], (f["x"], f["y"]), (196, 214, 214) if sea else (70, 54, 40),
               (40, 62, 76) if sea else (214, 202, 172))
    tone = pygame.Surface((width, height))
    tone.fill((255, 244, 222))
    surface.blit(tone, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return surface


def _label(surface, name, pos, color, halo):
    """A spaced-out italic name, as on an old atlas."""
    spaced = " ".join(name.upper())
    rect = theme.outlined(pygame.Surface((1, 1)), spaced, pos, 22, color, halo, style="italic", width=1)
    area = surface.get_rect().inflate(-32, -32)
    theme.outlined(surface, spaced, rect.clamp(area).center, 22, color, halo, style="italic", width=1)


def _frontiers(surface, grid, region, cols, rows):
    wash, ink = pygame.Surface((cols, rows), pygame.SRCALPHA), pygame.Surface((cols, rows), pygame.SRCALPHA)
    for r in range(rows):
        for c in range(cols):
            k = region[r * cols + c]
            if k == ABROAD:
                wash.set_at((c, r), (196, 182, 150, 150))
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if not (0 <= nc < cols and 0 <= nr < rows):
                    continue
                other = region[nr * cols + nc]
                if k != SEA and other == SEA:
                    ink.set_at((c, r), (52, 66, 70, 220))  # the coastline
                elif k == LAND and other == ABROAD:
                    ink.set_at((c, r), (120, 36, 28, 210))  # the realm's border
    size = (cols * CELL, rows * CELL)
    surface.blit(pygame.transform.smoothscale(wash, size), (0, 0))
    surface.blit(pygame.transform.smoothscale(ink, size), (0, 0))


def _waves(surface, rng, terrain_at, width, height):
    for x, y in _jittered(rng, width, height, 46):
        if terrain_at(x, y) != "sea" or terrain_at(x + 30, y) != "sea" or terrain_at(x - 30, y) != "sea":
            continue
        w = rng.uniform(10, 18)
        for k in range(2):
            rect = pygame.Rect(x + k * w - w, y, w, 7)
            pygame.draw.arc(surface, (150, 176, 180), rect, 0.3, math.pi - 0.3, 1)


def _grain(width, height):
    rng = random.Random(7)
    tile = pygame.Surface((96, 96))
    tile.fill((255, 255, 255))
    for _ in range(2600):
        v = rng.randint(222, 255)
        tile.fill((v, v, v - rng.randint(0, 6)), (rng.randrange(96), rng.randrange(96), rng.choice((1, 2)), 1))
    tile = pygame.transform.smoothscale(pygame.transform.smoothscale(tile, (64, 64)), (96, 96))
    out = pygame.Surface((width, height))
    for x in range(0, width, 96):
        for y in range(0, height, 96):
            out.blit(tile, (x, y))
    return out


def _vignette(width, height):
    small = pygame.Surface((48, 36))
    for y in range(36):
        for x in range(48):
            dx, dy = (x - 23.5) / 24, (y - 17.5) / 18
            v = max(0.0, min(1.0, 1.18 - 0.42 * (dx * dx + dy * dy) ** 1.4))
            small.set_at((x, y), (int(255 * v),) * 3)
    return pygame.transform.smoothscale(small, (width, height))


def _jittered(rng, width, height, step):
    for gy in range(0, height, step):
        for gx in range(0, width, step):
            yield gx + rng.uniform(0, step), gy + rng.uniform(0, step)


def _hills(surface, rng, terrain_at, near_centre, width, height):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for x, y in _jittered(rng, width, height, 38):
        if terrain_at(x, y) != "hills" or near_centre(x, y, soft=0.6) or rng.random() < 0.25:
            continue
        w, h = rng.uniform(36, 58), rng.uniform(13, 20)
        rect = pygame.Rect(0, 0, w, h)
        rect.midbottom = (x, y)
        pygame.draw.ellipse(layer, (96, 80, 50, 90), rect.move(4, 3))  # the shaded flank
        pygame.draw.ellipse(layer, (182, 166, 116, 150), rect)
        top = rect.inflate(-w * 0.4, -h * 0.45).move(-w * 0.14, -h * 0.2)
        pygame.draw.ellipse(layer, (210, 196, 148, 130), top)  # the sunlit crest
    surface.blit(layer, (0, 0))


def _marsh(surface, rng, terrain_at, near_centre, width, height):
    for x, y in _jittered(rng, width, height, 34):
        if terrain_at(x, y) != "marsh" or near_centre(x, y, soft=0.6) or rng.random() < 0.3:
            continue
        # an irregular pool: a few overlapping blobs
        blobs = [(x + rng.uniform(-14, 14), y + rng.uniform(-5, 5), rng.uniform(10, 22), rng.uniform(5, 9))
                 for _ in range(rng.randint(2, 4))]
        for bx, by, bw, bh in blobs:
            pygame.draw.ellipse(surface, (70, 88, 76), (bx - bw - 2, by - bh - 1, 2 * bw + 4, 2 * bh + 3))
        for bx, by, bw, bh in blobs:
            pygame.draw.ellipse(surface, (88, 116, 122), (bx - bw, by - bh, 2 * bw, 2 * bh))
        for bx, by, bw, bh in blobs[:1]:
            pygame.draw.ellipse(surface, (138, 162, 164), (bx - bw * 0.6, by - bh * 0.7, bw, bh * 0.6))
        for k in range(rng.randint(3, 7)):
            rx, ry = x + rng.uniform(-26, 26), y + rng.uniform(-8, 10)
            pygame.draw.line(surface, (62, 82, 50), (rx, ry), (rx + rng.uniform(-1.5, 1.5), ry - rng.uniform(5, 9)), 1)


def _fields(surface, rng, terrain_at, provinces):
    colors = ((188, 176, 104), (170, 172, 98), (200, 184, 120), (150, 160, 92), (182, 160, 96))
    for p in provinces:
        if p["terrain"] not in ("plains", "hills"):
            continue
        for _ in range(26 if p["terrain"] == "plains" else 12):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(40, 95)
            x, y = p["x"] + math.cos(a) * d * 1.3, p["y"] + math.sin(a) * d
            if terrain_at(x, y) != p["terrain"]:
                continue
            w, h = rng.uniform(14, 26), rng.uniform(8, 14)
            field = pygame.Surface((w, h), pygame.SRCALPHA)
            color = rng.choice(colors)
            field.fill((*color, 150))
            for k in range(0, int(h), 3):
                pygame.draw.line(field, (*[max(0, c - 22) for c in color], 120), (0, k), (w, k))
            field = pygame.transform.rotate(field, rng.uniform(-25, 25))
            surface.blit(field, field.get_rect(center=(x, y)))


def _forests(surface, rng, terrain_at, near_centre, width, height):
    trees = []
    for x, y in _jittered(rng, width, height, 7):
        t = terrain_at(x, y)
        dense = t == "forest" or (t == "hills" and rng.random() < 0.06) or (t == "plains" and rng.random() < 0.02) \
            or (t == "marsh" and rng.random() < 0.05)
        if dense and not near_centre(x, y, 40, 30, soft=0.9):
            trees.append((y, x, rng.random()))
    for y, x, k in sorted(trees):
        r = 3.5 + 2.5 * k
        green = (46 + int(30 * k), 72 + int(26 * k), 40 + int(10 * k))
        pygame.draw.ellipse(surface, (40, 50, 30), (x - r + 2, y - r * 0.6 + 3, r * 2, r * 1.3))
        pygame.draw.circle(surface, green, (x, y), r)
        pygame.draw.circle(surface, tuple(min(255, c + 28) for c in green), (x - r * 0.35, y - r * 0.35), r * 0.5)


def _mountains(surface, rng, terrain_at, near_centre, width, height):
    peaks = []
    for x, y in _jittered(rng, width, height, 24):
        t = terrain_at(x, y)
        if t == "mountains" and not near_centre(x, y, 52, 44):
            peaks.append((y, x, rng.uniform(0.85, 1.25), True))
        elif t == "hills" and rng.random() < 0.08 and not near_centre(x, y, 52, 44):
            peaks.append((y, x, rng.uniform(0.55, 0.7), False))
    for y, x, size, snowy in sorted(peaks):
        w, h = 34 * size, 30 * size
        top = (x + rng.uniform(-3, 3), y - h)
        left, right = (x - w / 2, y), (x + w / 2, y)
        mid = (top[0] + rng.uniform(-2, 4), y)
        pygame.draw.polygon(surface, (70, 64, 60), [(left[0] + 4, y + 3), (top[0] + 4, top[1] + 3), (right[0] + 4, y + 3)])
        pygame.draw.polygon(surface, (172, 164, 150), [left, top, mid])  # sunlit face
        pygame.draw.polygon(surface, (104, 96, 90), [mid, top, right])  # shadowed face
        if snowy:
            cap = 0.32
            sl = (top[0] + (left[0] - top[0]) * cap, top[1] + (y - top[1]) * cap)
            sr = (top[0] + (right[0] - top[0]) * cap, top[1] + (y - top[1]) * cap)
            sm = (top[0] + (mid[0] - top[0]) * cap * 1.2, top[1] + (y - top[1]) * cap * 1.25)
            pygame.draw.polygon(surface, (244, 244, 240), [sl, top, sm])
            pygame.draw.polygon(surface, (196, 200, 206), [sm, top, sr])
        pygame.draw.lines(surface, (60, 54, 50), False, [left, top, right], 1)


def _spline(points, steps=8):
    """Catmull-Rom curve through the points."""
    pts = [points[0], *points, points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    out.append(tuple(points[-1]))
    return out


def _rivers(surface, rivers):
    for river in rivers:
        line = _spline(river["points"])
        big = river["name"] == "Danube"
        n = len(line)
        for i in range(n - 1):
            w = (9 if big else 2 + 4 * i / n)
            pygame.draw.line(surface, (58, 82, 98), line[i], line[i + 1], int(w + 3))
        for i in range(n - 1):
            w = (9 if big else 2 + 4 * i / n)
            pygame.draw.line(surface, (96, 132, 156), line[i], line[i + 1], int(w))
        for i in range(0, n - 1, 2):
            pygame.draw.line(surface, (150, 180, 196), line[i], line[i + 1], 1)


def _roads(surface, provinces, rng):
    by_id = {p["id"]: p for p in provinces}
    done = set()
    for p in provinces:
        for nid in p.get("neighbors", ()):
            pair = tuple(sorted((p["id"], nid)))
            if pair in done:
                continue
            done.add(pair)
            q = by_id[nid]
            if "mountains" in (p["terrain"], q["terrain"]) and p.get("special") != "heart" and q.get("special") != "heart":
                continue  # only passes through the high peaks lead to the Heart
            a, b = (p["x"], p["y"]), (q["x"], q["y"])
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            nx, ny = -(b[1] - a[1]), b[0] - a[0]
            length = math.hypot(nx, ny) or 1
            bend = rng.uniform(-0.12, 0.12) * length
            ctrl = (mx + nx / length * bend, my + ny / length * bend)
            curve = [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * ctrl[0] + t * t * b[0],
                      (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * ctrl[1] + t * t * b[1]) for t in (i / 24 for i in range(25))]
            for i in range(2, len(curve) - 3, 2):
                pygame.draw.line(surface, (120, 94, 62), curve[i], curve[i + 1], 2)
