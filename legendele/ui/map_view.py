"""Draws the campaign map: terrain, ownership, highlights, labels and army banners.

Everything map-like is drawn at grid resolution (one cell = mapshape.CELL screen pixels)
and scaled up, which gives the pixel-art look and keeps the drawing cheap.
"""

from functools import lru_cache

import pygame

from ..mapshape import CELL, build_grid
from . import theme

DECOR_SPACING = 9  # grid cells between decoration glyphs


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
        self.terrain_layer = self._build_terrain()
        self.masks = {pid: self._build_mask(pid, outline=False) for pid in game.provinces}
        self.outlines = {pid: self._build_mask(pid, outline=True) for pid in game.provinces}
        self._tints = {}
        self._owner_key = None
        self._owner_layer = None
        self._snow_layer = None
        self.army_rects = []  # (rect, army id), refreshed every frame for clicks

    # --- static layers ---------------------------------------------------------------------

    def _small(self):
        return pygame.Surface((self.cols, self.rows), pygame.SRCALPHA)

    def _scaled(self, small):
        return pygame.transform.scale(small, self.size)

    def _build_terrain(self):
        terrain = self.game.data.terrain
        small = self._small()
        for r, row in enumerate(self.grid):
            for c, pid in enumerate(row):
                base = terrain[self.game.provinces[pid].terrain]["color"]
                shade = (_hash(c, r) % 5 - 2) * 4
                small.set_at((c, r), tuple(max(0, min(255, v + shade)) for v in base))
        for pid, cells in self.cells.items():
            self._decorate(small, pid, set(cells))
        return self._scaled(small)

    def _decorate(self, small, pid, cells):
        p = self.game.provinces[pid]
        cx, cy = p.x // CELL, p.y // CELL
        for c, r in sorted(cells):
            if c % DECOR_SPACING or r % DECOR_SPACING:
                continue
            h = _hash(c, r)
            x = c + h % 5 - 2
            y = r + (h >> 3) % 5 - 2
            # keep clear of the label/army area and of the borders
            if abs(x - cx) < 14 and abs(y - cy) < 9:
                continue
            if any((x + dx, y + dy) not in cells for dx in (-4, 4) for dy in (-4, 4)):
                continue
            _GLYPHS[p.terrain](small, x, y, h)

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
        return self._scaled(small)

    def _tinted(self, kind, pid, rgba):
        key = (kind, pid, rgba)
        if key not in self._tints:
            surf = (self.outlines if kind == "outline" else self.masks)[pid].copy()
            surf.fill(rgba, special_flags=pygame.BLEND_RGBA_MULT)
            self._tints[key] = surf
        return self._tints[key]

    def _owner_overlay(self):
        key = tuple((pid, p.owner) for pid, p in self.game.provinces.items())
        if key != self._owner_key:
            self._owner_key = key
            provinces = self.game.provinces
            small = self._small()
            for r, row in enumerate(self.grid):
                for c, pid in enumerate(row):
                    owner = provinces[pid].owner
                    color = theme.faction_color(self.game, owner)
                    rgba = (*color, 64 if owner else 0)
                    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nc, nr = c + dc, r + dr
                        if not (0 <= nc < self.cols and 0 <= nr < self.rows):
                            continue
                        other = self.grid[nr][nc]
                        if other == pid:
                            continue
                        if provinces[other].owner != owner:
                            rgba = (*color, 255) if owner else (*theme.INK, 150)
                            break
                        rgba = (*theme.INK, 110)
                    small.set_at((c, r), rgba)
            self._owner_layer = self._scaled(small)
        return self._owner_layer

    def _snow(self):
        if self._snow_layer is None:
            small = self._small()
            small.fill((235, 240, 250, 60))
            for r in range(self.rows):
                for c in range(self.cols):
                    if _hash(c + 7, r + 3) % 9 == 0:
                        small.set_at((c, r), (250, 252, 255, 170))
            self._snow_layer = self._scaled(small)
        return self._snow_layer

    # --- per frame -------------------------------------------------------------------------

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
        surface.blit(self._owner_overlay(), (0, 0))
        if game.season == "Winter":
            surface.blit(self._snow(), (0, 0))

        if reach:
            # Dim everything the selected army cannot reach this turn.
            here = game.armies[selected_army].province if selected_army in game.armies else None
            for pid in game.provinces:
                if pid not in reach and pid != here:
                    surface.blit(self._tinted("mask", pid, (20, 14, 10, 110)), (0, 0))
        if hovered:
            surface.blit(self._tinted("outline", hovered, (255, 250, 220, 200)), (0, 0))
        if selected_province:
            surface.blit(self._tinted("outline", selected_province, (*theme.HIGHLIGHT, 255)), (0, 0))

        if path:
            points = [(game.provinces[pid].x, game.provinces[pid].y + 24) for pid in path]
            pygame.draw.lines(surface, theme.INK, False, points, 5)
            pygame.draw.lines(surface, theme.HIGHLIGHT, False, points, 3)
            pygame.draw.circle(surface, theme.HIGHLIGHT, points[-1], 6)

        attacker = game.armies[selected_army].faction if selected_army in game.armies else None
        for p in game.provinces.values():
            self._draw_province_marks(surface, p, reach, attacker)

        self.army_rects = []
        for pid in game.provinces:
            self._draw_armies(surface, pid, selected_army)

    def _draw_province_marks(self, surface, p, reach, attacker):
        game = self.game
        icon = None
        if p.special == "heart":
            icon = self.assets.get("heart")
        elif p.walls:
            icon = self.assets.get("castle", theme.faction_color(game, p.owner))
        elif p.garrison:
            icon = self.assets.get("camp", theme.faction_color(game, p.owner))
        if icon:
            rect = surface.blit(icon, icon.get_rect(midbottom=(p.x, p.y - 18)))
            if p.garrison:
                theme.text(surface, str(len(p.garrison)), (rect.right + 3, rect.centery), 16, theme.PARCHMENT,
                           anchor="midleft", shadow=theme.INK)
            if p.besieged_by is not None:
                swords = self.assets.get("siege")
                surface.blit(swords, swords.get_rect(midright=(rect.left - 4, rect.centery)))
        theme.text(surface, p.name, (p.x, p.y - 8), 18, theme.PARCHMENT, anchor="center", shadow=theme.INK)
        if reach and p.id in reach:
            # gold: a free march; red: a battle, a siege or an assault awaits
            color = theme.DANGER if game.looks_defended(attacker, p.id) else theme.HIGHLIGHT
            badge = (p.x, p.y + 52)
            pygame.draw.circle(surface, theme.INK, badge, 10)
            pygame.draw.circle(surface, color, badge, 10, 2)
            theme.text(surface, str(reach[p.id].cost), (badge[0] + 1, badge[1] + 1), 18, color, anchor="center")

    def _draw_armies(self, surface, pid, selected_army):
        armies = self.game.armies_seen(self.game.player, pid)
        p = self.game.provinces[pid]
        for i, army in enumerate(armies):
            color = theme.faction_color(self.game, army.faction)
            sprite = self.assets.get(f"army_{army.faction}", color)
            x = p.x + (i - (len(armies) - 1) / 2) * 26
            rect = sprite.get_rect(midbottom=(x, p.y + 40))
            if army.id == selected_army:
                pygame.draw.ellipse(surface, theme.HIGHLIGHT, rect.inflate(14, 4).move(0, 4), 3)
            elif army.faction == self.game.player and army.moves_left == 0:
                sprite = sprite.copy()
                sprite.set_alpha(140)
            surface.blit(sprite, rect)
            theme.text(surface, str(len(army.regiments)), rect.midright, 16, theme.PARCHMENT,
                       anchor="midleft", shadow=theme.INK)
            self.army_rects.append((rect.inflate(8, 4), army.id))


# --- terrain glyphs, drawn at grid resolution --------------------------------------------

def _mountain(s, x, y, h):
    pygame.draw.polygon(s, (92, 86, 84), [(x - 4, y + 2), (x, y - 4), (x + 4, y + 2)])
    pygame.draw.polygon(s, (112, 106, 102), [(x, y - 4), (x + 4, y + 2), (x + 1, y + 2)])
    pygame.draw.polygon(s, (240, 240, 236), [(x - 1, y - 2), (x, y - 4), (x + 1, y - 2)])


def _tree(s, x, y, h):
    for dx in (-2, 2) if h & 1 else (0,):
        pygame.draw.polygon(s, (40, 82, 46), [(x + dx - 2, y + 1), (x + dx, y - 3), (x + dx + 2, y + 1)])
        s.set_at((x + dx, y + 2), (96, 64, 40))


def _hill(s, x, y, h):
    pygame.draw.lines(s, (140, 118, 72), False, [(x - 4, y + 1), (x - 2, y - 1), (x, y - 1), (x + 2, y + 1)])
    pygame.draw.lines(s, (196, 176, 122), False, [(x - 3, y + 1), (x - 2, y), (x, y)])


def _marsh(s, x, y, h):
    pygame.draw.line(s, (84, 106, 128), (x - 3, y + 1), (x + 3, y + 1))
    for dx in (-1, 1, 3):
        pygame.draw.line(s, (60, 86, 52), (x + dx, y), (x + dx, y - 2 - (h >> dx + 2) % 2))


def _field(s, x, y, h):
    color = (196, 188, 108) if h & 2 else (132, 160, 80)
    pygame.draw.rect(s, color, (x - 2, y - 1, 4, 2))


_GLYPHS = {"mountains": _mountain, "forest": _tree, "hills": _hill, "marsh": _marsh, "plains": _field}
