"""Draws the campaign map: the painted land (painter.py), then every frame the realms' colours,
highlights, settlement flags, labels and the armies' standards.

Province shapes come from a coarse grid (one cell = mapshape.CELL pixels); the colour washes and
highlights are drawn on that grid and smoothed up, so borders look painted rather than pixelated.
"""

import math
import time
from functools import lru_cache

import pygame

from .. import profile
from ..mapshape import CELL, build_grid
from . import figures, painter, theme


@lru_cache(maxsize=4)
def _grid_for(provinces_key, width, height):
    provinces = [dict(id=i, x=x, y=y, size=s) for i, x, y, s in provinces_key]
    return build_grid(provinces, width, height)


def province_grid(data):
    key = tuple((p["id"], p["x"], p["y"], p.get("size", 1.0)) for p in data.provinces)
    return _grid_for(key, data.map["width"], data.map["height"])


def _hash(c, r):
    h = (c * 374761393 + r * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h


_army_figures = {}
_pennants = {}


def army_figure(fid, color):
    if (fid, color) not in _army_figures:
        _army_figures[(fid, color)] = figures.army(fid, color, fid)
    return _army_figures[(fid, color)]


class MapView:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        data = game.data
        self.grid = province_grid(data)
        self.rows, self.cols = len(self.grid), len(self.grid[0])
        self.cells = {pid: [] for pid in game.provinces}
        for r, row in enumerate(self.grid):
            for c, pid in enumerate(row):
                self.cells[pid].append((c, r))
        self.size = (self.cols * CELL, self.rows * CELL)
        self.terrain_layer = painter.paint(data, self.grid, profile.home() / "cache")
        capitals = {f["capital"] for f in data.factions.values() if f["capital"]}
        self.settlement = {
            p["id"]: "shrine" if p.get("special") == "heart" else
            "castle" if p.get("walls") or p["id"] in capitals else "village"
            for p in data.provinces
        }
        self.masks = {pid: self._build_mask(pid, outline=False) for pid in game.provinces}
        self.outlines = {pid: self._build_mask(pid, outline=True) for pid in game.provinces}
        self._tints = {}
        self._owner_key = None
        self._owner_layer = None
        self._snow_layer = None
        self.army_rects = []  # (rect, army id), refreshed every frame for clicks
        self.marching = {}  # army id -> (points, start time, seconds per step): standards on the move

    # --- layers ----------------------------------------------------------------------------

    def _small(self):
        return pygame.Surface((self.cols, self.rows), pygame.SRCALPHA)

    def _smooth(self, small):
        return pygame.transform.smoothscale(small, self.size)

    def _build_mask(self, pid, outline):
        small = self._small()
        cells = self.cells[pid]
        if outline:
            cellset = set(cells)
            cells = [
                (c, r) for c, r in cells
                if any((c + dc, r + dr) not in cellset for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            ]
        for c, r in cells:
            small.set_at((c, r), (255, 255, 255, 255))
        return self._smooth(small)

    def _tinted(self, kind, pid, rgba):
        key = (kind, pid, rgba)
        if key not in self._tints:
            surf = (self.outlines if kind == "outline" else self.masks)[pid].copy()
            surf.fill(rgba, special_flags=pygame.BLEND_RGBA_MULT)
            self._tints[key] = surf
        return self._tints[key]

    def _owner_overlay(self):
        """A light wash of each realm's colour, a bold line where realms meet, a faint one between
        provinces of the same realm."""
        key = tuple((pid, p.owner) for pid, p in self.game.provinces.items())
        if key != self._owner_key:
            self._owner_key = key
            provinces = self.game.provinces
            wash, lines = self._small(), self._small()
            for r, row in enumerate(self.grid):
                for c, pid in enumerate(row):
                    owner = provinces[pid].owner
                    color = theme.faction_color(self.game, owner)
                    if owner:
                        wash.set_at((c, r), (*color, 46))
                    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nc, nr = c + dc, r + dr
                        if not (0 <= nc < self.cols and 0 <= nr < self.rows):
                            continue
                        other = self.grid[nr][nc]
                        if other == pid:
                            continue
                        if provinces[other].owner != owner:
                            lines.set_at((c, r), (*color, 235) if owner else (*theme.INK, 120))
                            break
                        lines.set_at((c, r), (*theme.INK, 60))
            layer = self._smooth(wash)
            layer.blit(self._smooth(lines), (0, 0))
            self._owner_layer = layer
        return self._owner_layer

    def _snow(self):
        if self._snow_layer is None:
            small = self._small()
            for r in range(self.rows):
                for c in range(self.cols):
                    n = (math.sin(c * 0.21 + math.sin(r * 0.13) * 2) + math.sin(r * 0.17 + c * 0.05)) / 2
                    alpha = int(52 + 38 * n + (_hash(c, r) % 14))
                    small.set_at((c, r), (232, 240, 252, max(0, min(150, alpha))))
            self._snow_layer = self._smooth(small)
        return self._snow_layer

    # --- per frame -------------------------------------------------------------------------

    def march(self, army_id, provinces, step=0.18):
        """Slide an army's standard along the provinces it just marched through."""
        points = [self._banner_spot(self.game.provinces[pid]) for pid in provinces]
        if len(points) > 1:
            self.marching[army_id] = (points, time.monotonic(), step)

    def _banner_spot(self, p):
        return (p.x, p.y + 54)

    def _marching_spot(self, army_id):
        points, start, step = self.marching[army_id]
        t = (time.monotonic() - start) / step
        if t >= len(points) - 1:
            del self.marching[army_id]
            return None
        i = int(t)
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        f = t - i
        return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)

    def province_at(self, pos):
        x, y = pos
        c, r = int(x) // CELL, int(y) // CELL
        if 0 <= c < self.cols and 0 <= r < self.rows:
            return self.grid[r][c]
        return None

    def army_at(self, pos):
        for rect, army_id in reversed(self.army_rects):
            if rect.collidepoint(pos):
                return army_id
        return None

    def draw(self, surface, *, hovered=None, selected_province=None, selected_army=None, reach=None,
             path=None):
        game = self.game
        surface.blit(self.terrain_layer, (0, 0))
        if game.season == "Winter":
            surface.blit(self._snow(), (0, 0))
        surface.blit(self._owner_overlay(), (0, 0))

        if reach:
            # Dim everything the selected army cannot reach this turn.
            here = game.armies[selected_army].province if selected_army in game.armies else None
            for pid in game.provinces:
                if pid not in reach and pid != here:
                    surface.blit(self._tinted("mask", pid, (16, 12, 8, 120)), (0, 0))
        if hovered:
            surface.blit(self._tinted("outline", hovered, (255, 248, 220, 230)), (0, 0))
        if selected_province:
            surface.blit(self._tinted("outline", selected_province, (*theme.HIGHLIGHT, 255)), (0, 0))

        if path:
            self._draw_path(surface, [self._banner_spot(game.provinces[pid]) for pid in path])

        attacker = game.armies[selected_army].faction if selected_army in game.armies else None
        for p in sorted(game.provinces.values(), key=lambda p: p.y):
            self._draw_province_marks(surface, p, reach, attacker)

        self.army_rects = []
        for pid in sorted(game.provinces, key=lambda pid: game.provinces[pid].y):
            self._draw_armies(surface, pid, selected_army)

    def _draw_path(self, surface, points):
        points = [(x, y - 4) for x, y in points]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = math.hypot(x1 - x0, y1 - y0) or 1
            for k in range(0, int(length), 14):
                a, b = k / length, min(1.0, (k + 8) / length)
                start = (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a)
                end = (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)
                pygame.draw.line(surface, theme.INK, start, end, 6)
                pygame.draw.line(surface, theme.HIGHLIGHT, start, end, 3)
        x, y = points[-1]
        pygame.draw.circle(surface, theme.INK, (x, y), 9)
        pygame.draw.circle(surface, theme.HIGHLIGHT, (x, y), 7)

    def _draw_province_marks(self, surface, p, reach, attacker):
        game = self.game
        kind = self.settlement[p.id]
        size = {"castle": figures.CASTLE_SIZE, "village": figures.VILLAGE_SIZE, "shrine": (54, 44)}[kind]
        base = (p.x, p.y - 14)
        if p.owner:
            color = theme.faction_color(game, p.owner)
            if color not in _pennants:
                _pennants[color] = figures.pennant(color)
            dx, dy = figures.flag_top(kind)
            flag = _pennants[color]
            surface.blit(flag, flag.get_rect(bottomleft=(base[0] + dx - 2, base[1] + dy + 8)))
        if p.garrison:
            self._shield(surface, (base[0] + size[0] // 2 + 2, base[1] - 10), len(p.garrison),
                         theme.faction_color(game, p.owner) if p.owner else theme.NEUTRAL, p.walls)
        if p.besieged_by is not None:
            swords = self.assets.get("siege")
            surface.blit(swords, swords.get_rect(midright=(base[0] - size[0] // 2 - 2, base[1] - 14)))
        theme.outlined(surface, p.name, (p.x, p.y + 4), 17)
        if reach and p.id in reach:
            # gold: a free march; red: a battle, a siege or an assault awaits
            color = theme.DANGER if game.looks_defended(attacker, p.id) else theme.HIGHLIGHT
            badge = (p.x + 26, p.y + 30)
            pygame.draw.circle(surface, theme.INK, badge, 11)
            pygame.draw.circle(surface, color, badge, 11, 2)
            theme.outlined(surface, str(reach[p.id].cost), (badge[0], badge[1] - 1), 15, color, width=1)

    def _shield(self, surface, pos, count, color, walls):
        x, y = pos
        points = [(x - 8, y - 9), (x + 8, y - 9), (x + 8, y + 1), (x, y + 9), (x - 8, y + 1)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (226, 190, 96) if walls else theme.INK, points, 2)
        theme.outlined(surface, str(count), (x, y - 1), 13, theme.PARCHMENT, width=1)

    def _draw_armies(self, surface, pid, selected_army):
        armies = self.game.armies_seen(self.game.player, pid)
        p = self.game.provinces[pid]
        for i, army in enumerate(armies):
            color = theme.faction_color(self.game, army.faction)
            sprite = self.assets.load(f"army_{army.faction}") or army_figure(army.faction, color)
            x, y = self._banner_spot(p)
            x += (i - (len(armies) - 1) / 2) * 36
            if army.id in self.marching:
                x, y = self._marching_spot(army.id) or (x, y)
            rect = sprite.get_rect(midbottom=(x, y))
            if army.id == selected_army:
                ring = pygame.Rect(0, 0, 50, 16)
                ring.center = (x, y - 3)
                pygame.draw.ellipse(surface, theme.INK, ring.inflate(4, 4), 3)
                pygame.draw.ellipse(surface, theme.HIGHLIGHT, ring, 3)
            elif army.faction == self.game.player and army.moves_left == 0:
                sprite = sprite.copy()
                sprite.set_alpha(150)
            surface.blit(sprite, rect)
            plaque = (rect.right - 2, rect.bottom - 8)
            pygame.draw.circle(surface, theme.INK, plaque, 9)
            pygame.draw.circle(surface, (226, 190, 96), plaque, 9, 1)
            theme.outlined(surface, str(len(army.regiments)), (plaque[0], plaque[1] - 1), 13, theme.PARCHMENT, width=1)
            self.army_rects.append((rect.inflate(6, 4), army.id))
