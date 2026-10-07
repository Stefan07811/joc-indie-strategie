"""The chosen army's orders drawn on the map: how far it can march this month (a field the land shader
rules in red ink) and the route it was ordered along (a ribbon of chevrons, then dots for the months
after)."""

import math

import numpy as np
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, Shader,
                          TransparencyAttrib)

from .. import geo
from ..game.navigation import CELL
from .world import SHADERS

RUBRIC = (0.68, 0.15, 0.09)
SEPIA = (0.30, 0.20, 0.12)
SPACING = 0.8   # world units between the ribbon's vertices
LIFT = 0.6      # world units above the ground


def reach_field(reach):
    """A Reach as the land shader wants it: km / budget (1.5 beyond the march), its cells at sea filled
    from the nearest land so the red bound follows the march, not the shore. Returns (field, rect in
    map pixels)."""
    field = np.minimum(reach.dist / max(reach.budget, 1e-6), 1.5).astype(np.float32)
    # close the little holes a river cell or a crag leaves inside the march (a min then a max filter)
    closed = field
    for pick in (np.minimum, np.maximum):
        out = closed.copy()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                out = pick(out, np.roll(np.roll(closed, dr, 0), dc, 1))
        closed = out
    field = np.minimum(field, closed)
    sea = ~reach.passable
    for _ in range(6):
        grown = field.copy()
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            grown = np.minimum(grown, np.roll(field, shift, axis=axis))
        field = np.where(sea, np.minimum(field, grown + 0.02), field)
    return field, reach.rect


def months_of(route, moves, march_km, most=6):
    """The route cut into months of marching: [[(x, y), ...], ...], this month's first (which may be
    empty if the army has no movement left)."""
    parts = []
    left, budget = route, moves
    while left is not None and len(parts) < most:
        if budget <= 0:
            parts.append([])
        else:
            walked, left, _ = left.advance(budget)
            parts.append(walked)
        budget = march_km
    return parts


class RouteRibbon:
    """The ribbon showing one army's route; rebuilt whenever the orders change."""

    def __init__(self, parent, height_at):
        self.height_at = height_at
        self.root = parent.attachNewNode("route")
        self.root.setShader(Shader.load(Shader.SL_GLSL, str(SHADERS / "route.vert"), str(SHADERS / "route.frag")))
        self.root.setShaderInputs(width=1.0, time=0.0)
        self.root.setTransparency(TransparencyAttrib.M_alpha)
        self.root.setDepthWrite(False)
        self.root.setBin("fixed", 20)
        self.root.setLightOff()
        self.node = None

    def ground(self, x, y):
        """The ground's world height around world (x, y): the highest of the nearby samples, so the
        ribbon never dips under the coarser terrain mesh."""
        return max(self.height_at(x + dx, y + dy) for dx in (-1.5, 0, 1.5) for dy in (-1.5, 0, 1.5)) + LIFT

    def show(self, months):
        """Draw a route cut into months (see months_of), in map pixels."""
        self.hide()
        fmt = GeomVertexFormat.getV3n3c4t2()
        data = GeomVertexData("route", fmt, Geom.UH_static)
        vw, nw, cw, tw = (GeomVertexWriter(data, c) for c in ("vertex", "normal", "color", "texcoord"))
        tris = GeomTriangles(Geom.UH_static)
        count = 0
        along = 0.0
        for month, points in enumerate(months):
            if len(points) < 2:
                continue
            color = (*RUBRIC, 1.0) if month == 0 else (*SEPIA, max(0.35, 0.7 - 0.08 * month))
            pts = _resample([(x, geo.HEIGHT - y) for x, y in points], SPACING)
            for i, (x, y) in enumerate(pts):
                ax, ay = pts[max(0, i - 1)]
                bx, by = pts[min(len(pts) - 1, i + 1)]
                dx, dy = bx - ax, by - ay
                n = math.hypot(dx, dy) or 1.0
                px, py = -dy / n, dx / n
                if i:
                    along += math.hypot(x - pts[i - 1][0], y - pts[i - 1][1])
                z = self.ground(x, y)
                for side in (-1.0, 1.0):
                    vw.addData3(x, y, z)
                    nw.addData3(px, py, 0)
                    cw.addData4(*color)
                    tw.addData2(along, side)
                if i:
                    a = count + 2 * (i - 1)
                    tris.addVertices(a, a + 1, a + 3)
                    tris.addVertices(a, a + 3, a + 2)
            count += 2 * len(pts)
        if count == 0:
            return
        geom = Geom(data)
        geom.addPrimitive(tris)
        node = GeomNode("route")
        node.addGeom(geom)
        self.node = self.root.attachNewNode(node)
        self.node.setTwoSided(True)

    def hide(self):
        if self.node is not None:
            self.node.removeNode()
            self.node = None

    def update(self, camera_distance, time):
        self.root.setShaderInputs(width=float(np.clip(camera_distance / 260.0, 0.5, 6.0)), time=time)


def _resample(points, spacing):
    """Points every `spacing` world units along a polyline."""
    out = [points[0]]
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, int(length / spacing))
        out += [(ax + (bx - ax) * k / steps, ay + (by - ay) * k / steps) for k in range(1, steps + 1)]
    return out
