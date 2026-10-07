"""The map's ground, computed from the real relief: heights, land and sea, the colour of the land
(steppe, fields, forest, rock, snow) and the lie of the land for lighting. Pure numpy, no graphics.

Everything is an array in map pixels (crowns/geo.py), row 0 in the north. Results are cached in the
player's folder, since the colour map takes a few seconds to make.
"""

import json
from functools import cached_property
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import geo

DATA = Path(__file__).resolve().parent / "data" / "map"
HEIGHT_OFFSET = 12000
UPSCALE = 2  # the colour and normal maps have this many texels per map pixel


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _blob(lon, lat, lon0, lat0, sigma):
    return np.exp(-(((lon - lon0) / sigma) ** 2 + ((lat - lat0) / (sigma * 0.75)) ** 2))


def blur(a, radius, passes=3):
    """A box blur repeated a few times (close to a gaussian), edges clamped."""
    a = a.astype(np.float32)
    r = max(1, int(radius))
    for _ in range(passes):
        for axis in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[axis] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def _area(points):
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    return abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))) / 2


def _noise(shape, cell, seed):
    """Smooth value noise in 0..1: random values on a coarse grid, enlarged with bicubic filtering."""
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, shape[0] // cell + 2), max(2, shape[1] // cell + 2))).astype(np.float32)
    img = Image.fromarray(small, mode="F").resize((shape[1], shape[0]), Image.BICUBIC)
    return np.clip(np.asarray(img), 0, 1)


class Ground:
    """The map's relief and its derived maps. `scale` texels per map pixel for colour and normals."""

    def __init__(self, scale=UPSCALE):
        self.scale = scale

    @cached_property
    def height(self):
        """Metres above sea level (negative at sea), one value per map pixel."""
        raw = np.asarray(Image.open(DATA / "height.png"), dtype=np.float32)
        return raw - HEIGHT_OFFSET

    @cached_property
    def lakes(self):
        mask = Image.new("L", (geo.WIDTH, geo.HEIGHT), 0)
        draw = ImageDraw.Draw(mask)
        for lake in json.loads((DATA / "lakes.json").read_text(encoding="utf-8")):
            if len(lake["points"]) > 2:
                draw.polygon([tuple(p) for p in lake["points"]], fill=255)
        return np.asarray(mask) > 127

    @cached_property
    def land(self):
        """True on dry land (above sea level and not a lake)."""
        return (self.height > 0.5) & ~self.lakes

    @cached_property
    def rivers(self):
        return json.loads((DATA / "rivers.json").read_text(encoding="utf-8"))

    def fine(self, a, resample=Image.BICUBIC):
        """An array at the colour map's resolution."""
        if self.scale == 1:
            return a
        img = Image.fromarray(a.astype(np.float32), mode="F")
        return np.asarray(img.resize((a.shape[1] * self.scale, a.shape[0] * self.scale), resample))

    def lonlat(self, shape):
        h, w = shape
        lon = geo.LON0 + (np.arange(w) + 0.5) / w * (geo.LON1 - geo.LON0)
        lat = geo.LAT1 - (np.arange(h) + 0.5) / h * (geo.LAT1 - geo.LAT0)
        return np.meshgrid(lon, lat)

    # --- colour ---------------------------------------------------------------------------------

    def climate(self):
        """The land's climate at this Ground's scale: heights, slope, how dry it is (arid 0..1) and
        where the forests stand (woods 0..1), plus the noise fields that vary the colours."""
        h = self.fine(self.height)
        shape = h.shape
        lon, lat = self.lonlat(shape)
        gy, gx = np.gradient(h)
        slope = np.hypot(gx, gy) * self.scale / (geo.KM_PER_PX * 1000)  # rise over run
        n1, n2, n3 = _noise(shape, 48, 1), _noise(shape, 12, 2), _noise(shape, 4, 3)
        # how dry the land is: the Anatolian plateau, Syria, the Pontic steppe, the Aegean summers
        arid = np.clip(0.80 * _blob(lon, lat, 34.0, 38.9, 3.6) + 0.95 * _blob(lon, lat, 38.8, 35.3, 3.0)
                       + 0.50 * _blob(lon, lat, 35.0, 47.2, 5.0) + 0.35 * _blob(lon, lat, 24.5, 37.6, 2.6)
                       + 0.30 * _blob(lon, lat, 28.2, 44.4, 1.4) + 0.22 * _blob(lon, lat, 20.3, 46.8, 1.6)
                       + 0.25 * _blob(lon, lat, 43.5, 40.0, 2.0), 0, 1)
        arid = np.clip(arid - smoothstep(600, 2000, h) * 0.35 + (n1 - 0.5) * 0.25, 0, 1)
        # forests: on hills and mountain sides where it is wet enough, in patches on the plains
        hilly = blur(smoothstep(200, 900, h) + smoothstep(0.015, 0.06, slope), 3 * self.scale)
        woods = np.clip(hilly * 0.55 + (n1 * 0.7 + n2 * 0.4 - 0.62), 0, 1) * (1 - smoothstep(0.2, 0.55, arid))
        woods = smoothstep(0.3, 0.7, blur(woods, self.scale))
        return {"h": h, "lon": lon, "lat": lat, "slope": slope, "noise": (n1, n2, n3), "arid": arid, "woods": woods}

    def colors(self):
        """RGB (0..1) of the land and the sea floor, `scale` texels per map pixel."""
        c = self.climate()
        h, lat, slope, arid, woods = c["h"], c["lat"], c["slope"], c["arid"], c["woods"]
        n1, n2, n3 = c["noise"]
        lush = np.array([0.33, 0.47, 0.20])
        dry = np.array([0.60, 0.58, 0.34])
        desert = np.array([0.74, 0.64, 0.45])
        forest = np.array([0.22, 0.35, 0.15])
        conifer = np.array([0.16, 0.28, 0.16])
        rock = np.array([0.47, 0.43, 0.39])
        snow = np.array([0.93, 0.94, 0.96])
        sand = np.array([0.80, 0.74, 0.55])
        grass = (lush * (1 - smoothstep(0.0, 0.55, arid))[..., None]
                 + dry * (smoothstep(0.0, 0.55, arid) - smoothstep(0.55, 0.95, arid))[..., None]
                 + desert * smoothstep(0.55, 0.95, arid)[..., None])
        grass *= (0.88 + 0.24 * n2)[..., None]
        trees = forest * (1 - smoothstep(900, 1600, h))[..., None] + conifer * smoothstep(900, 1600, h)[..., None]
        trees *= (0.8 + 0.4 * n3)[..., None]
        color = grass * (1 - woods)[..., None] + trees * woods[..., None]
        # bare rock above the tree line and on cliffs, snow on the highest peaks
        treeline = 1700 + (45 - lat) * 60
        bare = np.clip(smoothstep(treeline, treeline + 500, h) + smoothstep(0.12, 0.3, slope), 0, 1)
        color = color * (1 - bare)[..., None] + rock * (0.85 + 0.3 * n3)[..., None] * bare[..., None]
        snowline = 2600 + (45 - lat) * 90
        white = smoothstep(snowline, snowline + 400, h + (n2 - 0.5) * 300) * (1 - smoothstep(0.35, 0.6, slope))
        color = color * (1 - white)[..., None] + snow * white[..., None]
        # beaches, then the sea floor (the water shader colours it by depth)
        beach = (1 - smoothstep(1, 6, h)) * (h > 0) * 0.6
        color = color * (1 - beach)[..., None] + sand * beach[..., None]
        color[h <= 0] = sand * 0.7
        # valleys darker, ridges lighter: the shape of the land reads even under a flat light
        cavity = np.clip((h - blur(h, 6 * self.scale)) / 400, -0.25, 0.2)
        color *= (1 + cavity)[..., None]
        return np.clip(color, 0, 1)

    def draw_waters(self, rgb):
        """Rivers and lakes painted onto an RGB uint8 image (in place) at the colour map's scale."""
        img = Image.fromarray(rgb)
        draw = ImageDraw.Draw(img)
        s = self.scale
        water = (52, 92, 128)
        for lake in json.loads((DATA / "lakes.json").read_text(encoding="utf-8")):
            pts = lake["points"]
            if len(pts) > 2 and _area(pts) > 30:  # map pixels; the smallest ponds only look like ink blots
                draw.polygon([(x * s, y * s) for x, y in pts], fill=water)
        for river in sorted(self.rivers, key=lambda r: -r["rank"]):
            width = max(1, round((2.4 if river["rank"] <= 2 else 1.7 if river["rank"] <= 5 else 1.1) * s))
            draw.line([(x * s, y * s) for x, y in river["points"]], fill=water, width=width, joint="curve")
        return np.asarray(img)

    def color_map(self):
        """The finished colour map: RGB uint8, rivers and lakes included."""
        rgb = (self.colors() * 255).astype(np.uint8)
        return self.draw_waters(rgb)

    def coast_distance(self, reach=48):
        """Map pixels to the nearest coast: positive at sea, negative on land, clamped to +-reach.
        (Engraved maps draw lines along the shore at growing distances: 'waterlining'.)"""
        land = self.land | self.lakes  # lakes count as land here: only the sea gets waterlines
        out = np.full(land.shape, float(reach), np.float32)
        for side, mask in ((1.0, ~land), (-1.0, land)):
            dist = np.where(mask, np.inf, 0.0).astype(np.float32)
            for _ in range(reach):
                grown = dist.copy()
                for dr, dc, step in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                                     (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
                    grown = np.minimum(grown, np.roll(np.roll(dist, dr, 0), dc, 1) + step)
                if np.array_equal(grown, dist):
                    break
                dist = grown
            out = np.where(mask, side * np.minimum(dist, reach), out)
        # the chamfer distance draws octagons; a light blur rounds the waterlines like a pen would
        smooth = blur(out, 2, passes=2)
        return np.where(np.sign(smooth) == np.sign(out), smooth, out * 0.5)

    # --- light ----------------------------------------------------------------------------------

    def normal_map(self, exaggeration):
        """Surface normals (x east, y north, z up) for heights scaled like the 3D map, RGB uint8."""
        h = np.maximum(self.fine(self.height), 0) / 1000 / geo.KM_PER_PX * exaggeration  # in map pixels
        gy, gx = np.gradient(h)
        texel = 1 / self.scale
        nx, ny, nz = -gx / texel, gy / texel, np.ones_like(h)  # rows run south, so north is -row
        length = np.sqrt(nx * nx + ny * ny + nz * nz)
        n = np.stack([nx, ny, nz], axis=-1) / length[..., None]
        return ((n * 0.5 + 0.5) * 255).astype(np.uint8)
