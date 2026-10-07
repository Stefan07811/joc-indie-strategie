"""Armies on the campaign map: painted miniatures on round bases, like hand-painted tin soldiers.

A miniature is built in code from simple solids (boxes, cylinders, cones), flat-shaded with vertex
colours, and drawn with an ink outline (a slightly inflated copy showing only its back faces), so the
figures sit on the engraved map like figures in a manuscript's margin. Armies march along their path
with a soldier's bob, turning to face where they go; their banners wave.
"""

import math
from pathlib import Path

import numpy as np
from panda3d.core import (CullFaceAttrib, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData,
                          GeomVertexFormat, NodePath, Shader, Vec3)

SHADERS = Path(__file__).resolve().parent / "shaders"
SKIN = (0.86, 0.70, 0.55)
STEEL = (0.62, 0.63, 0.66)
DARK = (0.18, 0.15, 0.13)
WOOD = (0.45, 0.32, 0.20)
BASE = (0.26, 0.28, 0.17)

_FORMAT = None


def _format():
    global _FORMAT
    if _FORMAT is None:
        arr = GeomVertexArrayFormat()
        arr.addColumn("vertex", 3, Geom.NT_float32, Geom.C_point)
        arr.addColumn("normal", 3, Geom.NT_float32, Geom.C_normal)
        arr.addColumn("color", 4, Geom.NT_float32, Geom.C_color)
        _FORMAT = GeomVertexFormat.registerFormat(GeomVertexFormat(arr))
    return _FORMAT


def _rot(yaw=0.0, pitch=0.0, roll=0.0):
    """Rotation matrix: roll about y, then pitch about x, then yaw about z (degrees)."""
    y, p, r = (math.radians(a) for a in (yaw, pitch, roll))
    rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    ry = np.array([[math.cos(r), 0, math.sin(r)], [0, 1, 0], [-math.sin(r), 0, math.cos(r)]])
    return rz @ rx @ ry


class Builder:
    """Collects flat-shaded, vertex-coloured triangles."""

    def __init__(self):
        self.tris = []  # (3x3 vertices, colour)

    def tri(self, a, b, c, color):
        self.tris.append((np.array([a, b, c], np.float64), color))

    def quad(self, a, b, c, d, color, double=False):
        self.tri(a, b, c, color)
        self.tri(a, c, d, color)
        if double:
            self.tri(a, c, b, color)
            self.tri(a, d, c, color)

    def box(self, centre, size, color, yaw=0.0, pitch=0.0, roll=0.0):
        sx, sy, sz = (s / 2 for s in size)
        corners = np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)])
        v = corners @ _rot(yaw, pitch, roll).T + np.array(centre)
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for f in faces:
            self.quad(*(v[i] for i in f), color)

    def cylinder(self, base, radius, height, color, sides=8, top=None, axis=(0.0, 0.0), cap=True):
        """A cylinder (or a cone with top=0, or a frustum) standing on `base`, tilted by axis=(yaw, pitch)."""
        top = radius if top is None else top
        rot = _rot(axis[0], axis[1])
        o = np.array(base)
        ring = [(math.cos(2 * math.pi * k / sides), math.sin(2 * math.pi * k / sides)) for k in range(sides)]
        lo = [rot @ np.array([c * radius, s * radius, 0.0]) + o for c, s in ring]
        hi = [rot @ np.array([c * top, s * top, height]) + o for c, s in ring]
        for k in range(sides):
            n = (k + 1) % sides
            if top > 0:
                self.quad(lo[k], lo[n], hi[n], hi[k], color)
            else:
                self.tri(lo[k], lo[n], hi[k], color)
        if cap:
            cb, ct = rot @ np.array([0, 0, 0.0]) + o, rot @ np.array([0, 0, height]) + o
            for k in range(sides):
                n = (k + 1) % sides
                self.tri(cb, lo[n], lo[k], color)
                if top > 0:
                    self.tri(ct, hi[k], hi[n], color)

    def node(self, name, smooth=False):
        """The triangles as a GeomNode: flat-shaded, or with normals averaged at shared corners
        (smooth=True, for the ink outline, which must swell without tearing apart)."""
        verts = np.array([v for v, _ in self.tris], np.float64)                  # (n, 3, 3)
        colors = np.array([(*c, 1.0) for _, c in self.tris], np.float64)         # (n, 4)
        n = np.cross(verts[:, 1] - verts[:, 0], verts[:, 2] - verts[:, 0])
        length = np.linalg.norm(n, axis=1, keepdims=True)
        n = np.where(length > 1e-9, n / np.maximum(length, 1e-9), np.array([0.0, 0.0, 1.0]))
        count = len(self.tris)
        data = np.concatenate([verts.reshape(-1, 3), np.repeat(n, 3, axis=0), np.repeat(colors, 3, axis=0)],
                              axis=1).astype(np.float32)
        assert data.shape == (count * 3, 10)
        if smooth:
            keys = np.round(data[:, :3] * 200).astype(np.int64)
            _, inverse = np.unique(keys, axis=0, return_inverse=True)
            sums = np.zeros((inverse.max() + 1, 3), np.float64)
            np.add.at(sums, inverse.ravel(), data[:, 3:6])
            norms = sums / np.maximum(np.linalg.norm(sums, axis=1, keepdims=True), 1e-9)
            data[:, 3:6] = norms[inverse.ravel()]
        vdata = GeomVertexData(name, _format(), Geom.UH_static)
        vdata.uncleanSetNumRows(len(data))
        vdata.modifyArrayHandle(0).copyDataFrom(data.tobytes())
        tris = GeomTriangles(Geom.UH_static)
        tris.addConsecutiveVertices(0, len(data))
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        return node


# --- the miniatures -------------------------------------------------------------------------

def _soldier(b, x, y, color, accent, eastern=False, facing=0.0):
    """A foot soldier standing at (x, y) on the base, spear in hand, shield on his arm."""
    b.box((x - 0.09, y, 0.32), (0.14, 0.16, 0.62), DARK)
    b.box((x + 0.09, y, 0.32), (0.14, 0.16, 0.62), DARK)
    b.cylinder((x, y, 0.58), 0.27, 0.78, color, sides=7, top=0.21)
    b.box((x, y, 1.42), (0.30, 0.30, 0.30), SKIN)
    if eastern:  # the tall white felt cap of the Ottoman infantry
        b.cylinder((x, y, 1.55), 0.17, 0.55, (0.94, 0.92, 0.86), sides=6, top=0.13)
    else:
        b.cylinder((x, y, 1.55), 0.21, 0.32, STEEL, sides=6, top=0.0)
    b.box((x + 0.32, y + 0.05, 1.25), (0.06, 0.06, 2.5), WOOD)
    b.cylinder((x + 0.32, y + 0.05, 2.5), 0.07, 0.25, STEEL, sides=4, top=0.0)
    b.cylinder((x - 0.33, y + 0.05, 0.62), 0.33 if eastern else 0.30, 0.06, accent, sides=10, axis=(0.0, 90.0))
    b.cylinder((x - 0.37, y + 0.05, 0.84), 0.09, 0.06, STEEL, sides=6, axis=(0.0, 90.0))


def _rider(b, color, accent, horse=(0.88, 0.85, 0.78), eastern=False):
    """The general on his horse, lance raised, cloak in the realm's colours."""
    # the horse
    b.box((0, 0.2, 1.35), (0.85, 2.1, 0.85), horse)
    for dx in (-0.28, 0.28):
        for dy in (-0.55, 0.95):
            b.box((dx, dy, 0.48), (0.2, 0.22, 0.98), horse)
            b.box((dx, dy, 0.06), (0.22, 0.26, 0.12), DARK)
    b.box((0, 1.35, 2.0), (0.38, 0.5, 1.0), horse, pitch=-32)
    b.box((0, 1.78, 2.38), (0.34, 0.85, 0.38), horse, pitch=18)
    b.box((0, -0.95, 1.25), (0.14, 0.16, 0.85), DARK, pitch=28)
    b.box((0, 1.30, 2.30), (0.1, 0.7, 0.35), DARK, pitch=-32)  # mane
    # caparison and saddle in the realm's colours
    b.box((0, 0.15, 1.62), (1.02, 1.5, 0.5), color)
    b.box((0, 0.15, 1.90), (1.05, 0.7, 0.14), accent)
    # the rider
    for dx in (-0.38, 0.38):
        b.box((dx, 0.3, 1.75), (0.16, 0.22, 0.75), DARK, pitch=-15)
    b.box((0, 0.15, 2.45), (0.58, 0.42, 0.85), color)
    b.box((0, -0.15, 2.35), (0.62, 0.14, 1.0), accent, pitch=8)  # cloak
    b.box((0, 0.15, 3.05), (0.34, 0.34, 0.34), SKIN)
    if eastern:
        b.cylinder((0, 0.15, 3.18), 0.24, 0.32, (0.95, 0.94, 0.9), sides=8, top=0.18)  # turban
        b.cylinder((0, 0.15, 3.48), 0.07, 0.18, color, sides=5, top=0.0)
    else:
        b.cylinder((0, 0.15, 3.18), 0.22, 0.42, STEEL, sides=8, top=0.0)
    # the lance with its pennon
    b.box((0.42, 0.55, 3.0), (0.07, 0.07, 3.6), WOOD, pitch=12)
    b.quad((0.42, 0.95, 4.65), (0.42, 1.65, 4.55), (0.42, 1.45, 4.35), (0.42, 0.9, 4.35), accent, double=True)


def _base(b, radius=3.6):
    b.cylinder((0, 0, 0), radius, 0.32, BASE, sides=20)
    b.cylinder((0, 0, 0.32), radius * 0.96, 0.03, (0.34, 0.36, 0.22), sides=20)
    rng = np.random.default_rng(3)
    for _ in range(9):  # tufts of grass painted on the base
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(1.0, radius * 0.85)
        b.cylinder((math.cos(a) * r, math.sin(a) * r, 0.33), 0.18, 0.22, (0.40, 0.46, 0.22), sides=5, top=0.0)


def miniature(color, accent, eastern=False):
    """(body, ink outline of the body, banner): an army's miniature in a realm's colours, facing +y."""
    b = Builder()
    _base(b)
    _rider(b, color, accent, eastern=eastern)
    for x, y in ((-2.0, -1.0), (2.0, -1.0), (-1.3, -2.4), (1.3, -2.4), (0.0, -2.0)):
        _soldier(b, x, y, color, accent, eastern=eastern)
    # the banner bearer's pole
    b.box((-2.0, 1.3, 2.4), (0.08, 0.08, 4.8), WOOD)
    b.cylinder((-2.0, 1.3, 4.8), 0.1, 0.25, (0.85, 0.7, 0.3), sides=6, top=0.0)
    body, outline = b.node("miniature"), b.node("miniature-ink", smooth=True)
    flag = Builder()
    w, h = 1.9, 1.15  # the cloth hangs from the pole at x = 0 (the node is placed at the pole's top)
    flag.quad((0, 0, 0), (0, 0, -h), (0, w, -h), (0, w, 0), color, double=True)
    flag.quad((0.01, 0.0, -h * 0.4), (0.01, 0.0, -h * 0.6), (0.01, w, -h * 0.6), (0.01, w, -h * 0.4), accent,
              double=True)
    flag.quad((-0.01, 0.0, -h * 0.4), (-0.01, w, -h * 0.4), (-0.01, w, -h * 0.6), (-0.01, 0.0, -h * 0.6), accent,
              double=True)
    return body, outline, flag.node("banner")


_shaders = {}


def _shader(kind):
    if kind not in _shaders:
        _shaders[kind] = Shader.load(Shader.SL_GLSL, str(SHADERS / f"{kind}.vert"), str(SHADERS / "figure.frag"))
    return _shaders[kind]


class ArmyFigure:
    """One army on the map: its miniature, where it stands, and the path it is marching along."""

    SCALE = 2.3   # like every campaign map, the armies are drawn far larger than life
    SPEED = 26.0  # world units a second while marching

    def __init__(self, parent, height_at, color, accent, sun, eastern=False):
        self.height_at = height_at
        self.root = parent.attachNewNode("army")
        body, outline, banner = miniature(color, accent, eastern)
        self.body = self.root.attachNewNode(body)
        self.banner = self.body.attachNewNode(banner)
        self.banner.setPos(-2.0, 1.3, 4.75)
        # ink outline: the body again, swollen along its smoothed normals, showing only its back faces
        self.root.setShader(_shader("figure"))
        self.root.setShaderInputs(sun_dir=sun, outline=0.0)
        ink = self.body.attachNewNode(outline)
        ink.setShader(_shader("figure_outline"), 1)
        ink.setShaderInput("outline", 0.07)
        ink.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)
        self.root.setScale(self.SCALE)
        self.path = []
        self.walked = 0.0
        self.pos = Vec3(0, 0, 0)
        self.heading = 0.0

    def place(self, x, y, heading=None):
        self.pos = Vec3(x, y, self.height_at(x, y))
        if heading is not None:
            self.heading = heading
        self.root.setPos(self.pos)
        self.root.setH(self.heading)

    def march(self, points):
        """Walk along these world (x, y) points."""
        self.path = [Vec3(x, y, 0) for x, y in points]
        self.walked = 0.0

    @property
    def marching(self):
        return len(self.path) > 0

    def update(self, dt, time):
        if self.path:
            target = self.path[0]
            step = Vec3(target.x - self.pos.x, target.y - self.pos.y, 0)
            dist = step.length()
            move = self.SPEED * dt
            if dist <= move:
                self.pos = Vec3(target.x, target.y, 0)
                self.path.pop(0)
            else:
                step.normalize()
                self.pos += step * move
                want = -math.degrees(math.atan2(step.x, step.y))
                turn = (want - self.heading + 180) % 360 - 180
                self.heading += turn * min(1.0, dt * 6)
            self.walked += move
            bob = abs(math.sin(self.walked * 0.6)) * 0.9
            sway = math.sin(self.walked * 0.3) * 3.0
        else:
            bob, sway = 0.0, 0.0
        z = self.height_at(self.pos.x, self.pos.y)
        self.root.setPos(self.pos.x, self.pos.y, z + bob)
        self.root.setHpr(self.heading, 0, sway)
        self.banner.setH(math.sin(time * 2.3 + self.pos.x) * 14 + 8)
