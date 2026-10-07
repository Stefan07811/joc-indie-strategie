"""A tactical battle on screen: the field painted like the map, its woods and its stream, and every
regiment a block of painted miniatures on a tray, like a wargame on a table, under its realm's banner.
Volleys of arrows arc over the field; broken regiments turn and run."""

import math

import numpy as np
from panda3d.core import (CullFaceAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, LineSegs, Shader, TransparencyAttrib, Vec3)

from ..game.battle import DEPLOY_DEPTH, FIELD_H, FIELD_W, Field
from .atmosphere import FOG, HAZE, SHADOW_CASTERS, Sky, Sun
from .figures import SHADERS, Builder, _rider, _soldier, geom_node

UNIT = 0.1          # world units per metre
LIFT = 1.5          # relief exaggeration on the field
FIGURE = 0.9        # the miniatures' size on the field
COUNTRY = 45        # cells of country drawn around the field, beyond where the regiments may go
GRASS = {"plains": (0.56, 0.62, 0.33), "steppe": (0.72, 0.68, 0.42), "hills": (0.50, 0.58, 0.31),
         "mountains": (0.56, 0.54, 0.45), "forest": (0.42, 0.52, 0.29), "marsh": (0.43, 0.53, 0.40),
         "desert": (0.80, 0.71, 0.50)}
WOOD_FLOOR = (0.33, 0.42, 0.24)
WATER = (0.42, 0.58, 0.64)
CANOPY = (0.24, 0.38, 0.20)
TRUNK = (0.40, 0.29, 0.18)


def world(x, y):
    return x * UNIT, y * UNIT


_shaders = {}


def _piece(outline=False):
    """The shader of the painted pieces on the field (or of their ink outlines)."""
    key = "piece_outline" if outline else "piece"
    if key not in _shaders:
        _shaders[key] = Shader.load(Shader.SL_GLSL, str(SHADERS / f"{key}.vert"), str(SHADERS / "piece.frag"))
    return _shaders[key]


def _flat(node):
    """Lines drawn over the field: no shader, no light, no shadow."""
    node.setShaderOff(1)
    node.setLightOff(1)
    node.hide(SHADOW_CASTERS)
    return node


class BattleScene:
    """Draws a Battle and keeps the drawing in step with it."""

    def __init__(self, parent, battle, colors, accents, eastern, sun, camera=None, shadow_size=4096):
        """colors, accents, eastern: per side (0 = attacker, 1 = defender). With a camera, the field gets
        its sky; the sun always throws shadows."""
        self.battle = battle
        self.root = parent.attachNewNode("battle")
        self.sun = sun
        self.colors, self.accents, self.eastern = colors, accents, eastern
        self.field = battle.field
        self.root.setShaderInputs(sun_dir=sun, outline=0.0, haze=Vec3(*HAZE), fog=FOG)
        self.light = Sun(parent, sun, size=shadow_size)
        self.root.setLight(self.light.root)
        self.sky = Sky(camera, parent, sun) if camera is not None else None
        self._build_ground()
        self._build_far_country()
        self._build_woods()
        self._build_river()
        self.gate = None
        if battle.siege is not None:
            self._build_walls()
        self.units = {}
        self.models = {}
        self.selected = set()
        self.viewer = 0                   # whose eyes we see with: the enemy hidden in woods is not drawn
        self.arcs = []
        for u in battle.units:
            self._build_unit(u)
        self.orders = self.root.attachNewNode("orders")

    # --- the ground ----------------------------------------------------------------------------------

    def height(self, x, y):
        """World height at world (x, y)."""
        return self.field.h(x / UNIT, y / UNIT) * UNIT * LIFT

    def _build_ground(self):
        f = self.field
        field_h = f.height * UNIT * LIFT
        # the country around the field, flattening out towards the horizon
        h = np.pad(field_h, COUNTRY, mode="edge")
        rows, cols = h.shape
        ys, xs = np.mgrid[0:rows, 0:cols]
        out = np.maximum(np.maximum(COUNTRY - xs, xs - (cols - 1 - COUNTRY)),
                         np.maximum(COUNTRY - ys, ys - (rows - 1 - COUNTRY)))
        fade = np.clip(out / COUNTRY, 0.0, 1.0)
        h = h * (1 - fade) + field_h.mean() * fade
        X, Y = (xs - COUNTRY) * Field.CELL * UNIT, (ys - COUNTRY) * Field.CELL * UNIT
        gy, gx = np.gradient(h, Field.CELL * UNIT)
        normals = np.dstack([-gx, -gy, np.ones_like(h)])
        normals /= np.linalg.norm(normals, axis=2, keepdims=True)
        base = np.array(GRASS.get(f.terrain, GRASS["plains"]))
        rng = np.random.default_rng(1)
        tint = base[None, None, :] * (0.92 + 0.16 * rng.random((rows, cols, 1)))
        woods = np.pad(f.woods, COUNTRY, mode="constant", constant_values=False)
        tint = np.where(woods[..., None], np.array(WOOD_FLOOR), tint)
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData("field", fmt, Geom.UH_static)
        data.setNumRows(rows * cols)
        vw, nw, cw = GeomVertexWriter(data, "vertex"), GeomVertexWriter(data, "normal"), GeomVertexWriter(data, "color")
        for r in range(rows):
            for c in range(cols):
                vw.addData3(X[r, c], Y[r, c], h[r, c])
                nw.addData3(*normals[r, c])
                cw.addData4(*tint[r, c], 1.0)
        tris = GeomTriangles(Geom.UH_static)
        for r in range(rows - 1):
            for c in range(cols - 1):
                a = r * cols + c
                tris.addVertices(a, a + 1, a + cols + 1)
                tris.addVertices(a, a + cols + 1, a + cols)
        geom = Geom(data)
        geom.addPrimitive(tris)
        node = GeomNode("field")
        node.addGeom(geom)
        self.ground = self.root.attachNewNode(node)
        self.ground.setShader(Shader.load(Shader.SL_GLSL, str(SHADERS / "field.vert"), str(SHADERS / "field.frag")))
        dy = DEPLOY_DEPTH * UNIT
        # these sit on the battle's root, so that the far country beyond is painted the same way
        self.root.setShaderInputs(deploying=1.0, deploy=(0, dy, FIELD_H * UNIT - dy, FIELD_H * UNIT),
                                  field_size=(FIELD_W * UNIT, FIELD_H * UNIT),
                                  our_color=Vec3(*self.colors[0]), their_color=Vec3(*self.colors[1]))

    def _build_far_country(self):
        """Flat land from the edge of the drawn country out to the horizon, lost in the haze."""
        x0, y0 = -COUNTRY * Field.CELL * UNIT, -COUNTRY * Field.CELL * UNIT
        x1, y1 = FIELD_W * UNIT - x0, FIELD_H * UNIT - y0
        far = 4000.0
        z = float(self.field.height.mean()) * UNIT * LIFT - 0.05
        color = tuple(np.array(GRASS.get(self.field.terrain, GRASS["plains"])) * 0.97)
        b = Builder()
        for (ax, ay, bx, by) in ((-far, -far, far, y0), (-far, y1, far, far), (-far, y0, x0, y1), (x1, y0, far, y1)):
            b.quad((ax, ay, z), (bx, ay, z), (bx, by, z), (ax, by, z), color)
        far_np = self.root.attachNewNode(b.node("far-country"))
        far_np.setShader(self.ground.getShader())
        far_np.hide(SHADOW_CASTERS)

    def _build_woods(self):
        f = self.field
        b = Builder()
        rng = np.random.default_rng(2)
        rows, cols = f.woods.shape
        for r in range(0, rows, 2):
            for c in range(0, cols, 2):
                if not f.woods[r, c]:
                    continue
                x = (c + rng.uniform(-0.6, 0.6)) * Field.CELL * UNIT
                y = (r + rng.uniform(-0.6, 0.6)) * Field.CELL * UNIT
                z = self.height(x, y)
                s = rng.uniform(0.8, 1.3)
                b.cylinder((x, y, z), 0.12 * s, 0.6 * s, TRUNK, sides=5)
                b.cylinder((x, y, z + 0.5 * s), 0.75 * s, 1.6 * s, CANOPY, sides=6, top=0.0)
        if not b.tris:
            return
        verts, colors = b.arrays()
        trees = self.root.attachNewNode("woods")
        trees.setShader(_piece())
        trees.attachNewNode(geom_node("trees", verts, colors))
        ink = trees.attachNewNode(geom_node("trees-ink", verts, colors, smooth=True))
        ink.setShader(_piece(outline=True), 1)
        ink.setShaderInput("outline", 0.05)
        ink.hide(SHADOW_CASTERS)
        ink.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)

    def _build_river(self):
        river = self.field.river
        if not river:
            return
        b = Builder()
        pts = [(x * UNIT, y * UNIT) for x, y in river]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            n = math.hypot(dx, dy) or 1
            px, py = -dy / n * 2.0, dx / n * 2.0
            za, zb = self.height(ax, ay) + 0.15, self.height(bx, by) + 0.15
            b.quad((ax - px, ay - py, za), (bx - px, by - py, zb), (bx + px, by + py, zb), (ax + px, ay + py, za), WATER)
        for fx, fy in self.field.fords:       # the fords: pale gravel where the stream runs shallow
            x, y = fx * UNIT, fy * UNIT
            z = self.height(x, y) + 0.2
            ring = [(x + math.cos(a) * 4.5, y + math.sin(a) * 3.0, z) for a in np.linspace(0, 2 * math.pi, 13)]
            for a, c in zip(ring, ring[1:]):
                b.tri((x, y, z), a, c, (0.70, 0.66, 0.52))
        node = self.root.attachNewNode(b.node("stream"))
        node.setShader(_piece())
        node.hide(SHADOW_CASTERS)

    def _build_walls(self):
        """The town being stormed: its curtain wall and towers across the field, the gate, the breaches the
        siege has made, and the houses, church and square behind."""
        from ..game.siege import BREACH_HALF, GATE_HALF
        from . import models as m
        w = self.battle.siege
        y = w.y * UNIT
        height, thick = 4.5 + 0.6 * w.fort, 2.4
        stone = (0.74, 0.70, 0.62)
        part = m.Part()

        def place(build, x, yy, z=None):
            piece = m.Part()
            build(piece)
            z = self.height(x, yy) if z is None else z
            part.add(piece, at=(x, yy, z))
        gaps = sorted([(w.gate_x - GATE_HALF, w.gate_x + GATE_HALF)] +
                      [(b - BREACH_HALF, b + BREACH_HALF) for b in w.breaches])
        x = 0.0
        for a, b in gaps + [(FIELD_W, FIELD_W)]:
            a, b = a * UNIT, b * UNIT
            n = max(1, int((a - x) / 6))
            for k in range(n):               # the curtain, in short lengths that follow the ground
                a0, a1 = x + (a - x) * k / n, x + (a - x) * (k + 1) / n
                if a1 - a0 > 0.1:
                    place(lambda pc, a0=a0, a1=a1: m.wall(pc, (0, 0), (a1 - a0, 0), height, thick, stone),
                          a0, y, min(self.height(a0, y), self.height(a1, y)))
            x = max(x, b)
        for tx in w.towers + [w.gate_x - GATE_HALF - 30, w.gate_x + GATE_HALF + 30]:
            place(lambda pc: m.square_tower(pc, 0, 0, 5.0, height + 3.0, stone,
                                            roof=m.TILE if w.fort >= 2 else None), tx * UNIT, y)
        rng = np.random.default_rng(5)
        for bx in w.breaches:               # rubble where the wall came down
            for k in range(8):
                place(lambda pc, k=k: pc.box((0, 0, 0.4), (1.5, 1.2, 0.9), (0.64, 0.60, 0.53), yaw=k * 23),
                      bx * UNIT + rng.uniform(-2.4, 2.4), y + rng.uniform(-1.5, 1.5))
        # the town behind: houses about a church and its square
        px, py = w.plaza[0] * UNIT, w.plaza[1] * UNIT
        for k in range(30):
            hx = rng.uniform(15, FIELD_W * UNIT - 15)
            hy = rng.uniform(y + 9, FIELD_H * UNIT - 4)
            if math.hypot(hx - px, hy - py) < 16 or abs(hx - w.gate_x * UNIT) < 8:
                continue
            walls_c = m.PLASTER if k % 3 else m.TIMBER
            place(lambda pc, walls_c=walls_c, yaw=rng.uniform(-20, 20):
                  m.gabled(pc, 0, 0, 3.2, 4.4, 2.6, walls_c, m.TILE, yaw=yaw), hx, hy)
        place(lambda pc: m.orthodox_church(pc, 0, 0, big=0.5), px + 15, py + 6)
        verts, colors = part.arrays()
        town = self.root.attachNewNode("town")
        town.setShader(_piece())
        town.attachNewNode(geom_node("walls", verts, colors))
        ink = town.attachNewNode(geom_node("walls-ink", verts, colors, smooth=True))
        ink.setShader(_piece(outline=True), 1)
        ink.setShaderInput("outline", 0.06)
        ink.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)
        ink.hide(SHADOW_CASTERS)
        # the gate's doors, and the banner over the square
        gate = m.Part()
        gate.box((0, 0, height * 0.4), (GATE_HALF * 2 * UNIT, 0.5, height * 0.8), (0.42, 0.29, 0.17))
        for k in range(-2, 3):
            gate.box((k * 0.8, -0.3, height * 0.4), (0.12, 0.1, height * 0.8), (0.25, 0.25, 0.27))
        self.gate = town.attachNewNode(gate.node("gate"))
        self.gate.setPos(w.gate_x * UNIT, y, self.height(w.gate_x * UNIT, y))
        flag = m.Part()
        flag.limb((0, 0, 0), (0, 0, 9), 0.15, 0.12, (0.45, 0.32, 0.2))
        cloth = m.Part()
        cloth.slab([(0, 0), (3.2, 0), (3.2, -2.0), (0, -2.0)], self.colors[1], 0.05)
        flag.add(cloth, at=(0, 0, 8.8))
        self.plaza_flag = town.attachNewNode(flag.node("plaza"))
        self.plaza_flag.setPos(px, py, self.height(px, py))

    # --- the regiments ---------------------------------------------------------------------------------

    def _figure_model(self, kind, side):
        key = (kind, side)
        if key not in self.models:
            b = Builder()
            if kind == "horse":
                _rider(b, self.colors[side], self.accents[side], eastern=self.eastern[side])
            else:
                _soldier(b, 0, 0, self.colors[side], self.accents[side], eastern=self.eastern[side])
            verts, colors = b.arrays()
            self.models[key] = (geom_node("figure", verts, colors), geom_node("figure-ink", verts, colors, True))
        return self.models[key]

    def _build_unit(self, u):
        node = self.root.attachNewNode(f"unit{u.id}")
        node.setShader(_piece())
        w, d = u.frontage * UNIT, u.depth * UNIT
        tray = Builder()
        tray.box((0, 0, 0.05), (w, d, 0.1), (0.30, 0.31, 0.20))
        tray.box((0, d / 2 - 0.08, 0.11), (w, 0.16, 0.02), self.colors[u.side])
        tray_np = node.attachNewNode(tray.node("tray"))
        count = int(np.clip(round(u.start_men / 40), 4, 28))
        ranks = 2 if u.kind == "horse" else 3
        files = max(2, math.ceil(count / ranks))
        body, ink = self._figure_model(u.kind, u.side)
        figures = []
        for k in range(count):
            f, r = k % files, k // files
            fx = (f + 0.5) / files * w - w / 2
            fy = d / 2 - (r + 0.5) / ranks * d
            fig = node.attachNewNode(f"fig{k}")
            fig.setPos(fx, fy, 0.1)
            fig.setScale(FIGURE * (0.6 if u.kind == "horse" else 1.0))
            fig.attachNewNode(body)
            outline = fig.attachNewNode(ink)
            outline.setShader(_piece(outline=True), 1)
            outline.setShaderInput("outline", 0.06)
            outline.hide(SHADOW_CASTERS)
            outline.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)
            figures.append(fig)
        banner = Builder()
        banner.box((0, -d / 2 - 0.2, 1.6), (0.08, 0.08, 3.2), (0.45, 0.32, 0.20))
        banner.quad((0, -d / 2 - 0.2, 3.1), (0, -d / 2 - 0.2, 2.2), (1.4, -d / 2 - 0.2, 2.2), (1.4, -d / 2 - 0.2, 3.1),
                    self.colors[u.side], double=True)
        if u.general:
            banner.cylinder((0, -d / 2 - 0.2, 3.2), 0.18, 0.3, (0.85, 0.7, 0.25), sides=6, top=0.0)
        flag = node.attachNewNode(banner.node("banner"))
        ring = LineSegs()
        ring.setThickness(3)
        ring.setColor(0.95, 0.75, 0.2, 1)
        for a, b2 in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2), (-w / 2, -d / 2)):
            ring.drawTo(a * 1.06, b2 * 1.1, 0.25)
        sel = _flat(node.attachNewNode(ring.create()))
        sel.hide()
        self.units[u.id] = {"node": node, "figures": figures, "tray": tray_np, "flag": flag, "select": sel,
                            "count": count, "bob": 0.0, "last": (u.x, u.y)}
        self._place(u)

    def _place(self, u, t=0.0, dt=0.0):
        view = self.units[u.id]
        x, y = world(u.x, u.y)
        moved = math.hypot(u.x - view["last"][0], u.y - view["last"][1])
        view["last"] = (u.x, u.y)
        view["bob"] += moved * 0.5
        bob = abs(math.sin(view["bob"])) * 0.12 if moved > 0.01 else 0.0
        view["node"].setPos(x, y, self.height(x, y) + bob)
        view["node"].setH(-math.degrees(u.facing))
        show = 0 if not u.alive else max(1, math.ceil(view["count"] * u.men / max(1, u.start_men)))
        for k, fig in enumerate(view["figures"]):
            if k < show:
                fig.show()
            else:
                fig.hide()
        if u.state == "routing":
            view["flag"].hide()
        if u.state in ("gone", "waiting") or not self.battle.visible(u, self.viewer):
            view["node"].hide()          # gone, still on the road, or hidden in a wood
        else:
            view["node"].show()
        view["select"].show() if u.id in self.selected else view["select"].hide()

    # --- every frame -----------------------------------------------------------------------------------

    def update(self, dt, time):
        b = self.battle
        self.ground.setShaderInput("deploying", 0.0 if b.started else 1.0)
        for u in b.units:
            self._place(u, time, dt)
        for event in b.events:
            if event[0] == "volley":
                self._arc(b.units[event[1]], b.units[event[2]])
            elif event[0] == "tower":
                target = b.units[event[3]]
                self._arc_between(event[1], event[2], target.x, target.y, int(event[1]), lift=5.0)
        if self.gate is not None and b.siege.gate_open:
            self.gate.removeNode()
            self.gate = None
        b.events.clear()
        for arc in list(self.arcs):
            arc[1] -= dt
            if arc[1] <= 0:
                arc[0].removeNode()
                self.arcs.remove(arc)
            else:
                arc[0].setAlphaScale(min(1.0, arc[1] * 1.5))
        self._draw_orders()

    def _arc(self, shooter, target):
        """A volley: a sheaf of arrows arcing from the shooters to their mark."""
        self._arc_between(shooter.x, shooter.y, target.x, target.y, shooter.id)

    def _arc_between(self, x0, y0, x1, y1, seed, lift=1.2):
        sx, sy = world(x0, y0)
        tx, ty = world(x1, y1)
        dist = math.hypot(tx - sx, ty - sy)
        lines = LineSegs()
        lines.setThickness(1.5)
        lines.setColor(0.22, 0.14, 0.08, 1)
        rng = np.random.default_rng(int(self.battle.time * 10) + seed)
        for _ in range(5):
            ox, oy = rng.uniform(-1.5, 1.5, 2)
            pts = []
            for k in range(9):
                t = k / 8
                x = sx + ox + (tx - sx) * t
                y = sy + oy + (ty - sy) * t
                z = self.height(x, y) + lift * (1 - t) + 1.2 * t + math.sin(t * math.pi) * dist * 0.18
                pts.append((x, y, z))
            lines.moveTo(*pts[0])
            for p in pts[1:]:
                lines.drawTo(*p)
        node = _flat(self.root.attachNewNode(lines.create()))
        node.setTransparency(TransparencyAttrib.M_alpha)
        self.arcs.append([node, 0.9])

    def _draw_orders(self):
        """For the chosen regiments: an ink line to where they march or whom they attack."""
        self.orders.getChildren().detach()
        if not self.selected:
            return
        lines = LineSegs()
        lines.setThickness(2)
        for uid in self.selected:
            u = self.battle.units[uid]
            if not u.standing or not u.order:
                continue
            if u.order[0] == "move":
                gx, gy = u.order[1], u.order[2]
                lines.setColor(0.95, 0.85, 0.5, 1)
            else:
                t = self.battle.units[u.order[1]]
                gx, gy = t.x, t.y
                lines.setColor(0.75, 0.15, 0.1, 1)
            x0, y0 = world(u.x, u.y)
            x1, y1 = world(gx, gy)
            for k in range(13):
                t = k / 12
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                (lines.moveTo if k == 0 else lines.drawTo)(x, y, self.height(x, y) + 0.6)
        _flat(self.orders.attachNewNode(lines.create()))

    # --- picking -----------------------------------------------------------------------------------------

    def unit_at(self, wx, wy):
        """The regiment under world point (wx, wy)."""
        best, dist = None, 1e9
        for u in self.battle.units:
            if not u.alive or u.state == "waiting" or not self.battle.visible(u, self.viewer):
                continue
            x, y = world(u.x, u.y)
            d = math.hypot(wx - x, wy - y)
            if d < max(u.frontage, u.depth) * UNIT * 0.6 + 1.0 and d < dist:
                best, dist = u, d
        return best

    def follow(self, x, y, distance, dt=0.0):
        """Keep the sun's shadows on what the camera looks at, and let the clouds drift."""
        self.light.follow(x, y, self.height(x, y), min(420.0, max(70.0, distance * 2.6)))
        if self.sky is not None:
            self.sky.update(dt)

    def destroy(self):
        self.root.clearLight()
        self.light.destroy()
        if self.sky is not None:
            self.sky.destroy()
        self.root.removeNode()

