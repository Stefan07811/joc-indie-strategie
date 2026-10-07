"""The towns on the map, as painted miniatures like the armies: a few houses for a village, a church, a
cathedral or a mosque with its minaret for a town, and walls with towers as strong as the town's
fortifications. The houses are roofed in red tile in the south, in shingle in the north; the Tatars
and Circassians live in felt tents. Shown when the camera comes close."""

import math
import zlib

import numpy as np
from panda3d.core import CullFaceAttrib

from .. import geo
from .figures import Builder, _shader, geom_node

SCALE = 1.9
SHOW_BELOW = 900.0          # camera distance under which the towns appear
STONE = (0.76, 0.72, 0.63)
DARK_STONE = (0.55, 0.52, 0.46)
PLASTER = (0.91, 0.87, 0.77)
TIMBER = (0.62, 0.52, 0.40)
TILE = (0.70, 0.30, 0.21)
SHINGLE = (0.40, 0.31, 0.24)
LEAD = (0.55, 0.60, 0.64)
FELT = (0.90, 0.86, 0.76)
GROUND = (0.60, 0.53, 0.38)
NORTH = {"romanian", "ruthenian", "polish", "lithuanian", "hungarian", "czech", "german", "slovak", "slovene",
         "croatian"}
TENTS = {"tatar", "circassian"}


def _size(city):
    return 0 if city < 2 else (1 if city < 8 else (2 if city < 20 else 3))


def _house(b, x, y, yaw, roof, rng, big=1.0):
    w, d, h = rng.uniform(0.45, 0.7) * big, rng.uniform(0.6, 0.95) * big, rng.uniform(0.38, 0.6) * big
    walls = PLASTER if rng.random() < 0.6 else TIMBER
    b.box((x, y, h / 2), (w, d, h), walls, yaw=yaw)
    # a gabled roof: two slopes along the house
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def p(lx, ly, z):
        return (x + lx * c - ly * s, y + lx * s + ly * c, z)
    rh = h + 0.32 * big
    hw, hd = w / 2 + 0.06, d / 2 + 0.06
    b.quad(p(-hw, -hd, h), p(0, -hd, rh), p(0, hd, rh), p(-hw, hd, h), roof)
    b.quad(p(hw, hd, h), p(0, hd, rh), p(0, -hd, rh), p(hw, -hd, h), roof)
    b.tri(p(-hw, -hd, h), p(hw, -hd, h), p(0, -hd, rh), walls)
    b.tri(p(hw, hd, h), p(-hw, hd, h), p(0, hd, rh), walls)


def _tent(b, x, y, rng):
    r = rng.uniform(0.35, 0.5)
    b.cylinder((x, y, 0), r, 0.35, FELT, sides=8)
    b.cylinder((x, y, 0.35), r, 0.3, FELT, sides=8, top=0.08)


def _catholic(b, x, y, big):
    b.box((x, y, 0.45 * big), (0.7 * big, 1.6 * big, 0.9 * big), STONE)
    b.cylinder((x - 0.35 * big, y + 0.8 * big, 0.9 * big), 0.36 * big, 0.5 * big, TILE, sides=4, top=0.0)
    b.box((x, y - 1.0 * big, 0.9 * big), (0.5 * big, 0.5 * big, 1.8 * big), STONE)
    b.cylinder((x, y - 1.0 * big, 1.8 * big), 0.38 * big, 1.1 * big, SHINGLE, sides=4, top=0.0)


def _orthodox(b, x, y, big):
    b.box((x, y, 0.45 * big), (1.1 * big, 1.3 * big, 0.9 * big), PLASTER)
    b.cylinder((x, y, 0.9 * big), 0.38 * big, 0.45 * big, PLASTER, sides=8)
    b.cylinder((x, y, 1.35 * big), 0.4 * big, 0.35 * big, LEAD, sides=8, top=0.12 * big)
    b.cylinder((x, y, 1.7 * big), 0.03, 0.3 * big, (0.8, 0.65, 0.25), sides=4)
    for dx, dy in ((-0.4, -0.45), (0.4, -0.45), (-0.4, 0.45), (0.4, 0.45)):
        b.cylinder((x + dx * big, y + dy * big, 0.9 * big), 0.16 * big, 0.3 * big, LEAD, sides=6, top=0.0)


def _mosque(b, x, y, big):
    b.box((x, y, 0.4 * big), (1.2 * big, 1.2 * big, 0.8 * big), PLASTER)
    b.cylinder((x, y, 0.8 * big), 0.55 * big, 0.25 * big, LEAD, sides=10, top=0.48 * big)
    b.cylinder((x, y, 1.05 * big), 0.48 * big, 0.3 * big, LEAD, sides=10, top=0.12 * big)
    b.cylinder((x + 0.8 * big, y - 0.6 * big, 0), 0.13 * big, 2.3 * big, PLASTER, sides=6)
    b.cylinder((x + 0.8 * big, y - 0.6 * big, 2.3 * big), 0.14 * big, 0.45 * big, LEAD, sides=6, top=0.0)


def _walls(b, radius, fort):
    height = 0.55 + 0.25 * fort
    towers = 4 + 2 * fort
    segments = towers * 2
    for k in range(segments):
        a0, a1 = 2 * math.pi * k / segments, 2 * math.pi * (k + 1) / segments
        mid = (a0 + a1) / 2
        length = 2 * radius * math.sin(math.pi / segments) + 0.05
        b.box((math.cos(mid) * radius, math.sin(mid) * radius, height / 2), (0.22, length, height), STONE,
              yaw=math.degrees(mid))
    for k in range(towers):
        a = 2 * math.pi * (k + 0.5) / towers
        x, y = math.cos(a) * radius, math.sin(a) * radius
        b.cylinder((x, y, 0), 0.3, height + 0.35, DARK_STONE, sides=6)
        b.cylinder((x, y, height + 0.35), 0.36, 0.45, TILE, sides=6, top=0.0)
    if fort >= 2:   # a keep at the heart
        b.box((0, 0.3, (height + 0.9) / 2), (0.8, 0.8, height + 0.9), DARK_STONE)
        b.cylinder((0, 0.3, height + 0.9), 0.62, 0.55, SHINGLE, sides=4, top=0.0)


def town_model(city, fort, religion, culture, seed):
    """The triangles of one town: (verts (n, 3, 3), colours (n, 4)), centred on (0, 0) at ground level."""
    rng = np.random.default_rng(seed)
    b = Builder()
    size = _size(city)
    radius = 1.4 + 0.7 * size
    b.cylinder((0, 0, -0.6), radius + 0.45, 0.62, GROUND, sides=14)
    tents = culture in TENTS
    roof = SHINGLE if culture in NORTH else TILE
    houses = (3, 6, 10, 15)[size]
    church_at = (0.0, -0.2) if size else None
    placed = []
    for i in range(houses):
        for _ in range(12):
            r = rng.uniform(0.5, radius - 0.4)
            a = rng.uniform(0, 2 * math.pi)
            x, y = math.cos(a) * r, math.sin(a) * r
            if church_at and math.hypot(x - church_at[0], y - church_at[1]) < 1.1 + 0.3 * size:
                continue
            if all(math.hypot(x - px, y - py) > 0.75 for px, py in placed):
                break
        placed.append((x, y))
        if tents:
            _tent(b, x, y, rng)
        else:
            _house(b, x, y, rng.uniform(0, 180), roof, rng, big=1.0 + 0.15 * size)
    if size and not tents:
        big = 0.8 + 0.25 * size
        if religion == "sunni":
            _mosque(b, *church_at, big)
        elif religion in ("orthodox", "armenian"):
            _orthodox(b, *church_at, big)
        else:
            _catholic(b, *church_at, big)
    if fort > 0:
        _walls(b, radius, min(fort, 4))
    verts, colors = b.arrays()
    return verts * SCALE, colors


class Towns:
    """All the towns of the map in one painted mesh with its ink outline, rebuilt when walls rise."""

    def __init__(self, parent, campaign, height_at, sun):
        self.root = parent.attachNewNode("towns")
        self.root.setShader(_shader("figure"))
        self.root.setShaderInputs(sun_dir=sun, outline=0.0)
        self.campaign = campaign
        self.height_at = height_at
        self.models = {}
        self.signature = None
        self.rebuild()

    def _signature(self):
        c = self.campaign
        return tuple(c.fort(pid) for pid in sorted(c.provinces))

    def rebuild(self, force=False):
        signature = self._signature()
        if signature == self.signature and not force:
            return
        self.signature = signature
        c = self.campaign
        all_verts, all_colors = [], []
        for pid, p in sorted(c.provinces.items()):
            info = c.static(pid)
            fort = c.fort(pid)
            key = (_size(info.city), min(fort, 4), info.religion, info.culture)
            if key not in self.models:
                self.models[key] = town_model(info.city, fort, info.religion, info.culture,
                                              zlib.crc32(repr(key).encode()))
            verts, colors = self.models[key]
            yaw = (zlib.crc32(pid.encode()) % 360) * math.pi / 180
            rot = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
            x, y = info.town[0], geo.HEIGHT - info.town[1]
            z = max(self.height_at(x + dx, y + dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2))
            all_verts.append(verts @ rot.T + np.array([x, y, z]))
            all_colors.append(colors)
        verts, colors = np.concatenate(all_verts), np.concatenate(all_colors)
        self.root.getChildren().detach()
        body = self.root.attachNewNode(geom_node("towns", verts, colors))
        ink = self.root.attachNewNode(geom_node("towns-ink", verts, colors, smooth=True))
        ink.setShader(_shader("figure_outline"), 1)
        ink.setShaderInput("outline", 0.09)
        ink.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)
        self.body = body

    def update(self, camera_distance):
        if camera_distance < SHOW_BELOW:
            self.root.show()
        else:
            self.root.hide()
