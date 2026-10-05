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


def build_grid(provinces, width, height, cell=CELL):
    """Return grid[row][col] = province id, for a map of `width` x `height` pixels.

    `provinces` is an iterable of dicts with "id", "x", "y" and optional "size" (default 1.0;
    bigger values make the province claim more ground).
    """
    centres = [(p["id"], p["x"], p["y"], p.get("size", 1.0)) for p in provinces]
    cols, rows = width // cell, height // cell
    grid = []
    for r in range(rows):
        y = r * cell + cell / 2
        row = []
        for c in range(cols):
            x = c * cell + cell / 2
            wx = x + _noise(x, y) * WARP
            wy = y + _noise(y + 311.0, x + 97.0) * WARP
            best, best_d = None, math.inf
            for pid, px, py, size in centres:
                d = math.hypot(wx - px, wy - py) / size
                if d < best_d:
                    best, best_d = pid, d
            row.append(best)
        grid.append(row)
    return grid


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
                    if a != b:
                        key = (a, b) if a < b else (b, a)
                        shared[key] = shared.get(key, 0) + 1
    result = {pid: set() for row in grid for pid in row}
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
