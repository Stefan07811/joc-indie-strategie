"""Turns the province centre points from map.json into an organic, pixelated territory grid.

Pure Python (no pygame), so the logic tests and the adjacency tool can use the exact same
shapes the player sees on screen.
"""

import math

CELL = 4  # pixels per grid cell; the map is drawn at this resolution and scaled up (pixel-art look)
WARP = 11.0  # how far (in pixels) borders wander away from straight Voronoi lines


def _noise(x, y):
    return (
        math.sin(x * 0.071 + math.sin(y * 0.043) * 2.1)
        + math.sin(y * 0.067 + math.cos(x * 0.029) * 1.7)
        + 0.5 * math.sin((x + y) * 0.13)
    ) / 2.5


def land_mask(polygon, cols, rows, cell=CELL):
    """mask[row][col] = True where the cell's centre lies inside `polygon` (a list of (x, y) pixels)."""
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    mask = []
    for r in range(rows):
        y = r * cell + cell / 2
        xs = sorted(
            x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            for (x0, y0), (x1, y1) in edges
            if (y0 <= y < y1) or (y1 <= y < y0)
        )
        row = [False] * cols
        for a, b in zip(xs[::2], xs[1::2]):
            for c in range(max(0, math.ceil(a / cell - 0.5)), min(cols, math.ceil(b / cell - 0.5))):
                row[c] = True
        mask.append(row)
    return mask


BLOCK = 8  # cells per side of the blocks used to narrow down which centres can own a cell


def build_grid(provinces, width, height, cell=CELL, land=None):
    """Return grid[row][col] = province id, for a map of `width` x `height` pixels.

    `provinces` is an iterable of dicts with "id", "x", "y" and optional "size" (default 1.0;
    bigger values make the province claim more ground). With a `land` polygon, cells outside it
    belong to no province (None): the sea and the lands beyond the borders.
    """
    centres = [(p["id"], p["x"], p["y"], p.get("size", 1.0)) for p in provinces]
    cols, rows = width // cell, height // cell
    mask = land_mask(land, cols, rows, cell) if land else None
    reach = BLOCK * cell / math.sqrt(2) + WARP * math.sqrt(2)  # block centre to any warped point in it
    grid = []
    candidates = {}
    for r in range(rows):
        y = r * cell + cell / 2
        row = []
        for c in range(cols):
            if mask is not None and not mask[r][c]:
                row.append(None)
                continue
            block = (c // BLOCK, r // BLOCK)
            if block not in candidates:
                bx, by = (block[0] + 0.5) * BLOCK * cell, (block[1] + 0.5) * BLOCK * cell
                dists = [(math.hypot(bx - px, by - py), size) for _, px, py, size in centres]
                limit = min((d + reach) / s for d, s in dists)
                candidates[block] = [ce for ce, (d, s) in zip(centres, dists) if (d - reach) / s <= limit]
            x = c * cell + cell / 2
            wx = x + _noise(x, y) * WARP
            wy = y + _noise(y + 311.0, x + 97.0) * WARP
            best, best_d = None, math.inf
            for pid, px, py, size in candidates[block]:
                d = math.hypot(wx - px, wy - py) / size
                if d < best_d:
                    best, best_d = pid, d
            row.append(best)
        grid.append(row)
    if mask is not None:
        _merge_fragments(grid)
    return grid


def _pieces(grid):
    """Every connected piece of every province, as (province id, [(row, col), ...])."""
    rows, cols = len(grid), len(grid[0])
    seen = set()
    for r in range(rows):
        for c in range(cols):
            pid = grid[r][c]
            if pid is None or (r, c) in seen:
                continue
            piece, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                cr, cc = stack.pop()
                piece.append((cr, cc))
                for nr, nc in ((cr + 1, cc), (cr - 1, cc), (cr, cc + 1), (cr, cc - 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == pid and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            yield pid, piece


def _merge_fragments(grid):
    """A coastline can cut a sliver off a province; hand such stray pieces to the province around them."""
    rows, cols = len(grid), len(grid[0])
    pieces = list(_pieces(grid))
    largest = {}
    for pid, piece in pieces:
        largest[pid] = max(largest.get(pid, 0), len(piece))
    for pid, piece in pieces:
        if len(piece) == largest[pid]:
            continue
        around = {}
        for r, c in piece:
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] not in (None, pid):
                    around[grid[nr][nc]] = around.get(grid[nr][nc], 0) + 1
        if around:
            other = max(around, key=around.get)
            for r, c in piece:
                grid[r][c] = other


def adjacency(grid, min_shared=3):
    """Province pairs that share at least `min_shared` cell edges, as {id: set(neighbour ids)}."""
    shared = {}
    rows, cols = len(grid), len(grid[0])
    for r in range(rows):
        for c in range(cols):
            a = grid[r][c]
            for nr, nc in ((r + 1, c), (r, c + 1)):
                if nr < rows and nc < cols:
                    b = grid[nr][nc]
                    if a != b and a is not None and b is not None:
                        key = (a, b) if a < b else (b, a)
                        shared[key] = shared.get(key, 0) + 1
    result = {pid: set() for row in grid for pid in row if pid is not None}
    for (a, b), n in shared.items():
        if n >= min_shared:
            result[a].add(b)
            result[b].add(a)
    return result


def components(grid, pid):
    """Number of separate connected pieces province `pid` is split into (should always be 1)."""
    rows, cols = len(grid), len(grid[0])
    seen = set()
    count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != pid or (r, c) in seen:
                continue
            count += 1
            stack = [(r, c)]
            seen.add((r, c))
            while stack:
                cr, cc = stack.pop()
                for nr, nc in ((cr + 1, cc), (cr - 1, cc), (cr, cc + 1), (cr, cc - 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == pid and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
    return count


def map_grid(map_data, provinces=None):
    """The grid for a map.json document (its provinces unless others are given)."""
    land = [tuple(p) for p in map_data["land"]] if map_data.get("land") else None
    return build_grid(provinces if provinces is not None else map_data["provinces"],
                      map_data["width"], map_data["height"], land=land)
