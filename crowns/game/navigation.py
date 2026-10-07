"""Where armies can march, and how far in a month: Total War style free movement over the real land.

The land is a grid of cells (CELL map pixels each, 3 km). Every cell costs movement to cross:
plains little, forests and hills more, mountains and marshes a lot; the sea cannot be crossed on
foot, and the big rivers only slowly, except at their fords and bridges. An army spends its monthly
movement budget along the cheapest path, and the player sees beforehand how far it can reach.
"""

import heapq
import math
from functools import cached_property

import numpy as np
from PIL import Image, ImageDraw

from .. import geo

CELL = 2                         # map pixels per navigation cell
CELL_KM = CELL * geo.KM_PER_PX   # 3 km
TERRAIN_COST = {"plains": 1.0, "steppe": 0.9, "hills": 1.5, "forest": 1.7, "mountains": 2.6, "marsh": 2.5,
                "desert": 1.3}
# The great rivers can only be crossed slowly away from a ford or a bridge: boats must be gathered and
# the army ferried over, a week and more. The lesser rivers cost a day or two.
GREAT_RIVERS = {"Danube", "Donau", "Bratul Chillia", "Bratul Sfintu Gheorghe", "Bratul Sulina", "Borcea",
                "Dnipro", "Volga", "Don", "Euphrates", "Firat", "Al Furat", "Tigris", "Dicle", "Dniester",
                "Tisa", "Sava", "Drau", "Vistula", "Oder", "Elbe", "Po"}
GREAT_RIVER_COST = 25.0
RIVER_COST = 5.0
RIVER_RANK = 8                   # Natural Earth scale ranks of the lesser rivers that slow a march
STRAIT_COST = 4.0                # ferrying over a narrow strait at its crossing
SQRT2 = math.sqrt(2.0)
STEPS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
         (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2)]
# The fords, ferries and bridges of the big rivers in 1402 (lon, lat): the old crossing places.
CROSSINGS = [
    (22.88, 43.99), (24.87, 43.72), (25.35, 43.62), (25.96, 43.88), (27.26, 44.11), (28.10, 45.10), (28.85, 45.30),  # Danube, lower
    (20.46, 44.82), (21.20, 44.68), (22.42, 44.70), (18.93, 47.79), (19.04, 47.50), (18.89, 46.14),    # Danube, upper
    (17.60, 47.70), (16.37, 48.21), (19.45, 45.25),
    (18.69, 45.55), (17.20, 45.20), (16.00, 45.47), (19.27, 44.95),                                    # Drava, Sava
    (20.15, 46.25), (20.38, 46.93), (21.40, 47.90),                                                    # Tisza
    (27.85, 47.95), (28.30, 48.16), (29.62, 46.83), (30.35, 46.19),                                    # Dniester
    (30.52, 50.45), (33.40, 47.80), (34.60, 47.00), (31.70, 49.40),                                    # Dnieper
    (26.85, 46.55), (27.45, 46.00), (27.15, 47.30), (28.14, 46.90), (28.20, 45.92),                    # Siret, Prut
    (22.90, 45.88), (21.31, 46.18), (24.37, 44.42), (24.55, 45.10), (23.80, 44.32),                    # Mureș, Olt, Jiu
    (26.67, 40.41), (29.00, 41.02), (36.47, 45.35), (39.42, 47.10), (41.0, 47.3),                      # straits, Don
    (41.10, 37.87), (38.00, 36.60), (39.00, 35.95), (34.85, 40.95), (31.80, 40.60),                    # Tigris, Euphrates, Kızılırmak, Sakarya
]
CROSSING_RADIUS_KM = 9.0


class Navigation:
    """The movement-cost grid and the searches over it."""

    def __init__(self, ground, provmap):
        self.ground = ground
        self.provmap = provmap

    @cached_property
    def cost(self):
        """Movement cost of every cell (km of plain marching per km crossed); inf at sea."""
        labels = self.provmap.labels[::CELL, ::CELL]
        shape = labels.shape
        terrain_cost = np.ones(max(self.provmap.by_index) + 1, np.float32)
        for p in self.provmap.provinces.values():
            terrain_cost[p.index] = TERRAIN_COST.get(p.terrain, 1.0)
        h = self.ground.height[::CELL, ::CELL]
        gy, gx = np.gradient(h)
        slope = np.hypot(gx, gy) / (CELL_KM * 1000)
        cost = terrain_cost[labels] * (1 + 4 * np.clip(slope - 0.03, 0, 0.25))
        fords = np.zeros(shape, bool)
        rr, cc = np.mgrid[0:shape[0], 0:shape[1]]
        radius = CROSSING_RADIUS_KM / CELL_KM
        for lon, lat in CROSSINGS:
            x, y = geo.to_map(lon, lat)
            fords |= (rr - y / CELL) ** 2 + (cc - x / CELL) ** 2 <= radius ** 2
        for great, factor in ((False, RIVER_COST), (True, GREAT_RIVER_COST)):
            mask = Image.new("L", (shape[1], shape[0]), 0)
            draw = ImageDraw.Draw(mask)
            for r in self.ground.rivers:
                if (r["name"] in GREAT_RIVERS) == great and (great or r["rank"] <= RIVER_RANK):
                    draw.line([(x / CELL, y / CELL) for x, y in r["points"]], fill=255, width=1)
            river = (np.asarray(mask) > 0) & ~fords
            cost = np.where(river, cost * factor, cost)
        land = self.ground.land[::CELL, ::CELL]
        # the narrow straits with a crossing (the Bosporus, the Dardanelles, Kerch) are ferried over
        cost = np.where(land, cost, np.where(fords, STRAIT_COST, np.inf))
        return cost.astype(np.float32)

    @cached_property
    def steps(self):
        """For each of the STEPS (dr, dc): the km of budget it takes to step into every cell from its
        neighbour at (-dr, -dc). A diagonal step pays for the two cells it cuts between as well, so it
        cannot slip across a river drawn diagonally or squeeze past a corner of the sea."""
        c = self.cost
        h, w = c.shape
        pad = np.pad(c, 1, constant_values=np.inf)

        def at(dr, dc):
            return pad[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]

        out = []
        for dr, dc, length in STEPS:
            if dr and dc:
                mean = (c + at(-dr, -dc) + at(-dr, 0) + at(0, -dc)) / 4
            else:
                mean = (c + at(-dr, -dc)) / 2
            out.append((mean * (length * CELL_KM)).astype(np.float32))
        return out

    def cell(self, x, y):
        """The grid cell (row, col) of map pixel (x, y)."""
        return int(np.clip(y / CELL, 0, self.cost.shape[0] - 1)), int(np.clip(x / CELL, 0, self.cost.shape[1] - 1))

    def reach(self, x, y, budget_km):
        """How far an army at map pixel (x, y) can march with budget_km of movement.

        Returns a Reach: the km of budget spent to get to every cell of a window around the army
        (inf where it cannot go this month)."""
        cost = self.cost
        r0, c0 = self.cell(x, y)
        radius = int(budget_km / (CELL_KM * 0.9)) + 2
        top, left = max(0, r0 - radius), max(0, c0 - radius)
        bottom, right = min(cost.shape[0], r0 + radius + 1), min(cost.shape[1], c0 + radius + 1)
        h, w = bottom - top, right - left
        steps = [s[top:bottom, left:right] for s in self.steps]
        pad = np.full((h + 2, w + 2), np.inf, np.float32)
        pad[1 + r0 - top, 1 + c0 - left] = 0.0
        dist = pad[1:-1, 1:-1]
        for _ in range(4 * radius + 10):
            changed = False
            for (dr, dc, _), step in zip(STEPS, steps):
                cand = pad[1 - dr:1 - dr + h, 1 - dc:1 - dc + w] + step
                better = cand < dist
                if better.any():
                    np.minimum(dist, cand, out=dist)
                    changed = True
            if not changed:
                break
        dist = dist.copy()
        dist[dist > budget_km] = np.inf
        return Reach(dist, top, left, budget_km)

    def path(self, x0, y0, x1, y1, max_km=None):
        """The cheapest march from map pixel (x0, y0) to (x1, y1): [(x, y), ...] in map pixels, and its
        cost in km, or (None, inf) if the target cannot be reached (A* over the grid)."""
        cost = self.cost
        steps = self.steps
        rows, cols = cost.shape
        start, goal = self.cell(x0, y0), self.cell(x1, y1)
        if not np.isfinite(cost[goal]):
            return None, math.inf
        frontier = [(0.0, start)]
        best = {start: 0.0}
        came = {}
        floor = float(np.min(cost)) * CELL_KM
        done = set()
        while frontier:
            _, node = heapq.heappop(frontier)
            if node == goal:
                break
            if node in done:
                continue
            done.add(node)
            g = best[node]
            if max_km is not None and g > max_km:
                continue
            r, c = node
            for k, (dr, dc, _) in enumerate(STEPS):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                ng = g + float(steps[k][nr, nc])
                if ng < best.get((nr, nc), math.inf):
                    best[(nr, nc)] = ng
                    came[(nr, nc)] = node
                    est = math.hypot(goal[0] - nr, goal[1] - nc) * floor
                    heapq.heappush(frontier, (ng + est, (nr, nc)))
        if goal not in best:
            return None, math.inf
        cells = [goal]
        while cells[-1] != start:
            cells.append(came[cells[-1]])
        cells.reverse()
        points = [((c + 0.5) * CELL, (r + 0.5) * CELL) for r, c in cells]
        points[0], points[-1] = (x0, y0), (x1, y1)
        return _simplify(points), best[goal]


class Reach:
    """The cells an army can reach this month, and what each costs (a window of the grid)."""

    def __init__(self, dist, top, left, budget):
        self.dist, self.top, self.left, self.budget = dist, top, left, budget

    def cost_to(self, x, y):
        r, c = int(y / CELL) - self.top, int(x / CELL) - self.left
        if 0 <= r < self.dist.shape[0] and 0 <= c < self.dist.shape[1]:
            return float(self.dist[r, c])
        return math.inf

    def can_reach(self, x, y):
        return math.isfinite(self.cost_to(x, y))

    @property
    def rect(self):
        """(x, y, width, height) of the window in map pixels."""
        h, w = self.dist.shape
        return self.left * CELL, self.top * CELL, w * CELL, h * CELL


def _simplify(points, tolerance=1.2):
    """Fewer points along straight stretches (Ramer-Douglas-Peucker), so marches look like strides."""
    if len(points) < 3:
        return points
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1e-9
    far, index = 0.0, 0
    for i, (x, y) in enumerate(points[1:-1], start=1):
        d = abs(dy * (x - x0) - dx * (y - y0)) / length
        if d > far:
            far, index = d, i
    if far <= tolerance:
        return [points[0], points[-1]]
    return _simplify(points[:index + 1], tolerance)[:-1] + _simplify(points[index:], tolerance)
