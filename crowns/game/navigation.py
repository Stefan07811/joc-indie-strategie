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
REACH_MARGIN = 1.35              # the reach is measured a little beyond the budget, so its edge is smooth


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

    def land_cell(self, x, y, radius=6):
        """The cell of map pixel (x, y), or the nearest passable cell to it (a town on the shore or in a
        lagoon stands in the water on this grid); None if there is no land near."""
        r, c = self.cell(x, y)
        cost = self.cost
        if np.isfinite(cost[r, c]):
            return r, c
        h, w = cost.shape
        win = cost[max(0, r - radius):r + radius + 1, max(0, c - radius):c + radius + 1]
        rr, cc = np.nonzero(np.isfinite(win))
        if len(rr) == 0:
            return None
        rr, cc = rr + max(0, r - radius), cc + max(0, c - radius)
        i = int(np.argmin((rr - r) ** 2 + (cc - c) ** 2))
        return int(rr[i]), int(cc[i])

    def reach(self, x, y, budget_km):
        """How far an army at map pixel (x, y) can march with budget_km of movement.

        Returns a Reach: the km of budget spent to get to every cell of a window around the army,
        measured a little beyond the budget (inf further, and where it cannot go at all)."""
        cost = self.cost
        r0, c0 = self.land_cell(x, y) or self.cell(x, y)
        limit = budget_km * REACH_MARGIN
        radius = int(limit / (CELL_KM * 0.9)) + 2
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
        dist[dist > limit] = np.inf
        return Reach(dist, top, left, budget_km, np.isfinite(cost[top:bottom, left:right]))

    @cached_property
    def regions(self):
        """A label for every cell: cells with the same label are joined by land (or a ferry); 0 at sea.
        Islands are their own regions, so a march to one is known to be impossible at once."""
        passable = np.isfinite(self.cost)
        labels = np.zeros(passable.shape, np.int32)
        parent = [0]

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        previous = []   # runs of the row above: (start, end, run id)
        runs_of_rows = []
        for r in range(passable.shape[0]):
            row = np.concatenate(([False], passable[r], [False])).astype(np.int8)
            edges = np.flatnonzero(np.diff(row))
            runs = []
            j = 0
            for start, end in zip(edges[::2], edges[1::2] - 1):
                rid = len(parent)
                parent.append(rid)
                while j < len(previous) and previous[j][1] < start:
                    j += 1
                k = j
                while k < len(previous) and previous[k][0] <= end:   # overlaps the run above
                    a, b = find(rid), find(previous[k][2])
                    if a != b:
                        parent[max(a, b)] = min(a, b)
                    k += 1
                runs.append((int(start), int(end), rid))
            runs_of_rows.append(runs)
            previous = runs
        for r, runs in enumerate(runs_of_rows):
            for start, end, rid in runs:
                labels[r, start:end + 1] = find(rid)
        return labels

    def connected(self, x0, y0, x1, y1):
        """Can an army at map pixel (x0, y0) march to (x1, y1) at all?"""
        a, b = self.land_cell(x0, y0), self.cell(x1, y1)
        return a is not None and self.regions[a] != 0 and self.regions[a] == self.regions[b]

    @cached_property
    def _flat_steps(self):
        """The step costs on a grid padded with a border of inf, flattened, for a quick A*: (width,
        [(offset, memoryview of costs) for every step])."""
        h, w = self.cost.shape
        out = []
        for (dr, dc, _), step in zip(STEPS, self.steps):
            padded = np.full((h + 2, w + 2), np.inf, np.float32)
            padded[1:-1, 1:-1] = step
            out.append((dr * (w + 2) + dc, memoryview(padded.ravel())))
        return w + 2, out

    def route(self, x0, y0, x1, y1, max_km=None, greed=1.0):
        """The cheapest march from map pixel (x0, y0) to (x1, y1) as a Route, or None if the target
        cannot be reached (A* over the grid). A greed above 1 finds a good route much sooner, though
        not always the very best (the AI's armies use it)."""
        start, goal = self.land_cell(x0, y0), self.cell(x1, y1)
        if start is None or not np.isfinite(self.cost[goal]) or self.regions[start] != self.regions[goal]:
            return None
        width, steps = self._flat_steps
        s0 = (start[0] + 1) * width + start[1] + 1
        g0 = (goal[0] + 1) * width + goal[1] + 1
        gr, gc = divmod(g0, width)
        floor = float(np.min(self.cost)) * CELL_KM * greed
        diag = SQRT2 - 1.0
        frontier = [(0.0, s0)]
        best = {s0: 0.0}
        came = {}
        done = set()
        push, pop, inf = heapq.heappush, heapq.heappop, math.inf
        limit = inf if max_km is None else max_km
        while frontier:
            _, node = pop(frontier)
            if node == g0:
                break
            if node in done:
                continue
            done.add(node)
            g = best[node]
            if g > limit:
                continue
            for offset, step in steps:
                nxt = node + offset
                ng = g + step[nxt]
                if ng < best.get(nxt, inf):
                    best[nxt] = ng
                    came[nxt] = node
                    r, c = divmod(nxt, width)
                    dy, dx = abs(gr - r), abs(gc - c)
                    est = (dx + dy + (diag - 1.0) * min(dx, dy)) * floor
                    push(frontier, (ng + est, nxt))
        if g0 not in best:
            return None
        nodes = [g0]
        while nodes[-1] != s0:
            nodes.append(came[nodes[-1]])
        nodes.reverse()
        points = []
        for n in nodes:
            r, c = divmod(n, width)
            points.append(((c - 1 + 0.5) * CELL, (r - 1 + 0.5) * CELL))
        points[0], points[-1] = (x0, y0), (x1, y1)
        keep = _simplify(points)
        return Route([points[i] for i in keep], [best[nodes[i]] for i in keep])


class Route:
    """A march along the cheapest path: its points (map pixels) and the km of movement spent to get
    to each of them."""

    def __init__(self, points, costs):
        self.points = [tuple(p) for p in points]
        self.costs = list(costs)

    @property
    def cost(self):
        return self.costs[-1] - self.costs[0]

    @property
    def end(self):
        return self.points[-1]

    def at(self, spent):
        """The point reached after `spent` km of movement, and the index of the stretch it lies on."""
        target = self.costs[0] + spent
        for i in range(1, len(self.points)):
            if self.costs[i] >= target:
                span = self.costs[i] - self.costs[i - 1]
                t = 1.0 if span <= 0 else (target - self.costs[i - 1]) / span
                (ax, ay), (bx, by) = self.points[i - 1], self.points[i]
                return (ax + (bx - ax) * t, ay + (by - ay) * t), i
        return self.points[-1], len(self.points)

    def advance(self, budget):
        """March `budget` km along the route: the points walked, the route still ahead (None once
        arrived) and the km spent."""
        if budget >= self.cost:
            return list(self.points), None, self.cost
        (x, y), i = self.at(budget)
        walked = self.points[:i] + [(x, y)]
        ahead = Route([(x, y)] + self.points[i:], [self.costs[0] + budget] + self.costs[i:])
        return walked, ahead, budget

    def split(self, budget):
        """The points reachable with `budget` km, and the points beyond (for drawing this month's march
        and the months after it)."""
        walked, ahead, _ = self.advance(budget)
        return walked, ahead.points if ahead else []


class Reach:
    """The cells an army can reach this month, and what each costs (a window of the grid)."""

    def __init__(self, dist, top, left, budget, passable=None):
        self.dist, self.top, self.left, self.budget = dist, top, left, budget
        self.passable = np.isfinite(dist) if passable is None else passable   # False at sea

    def cost_to(self, x, y):
        """The km of movement to get to map pixel (x, y), or inf if it is out of reach this month."""
        r, c = int(y / CELL) - self.top, int(x / CELL) - self.left
        if 0 <= r < self.dist.shape[0] and 0 <= c < self.dist.shape[1] and self.dist[r, c] <= self.budget:
            return float(self.dist[r, c])
        return math.inf

    def can_reach(self, x, y):
        return math.isfinite(self.cost_to(x, y))

    @property
    def rect(self):
        """(x, y, width, height) of the window in map pixels."""
        h, w = self.dist.shape
        return self.left * CELL, self.top * CELL, w * CELL, h * CELL


def _simplify(points, tolerance=1.2, first=0, last=None):
    """The indices of the points to keep along straight stretches (Ramer-Douglas-Peucker), so marches
    look like strides."""
    last = len(points) - 1 if last is None else last
    if last - first < 2:
        return list(range(first, last + 1))
    (x0, y0), (x1, y1) = points[first], points[last]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1e-9
    far, index = 0.0, first
    for i in range(first + 1, last):
        x, y = points[i]
        d = abs(dy * (x - x0) - dx * (y - y0)) / length
        if d > far:
            far, index = d, i
    if far <= tolerance:
        return [first, last]
    return _simplify(points, tolerance, first, index)[:-1] + _simplify(points, tolerance, index, last)
