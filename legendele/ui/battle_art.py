"""The look of a real-time battle: the painted field, the soldiers one by one, and what flies
between them (arrows, shot, dust, sparks). Drawing only; the fight itself is game/realtime.py.

Every regiment is drawn as a little crowd in formation. Each man walks to his place in the ranks,
steps while marching, strikes while in melee and falls when the regiment loses strength; the fallen
stay on the ground for the rest of the battle.
"""

import math
import random

import pygame

from ..game.realtime import FIELD_H, FIELD_W, WALL_X
from . import painter

SCALE = 1.5  # figures' size on the field, in pixels per unit of their drawings
S = 3 * SCALE  # figures are drawn this many times larger, then smoothed down
SKIN = (222, 184, 146)
METAL = (186, 186, 196)
WOOD = (112, 80, 48)
DARK = (34, 26, 22)


def _shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


# --- the figures -----------------------------------------------------------------------------

class _Pen:
    """Draws on a figure at S times its size, with coordinates in final pixels."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.surface = pygame.Surface((round(w * S), round(h * S)), pygame.SRCALPHA)

    def ellipse(self, color, x, y, w, h):
        pygame.draw.ellipse(self.surface, color, (x * S, y * S, w * S, h * S))

    def rect(self, color, x, y, w, h):
        pygame.draw.rect(self.surface, color, (round(x * S), round(y * S), round(w * S), round(h * S)))

    def line(self, color, a, b, width=1.0):
        pygame.draw.line(self.surface, color, (a[0] * S, a[1] * S), (b[0] * S, b[1] * S), max(1, round(width * S)))

    def circle(self, color, x, y, r):
        pygame.draw.circle(self.surface, color, (x * S, y * S), r * S)

    def poly(self, color, points):
        pygame.draw.polygon(self.surface, color, [(x * S, y * S) for x, y in points])

    def arc(self, color, x, y, w, h, a0, a1, width=1.0):
        pygame.draw.arc(self.surface, color, (x * S, y * S, w * S, h * S), a0, a1, max(1, round(width * S)))

    def done(self):
        return pygame.transform.smoothscale(self.surface, (round(self.w * SCALE), round(self.h * SCALE)))


def _shadow(p, cx, ground, w):
    p.ellipse((0, 0, 0, 70), cx - w / 2, ground - 1.6, w, 3.2)


def _legs(p, cx, top, ground, step, color, gap=1.6):
    """Two legs from `top` to the feet, swung by `step` (-1, 0 or 1)."""
    for side in (-1, 1):
        foot = cx + side * gap / 2 + step * side * 1.2
        p.line(color, (cx + side * 0.6, top), (foot, ground - 0.4), 1.4)


def _man(p, cx, ground, color, step, tall=11.0, head=SKIN, hat=None, cloak=None):
    """A standing man facing right; returns (shoulder y, hand x, hand y) for his weapons."""
    hip = ground - tall * 0.42
    shoulder = ground - tall * 0.78
    _legs(p, cx, hip, ground, step, _shade(color, 0.55))
    if cloak:
        p.poly(cloak, [(cx - 1.4, shoulder), (cx - 3.4, hip + 2.5), (cx + 0.2, hip + 2.0)])
    p.poly(color, [(cx - 1.8, shoulder), (cx + 1.8, shoulder), (cx + 2.2, hip + 1), (cx - 2.2, hip + 1)])
    p.line(_shade(color, 0.7), (cx - 2.1, hip + 0.4), (cx + 2.1, hip + 0.4), 0.6)  # belt
    p.circle(head, cx + 0.2, shoulder - 1.7, 1.75)
    if hat:
        p.ellipse(hat, cx - 1.8, shoulder - 4.0, 4.0, 2.2)
    return shoulder, cx + 2.0, shoulder + 2.2


def _spearman(p, color, step, strike, shield=True):
    _shadow(p, 6, 17, 8)
    sh, hx, hy = _man(p, 6, 17, color, step, hat=_shade(color, 0.6))
    reach = 2.5 if strike else 0
    p.line(WOOD, (hx - 4 + reach, hy + 3), (hx + 2 + reach, sh - 6), 0.9)
    p.poly(METAL, [(hx + 2 + reach, sh - 6), (hx + 2.8 + reach, sh - 8.2), (hx + 2.9 + reach, sh - 5.4)])
    if shield:
        p.ellipse(_shade(color, 0.8), 6.4, sh + 0.2, 3.4, 5.0)
        p.ellipse(METAL, 7.6, sh + 2.0, 1.0, 1.2)


def _archer(p, color, step, strike):
    _shadow(p, 6, 17, 8)
    sh, hx, hy = _man(p, 6, 17, _shade(color, 0.9), step, hat=(96, 72, 50))
    pull = 1.2 if strike else 0
    p.arc(WOOD, hx - 1.5, sh - 3.5, 4.5, 10, -1.3, 1.3, 0.8)
    p.line((230, 220, 190), (hx + 0.6, sh - 3.2), (hx - pull, sh + 1.5), 0.4)
    p.line((230, 220, 190), (hx - pull, sh + 1.5), (hx + 0.6, sh + 6.2), 0.4)
    p.rect((120, 90, 60), 3.2, sh + 0.5, 1.4, 4)  # quiver


def _gunner(p, color, step, strike):
    _shadow(p, 6, 17, 8)
    sh, hx, hy = _man(p, 6, 17, color, step, hat=DARK)
    kick = -0.8 if strike else 0
    p.line(WOOD, (hx - 3 + kick, hy + 1), (hx + 1 + kick, hy - 1), 1.3)
    p.line((70, 70, 76), (hx + 1 + kick, hy - 1), (hx + 6 + kick, hy - 3), 0.9)
    if strike:
        p.circle((255, 220, 120), hx + 6.8, hy - 3.3, 1.0)


def _hunter(p, color, step, strike):
    _shadow(p, 6, 17, 8)
    sh, hx, hy = _man(p, 6, 17, (70, 62, 54), step, hat=(52, 44, 38), cloak=color)
    reach = 2 if strike else 0
    p.line(WOOD, (hx - 1 + reach, hy + 2), (hx + 3 + reach, sh - 3), 1.1)
    p.poly((200, 190, 160), [(hx + 3 + reach, sh - 3), (hx + 4.5 + reach, sh - 5), (hx + 3.8 + reach, sh - 2.4)])


def _outlaw(p, color, step, strike):
    _shadow(p, 6, 17, 8)
    sh, hx, hy = _man(p, 6, 17, (214, 204, 182), step, hat=(60, 44, 32))
    p.line(color, (4.2, sh + 4.6), (7.8, sh + 4.6), 0.9)  # sash
    lift = -3 if strike else 0
    p.line(WOOD, (hx, hy), (hx + 2.4, sh - 4 + lift), 0.9)
    p.poly(METAL, [(hx + 2.4, sh - 4 + lift), (hx + 4.2, sh - 3.4 + lift), (hx + 3.2, sh - 1.4 + lift)])


def _rider(p, color, step, strike):
    _shadow(p, 9, 19, 15)
    horse = (104, 72, 46)
    legs = _shade(horse, 0.7)
    for i, x in enumerate((4.0, 6.0, 12.0, 14.0)):
        swing = step * (1 if i % 2 else -1) * 1.4
        p.line(legs, (x, 13.5), (x + swing, 18.6), 1.1)
    p.ellipse(horse, 2.5, 9.6, 13.5, 5.6)
    p.poly(horse, [(14, 11.5), (17.2, 7.4), (18.6, 8.4), (16, 13)])  # neck and head
    p.line((40, 30, 24), (2.8, 10.8), (0.8, 14), 1.0)  # tail
    p.rect(color, 5.5, 9.4, 6, 1.6)  # saddle cloth
    sh, hx, hy = _man(p, 9, 11, color, 0, tall=8.5, hat=METAL)
    reach = 3 if strike else 0
    p.line(WOOD, (hx - 5 + reach, hy + 1.5), (hx + 6 + reach, hy - 2.5), 0.9)
    p.poly(METAL, [(hx + 6 + reach, hy - 2.5), (hx + 8 + reach, hy - 3.4), (hx + 6.4 + reach, hy - 1.4)])


def _whelp(p, color, step, strike):
    _shadow(p, 7, 15, 11)
    body = (122, 132, 66)
    for x in (4.5, 9):
        p.line(_shade(body, 0.7), (x, 11), (x + step, 15), 1.3)
    p.ellipse(body, 2.5, 7.5, 9.5, 5.5)
    p.poly(_shade(color, 0.9), [(5, 8.5), (8, 2.5 - (1.5 if strike else 0)), (9.5, 8)])  # wing
    p.poly(body, [(10.5, 9), (13.4, 6.2), (14.4, 7.6), (12, 10.4)])
    p.line(body, (3, 10), (0.4, 12.5), 1.0)
    if strike:
        p.circle((255, 170, 60), 14.6, 7.0, 1.1)


def _drake(p, color, step, strike):
    _shadow(p, 7, 19, 11)
    scales = (96, 116, 70)
    sh, hx, hy = _man(p, 7, 19, color, step, tall=15, head=scales)
    p.poly(scales, [(6.0, sh - 3.6), (8.6, sh - 4.4), (8.0, sh - 2.4)])  # snout
    lift = -4 if strike else 0
    p.line(WOOD, (hx, hy), (hx + 3, sh - 3 + lift), 1.2)
    p.circle((90, 90, 96), hx + 3.4, sh - 3.6 + lift, 1.8)
    p.circle(METAL, hx + 3.0, sh - 4.0 + lift, 0.6)


def _wyrm(p, color, step, strike):
    _shadow(p, 15, 27, 26)
    body = (92, 104, 62)
    belly = (170, 160, 100)
    p.poly(_shade(color, 0.8), [(10, 15), (14, 2 - (2 if strike else 0)), (21, 13)])  # wing
    for i, x in enumerate((8, 12, 18, 22)):
        p.line(_shade(body, 0.7), (x, 21), (x + step * (1 if i % 2 else -1), 26.4), 1.6)
    p.ellipse(body, 4, 14, 22, 9)
    p.ellipse(belly, 7, 18.5, 15, 3.5)
    p.line(body, (5, 18), (0.5, 22), 1.8)
    for k, (dx, dy) in enumerate(((0, -2), (2.6, 1), (1, 4))):
        neck = (24 + dx * 0.4, 16 + dy * 0.4)
        head = (28 + dx, 10 + dy)
        p.line(body, neck, head, 1.6)
        p.ellipse(body, head[0] - 1, head[1] - 1.2, 3.4, 2.4)
        if strike:
            p.circle((255, 150, 40), head[0] + 3.4, head[1] + 0.2, 1.4)
            p.circle((255, 230, 140), head[0] + 3.0, head[1] + 0.2, 0.7)


def _imp(p, color, step, strike):
    _shadow(p, 5, 13, 6)
    sh, hx, hy = _man(p, 5, 13, (66, 50, 44), step, tall=8, head=(104, 70, 56))
    p.poly((66, 50, 44), [(4.2, sh - 3.4), (4.6, sh - 5.4), (5.4, sh - 3.6)])  # little horn
    p.line(color, (hx, hy), (hx + 2 + (1 if strike else 0), hy - 2), 0.8)


def _hero(p, color, step, strike):
    _shadow(p, 9, 25, 12)
    sh, hx, hy = _man(p, 9, 25, color, step, tall=19, cloak=_shade(color, 0.6))
    p.poly((236, 196, 70), [(7.4, sh - 5.6), (7.6, sh - 7.6), (8.6, sh - 6.4), (9.4, sh - 7.8), (10.2, sh - 6.4),
                            (11, sh - 7.6), (11.2, sh - 5.6)])  # crown
    lift = -5 if strike else 0
    p.line(METAL, (hx, hy), (hx + 4, sh - 6 + lift), 1.2)
    p.line((236, 196, 70), (hx - 1, hy + 0.6), (hx + 1.2, hy - 0.6), 1.0)


def _fae(p, color, step, strike):
    _shadow(p, 6, 17, 7)
    dress = (236, 232, 240)
    sway = (1.2 if strike else 0.4) * (1 if step >= 0 else -1)
    p.poly(dress, [(6 + sway, 6), (2.4, 16.6), (9.6, 16.6)])
    p.line(_shade(color, 1.1), (3.4, 12.5), (8.6, 12.5), 0.6)
    p.circle(SKIN, 6.2 + sway, 4.6, 1.7)
    p.line((214, 176, 92), (5, 3.2), (3.2 + sway, 7.5), 0.8)  # long hair
    p.line(dress, (6.4, 8), (10 + sway, 4.5 - (2 if strike else 0)), 0.6)
    p.line(dress, (5.6, 8), (2 + sway, 5), 0.6)


def _maiden(p, color, step, strike):
    _fae(p, color, step, strike)
    p.poly((246, 214, 96), [(4.8, 3.0), (6.2, 1.6), (7.6, 3.0)])  # a wreath of flowers
    if strike:
        p.circle((255, 246, 190, 160), 6, 9, 5)


def _sprite(p, color, step, strike):
    glow = (190, 220, 255)
    p.circle((*glow, 60), 6, 9, 5.5)
    _shadow(p, 6, 17, 5)
    p.poly(glow, [(6, 6), (3.8, 14 + step * 0.5), (8.2, 14 - step * 0.5)])
    p.circle((236, 244, 255), 6.2, 4.6, 1.6)
    p.line((150, 200, 255), (7.4, 8), (11, 5.4 - (2 if strike else 0)), 0.8)


def _spirit(p, color, step, strike):
    _shadow(p, 7, 18, 10)
    bark = (98, 76, 52)
    _legs(p, 7, 11, 18, step, _shade(bark, 0.8), gap=3)
    p.poly(bark, [(5, 13), (9, 13), (8.6, 5), (5.4, 5)])
    p.circle((70, 112, 58), 7, 5, 4.2)
    p.circle((96, 140, 70), 6, 4, 2.4)
    p.line(bark, (9, 7), (12 + (1.5 if strike else 0), 4), 1.0)


def _dead(p, color, step, strike):
    _shadow(p, 6, 17, 7)
    bone = (200, 196, 172)
    sh, hx, hy = _man(p, 6, 17, (110, 108, 96), step, head=bone)
    p.line(bone, (hx - 1, hy - 0.6), (hx + 2.8 + (1.5 if strike else 0), hy - 0.2), 0.8)  # reaching arm
    p.circle(DARK, 6.8, sh - 1.9, 0.4)
    p.line((140, 130, 120), (hx + 1, hy + 1), (hx + 4, hy - 3 + (2 if strike else 0)), 0.8)  # rusty blade


def _vampire(p, color, step, strike):
    _shadow(p, 6, 17, 8)
    cloak = (30, 24, 30)
    sh, hx, hy = _man(p, 6, 17, cloak, step, head=(222, 214, 210), cloak=(150, 24, 32))
    p.poly(cloak, [(4.2, sh - 1), (6.2, sh + 0.6), (8.2, sh - 1), (8, sh + 3), (4.4, sh + 3)])  # high collar
    reach = 2 if strike else 0
    p.line((210, 200, 196), (hx, hy), (hx + 2 + reach, hy - 1), 0.8)


def _wraith(p, color, step, strike):
    ghost = (210, 226, 220, 190)
    p.circle((160, 220, 200, 50), 6, 10, 6)
    p.poly(ghost, [(6, 3), (2.2, 15 + step), (4.4, 13.6), (6, 16), (7.6, 13.6), (9.8, 15 - step)])
    p.circle((30, 40, 40), 5.4, 5.4, 0.5)
    p.circle((30, 40, 40), 7.0, 5.4, 0.5)
    p.line(ghost, (8, 8), (11.5, 6 - (2 if strike else 0)), 0.8)


def _wolf(p, color, step, strike):
    _shadow(p, 8, 15, 13)
    fur = (110, 104, 98)
    for i, x in enumerate((4, 6, 11, 13)):
        p.line(_shade(fur, 0.7), (x, 11), (x + step * (1 if i % 2 else -1), 15), 1.1)
    p.ellipse(fur, 2, 7, 13, 5.4)
    jaw = 1.2 if strike else 0
    p.poly(fur, [(13, 8), (16.5, 7 + jaw * 0.3), (16.5, 9.4 + jaw), (13.4, 11)])  # head
    p.poly(fur, [(13.6, 7.6), (14.4, 5.4), (15, 7.6)])  # ear
    p.line(fur, (2.4, 8.4), (0.2, 6.4), 1.1)  # tail
    p.circle((230, 200, 80), 15.2, 8.2, 0.4)


FIGURES = {
    # icon: (draw, size, men, files, spacing)
    "spear": (_spearman, (12, 19), 20, 5, 7.0),
    "bow": (_archer, (12, 19), 16, 4, 8.0),
    "gun": (_gunner, (14, 19), 16, 4, 8.0),
    "stake": (_hunter, (12, 19), 16, 4, 8.0),
    "axe": (_outlaw, (12, 19), 16, 4, 8.0),
    "horse": (_rider, (20, 21), 10, 5, 8.0),
    "whelp": (_whelp, (16, 17), 9, 3, 11.0),
    "mace": (_drake, (14, 21), 6, 3, 11.0),
    "wyrm": (_wyrm, (34, 29), 2, 2, 20.0),
    "imp": (_imp, (10, 15), 16, 4, 8.0),
    "crown": (_hero, (18, 27), 1, 1, 0.0),
    "flower": (_fae, (12, 19), 16, 4, 8.0),
    "star": (_maiden, (12, 19), 12, 4, 8.0),
    "bolt": (_sprite, (12, 19), 16, 4, 8.0),
    "tree": (_spirit, (14, 20), 9, 3, 11.0),
    "skull": (_dead, (12, 19), 20, 5, 7.0),
    "fang": (_vampire, (12, 19), 12, 4, 8.0),
    "ghost": (_wraith, (12, 19), 12, 4, 8.0),
    "wolf": (_wolf, (18, 17), 10, 5, 8.0),
}
STEPS = (0, 1, 0, -1)  # a walking cycle
_figures = {}


def figure(icon, color, frame, flip):
    """frame: 0-3 walking, 4 striking. Feet at the bottom centre of the image."""
    key = (icon, color, frame, flip)
    if key not in _figures:
        draw, size, *_ = FIGURES.get(icon, FIGURES["spear"])
        pen = _Pen(*size)
        draw(pen, color, STEPS[frame % 4] if frame < 4 else 0, frame == 4)
        image = pen.done()
        _figures[key] = pygame.transform.flip(image, True, False) if flip else image
    return _figures[key]


def fallen(icon, color, flip):
    """A man lying on the field."""
    key = (icon, color, "fallen", flip)
    if key not in _figures:
        image = pygame.transform.rotate(figure(icon, color, 0, flip), 90 if flip else -90)
        dim = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        dim.fill((150, 140, 130, 255))
        image = image.copy()
        image.blit(dim, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        _figures[key] = image
    return _figures[key]


# --- the troops ------------------------------------------------------------------------------

class Man:
    __slots__ = ("x", "y", "slot", "jx", "jy", "phase", "alive")

    def __init__(self, slot, rng):
        self.slot = slot
        self.jx, self.jy = rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4)
        self.phase = rng.random() * 4
        self.alive = True
        self.x = self.y = None


class Troops:
    """The men of every regiment on the field, and the fallen."""

    def __init__(self, field, units, colors, decals):
        self.field = field
        self.units = units
        self.colors = colors
        self.decals = decals  # the ground; the fallen are painted onto it
        self.rng = random.Random(1)
        self.men = {}
        self.last = {}
        for u in field.units:
            icon = units[u.regiment.unit]["icon"]
            _, _, count, files, spacing = FIGURES.get(icon, FIGURES["spear"])
            slots = []
            ranks = math.ceil(count / files)
            for k in range(count):
                rank, file = divmod(k, files)
                in_rank = min(files, count - rank * files)
                slots.append(((ranks / 2 - rank - 0.5) * spacing * SCALE * 0.8,
                              (file - (in_rank - 1) / 2) * spacing * SCALE))
            self.men[u.id] = [Man(s, self.rng) for s in slots]
            self.last[u.id] = (u.x, u.y)

    def alive_count(self, u):
        if u.state not in ("ready", "routing"):
            return 0
        full = self.units[u.regiment.unit]["hp"]
        return min(len(self.men[u.id]), max(1, math.ceil(len(self.men[u.id]) * u.regiment.hp / full)))

    def update(self, dt, effects):
        for u in self.field.units:
            men = self.men[u.id]
            want = self.alive_count(u) if u.state != "fled" else 0
            living = [m for m in men if m.alive]
            if u.state == "fled":
                for m in living:
                    m.alive = False  # gone over the edge of the field; nobody falls
                continue
            while len(living) > want:
                m = living.pop(self.rng.randrange(len(living)))
                m.alive = False
                if m.x is not None:
                    self._fall(u, m)
            dead = [m for m in men if not m.alive]
            while len(living) < want and dead:
                m = dead.pop()
                m.alive = True  # healed back into the ranks
                living.append(m)
            routing = u.state == "routing"
            spread = 1.9 if routing else 1.0
            cos, sin = math.cos(u.facing), math.sin(u.facing)
            ease = min(1.0, dt * (5 if routing else 7))
            for m in living:
                fx, fy = m.slot
                tx = u.x + (fx * cos - fy * sin) * spread + m.jx * spread
                ty = u.y + (fx * sin + fy * cos) * spread + m.jy * spread
                if m.x is None:
                    m.x, m.y = tx, ty
                else:
                    m.x += (tx - m.x) * ease
                    m.y += (ty - m.y) * ease
            lx, ly = self.last[u.id]
            moving = math.hypot(u.x - lx, u.y - ly) > 0.01
            self.last[u.id] = (u.x, u.y)
            if moving and living:
                effects.dust(u, living, self.units[u.regiment.unit], dt)

    def _fall(self, u, m):
        icon = self.units[u.regiment.unit]["icon"]
        if icon in ("ghost", "bolt"):
            return  # spirits fade away
        flip = math.cos(u.facing) < 0
        if icon not in ("skull",):
            stain = pygame.Surface((14, 5), pygame.SRCALPHA)
            pygame.draw.ellipse(stain, (90, 24, 18, 110), (0, 0, 8 + self.rng.random() * 6, 4))
            self.decals.blit(stain, (m.x - 5, m.y - 1))
        body = fallen(icon, self.colors[u.side], flip)
        self.decals.blit(body, body.get_rect(center=(m.x, m.y - 1)))

    def sprites(self, time):
        """(y, image, rect) for every man standing, to be drawn in depth order."""
        out = []
        for u in self.field.units:
            if u.state not in ("ready", "routing"):
                continue
            icon = self.units[u.regiment.unit]["icon"]
            color = self.colors[u.side]
            flip = math.cos(u.facing) < 0
            lx, ly = self.last[u.id]
            moving = u.state == "routing" or (u.order is not None and u.fighting is None and u.shooting is None)
            for m in self.men[u.id]:
                if not m.alive or m.x is None:
                    continue
                if u.fighting is not None or u.shooting is not None:
                    beat = (time * (2.2 if u.shooting is not None else 3.0) + m.phase) % 2
                    frame = 4 if beat < 0.6 else 0
                elif moving:
                    frame = int(time * 8 + m.phase) % 4
                else:
                    frame = 0
                image = figure(icon, color, frame, flip)
                x, y = m.x, m.y
                if frame == 4 and u.fighting is not None:
                    x += math.cos(u.facing) * 1.5
                    y += math.sin(u.facing) * 1.5
                if moving and frame in (1, 3):
                    y -= 0.6
                out.append((m.y, image, image.get_rect(midbottom=(round(x), round(y) + 2))))
        return out

    def front(self, u):
        """The men of a regiment nearest its foe, for sparks and arrows."""
        return [m for m in self.men[u.id] if m.alive and m.x is not None]


# --- what flies ------------------------------------------------------------------------------

class Effects:
    def __init__(self, field, units, troops):
        self.field, self.units, self.troops = field, units, troops
        self.rng = random.Random(2)
        self.shots = []  # [x0, y0, x1, y1, start, duration, height, kind]
        self.puffs = []  # [x, y, vx, vy, start, life, r0, r1, color, alpha]
        self.timers = {}
        dust = {"marsh": (90, 110, 96), "forest": (110, 104, 80), "mountains": (150, 144, 132)}
        self.dust_color = dust.get(field.terrain, (176, 158, 116))

    def dust(self, u, living, unit, dt):
        rate = 10 if unit["speed"] >= 7 else 4
        if self.rng.random() < rate * dt:
            m = self.rng.choice(living)
            back = u.facing + math.pi
            self.puffs.append([m.x + math.cos(back) * 4, m.y, math.cos(back) * 6, -4, self.field.time,
                               1.4, 3, 11, self.dust_color, 80])

    def update(self, decals):
        f, now = self.field, self.field.time
        for u in f.units:
            if u.shooting is not None:
                self._shoot(u, f.unit(u.shooting), now)
            elif u.fighting is not None:
                self._clash(u, f.unit(u.fighting), now)
        landed = [s for s in self.shots if now >= s[4] + s[5]]
        for s in landed:
            if s[7] == "arrow" and self.rng.random() < 0.35:
                x, y = s[2], s[3]
                pygame.draw.line(decals, (70, 52, 36), (x, y), (x - 2, y - 4), 1)
            elif s[7] == "shot":
                self.puffs.append([s[2], s[3], 0, -3, now, 0.5, 1, 5, self.dust_color, 90])
        self.shots = [s for s in self.shots if now < s[4] + s[5]]
        self.puffs = [p for p in self.puffs if now < p[4] + p[5]]

    def _due(self, key, now, every):
        if now - self.timers.get(key, -99) >= every:
            self.timers[key] = now
            return True
        return False

    def _shoot(self, u, t, now):
        icon = self.units[u.regiment.unit]["icon"]
        gun = icon == "gun"
        if not self._due(("shot", u.id), now, 0.5 if gun else 0.13):
            return
        mine, theirs = self.troops.front(u), self.troops.front(t)
        if not mine or not theirs:
            return
        a, b = self.rng.choice(mine), self.rng.choice(theirs)
        x0, y0 = a.x + math.cos(u.facing) * 4, a.y - 9
        x1, y1 = b.x + self.rng.uniform(-6, 6), b.y + self.rng.uniform(-4, 4)
        dist = math.hypot(x1 - x0, y1 - y0)
        if gun:
            self.shots.append([x0, y0, x1, y1 - 6, now, 0.12, 0, "shot"])
            self.puffs.append([x0 + math.cos(u.facing) * 3, y0, math.cos(u.facing) * 10, -6, now, 1.6, 2, 10,
                               (226, 226, 220), 150])
        else:
            self.shots.append([x0, y0, x1, y1, now, 0.4 + dist / 520, dist * 0.22 + 10, "arrow"])

    def _clash(self, u, t, now):
        if not self._due(("clash", u.id), now, 0.09):
            return
        mx, my = (u.x + t.x) / 2, (u.y + t.y) / 2
        icon = self.units[u.regiment.unit]["icon"]
        if icon == "wyrm":
            for _ in range(2):
                self.puffs.append([mx + self.rng.uniform(-8, 8), my - 10 + self.rng.uniform(-6, 6),
                                   self.rng.uniform(-10, 10), -14, now, 0.6, 2, 7, (255, 150, 50), 200])
            return
        self.puffs.append([mx + self.rng.uniform(-12, 12), my - 8 + self.rng.uniform(-10, 8),
                           self.rng.uniform(-30, 30), self.rng.uniform(-40, -10), now, 0.22, 1, 1,
                           (255, 236, 170), 255])
        if self.rng.random() < 0.3:
            self.puffs.append([mx + self.rng.uniform(-14, 14), my + self.rng.uniform(-4, 6), 0, -5, now, 1.2, 3, 12,
                               self.dust_color, 70])

    def draw_shadows(self, surface):
        now = self.field.time
        for x0, y0, x1, y1, start, dur, h, kind in self.shots:
            if kind == "arrow":
                p = max(0.0, min(1.0, (now - start) / dur))
                x, y = x0 + (x1 - x0) * p, y0 + 9 + (y1 - y0) * p
                pygame.draw.line(surface, (40, 34, 26), (x - 2, y), (x + 2, y), 1)

    def draw(self, surface):
        now = self.field.time
        for x0, y0, x1, y1, start, dur, h, kind in self.shots:
            p = max(0.0, min(1.0, (now - start) / dur))
            x, y = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p - math.sin(p * math.pi) * h
            if kind == "shot":
                pygame.draw.line(surface, (255, 236, 180), (x, y), (x - (x1 - x0) * 0.08, y - (y1 - y0) * 0.08), 1)
                continue
            # the arrow points along its flight
            dx = (x1 - x0) / dur
            dy = (y1 - y0) / dur - math.cos(p * math.pi) * math.pi * h / dur
            length = math.hypot(dx, dy) or 1
            ux, uy = dx / length, dy / length
            pygame.draw.line(surface, (52, 38, 26), (x - ux * 7, y - uy * 7), (x, y), 1)
            pygame.draw.line(surface, (230, 224, 210), (x - ux * 7, y - uy * 7), (x - ux * 5, y - uy * 5), 1)
        for x, y, vx, vy, start, life, r0, r1, color, alpha in self.puffs:
            k = max(0.0, min(1.0, (now - start) / life))
            r = r0 + (r1 - r0) * k
            a = int(alpha * (1 - k))
            px, py = x + vx * (now - start), y + vy * (now - start)
            if r <= 1.5:
                surface.fill(color, (px, py, 2, 2))
                continue
            blob = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(blob, (*color, a), (r + 1, r + 1), r)
            surface.blit(blob, (px - r - 1, py - r - 1))


# --- the field -------------------------------------------------------------------------------

GROUND = {
    "plains": (128, 146, 76), "hills": (138, 140, 84), "forest": (96, 120, 64), "marsh": (98, 112, 78),
    "mountains": (132, 132, 104),
}
CELL = 4


def paint_field(field):
    """The battlefield, painted once: the lie of the land, its woods, waters, rocks and walls."""
    cols, rows = FIELD_W // CELL, FIELD_H // CELL
    rng = random.Random(sum(map(ord, f"{field.province}{field.terrain}{field.kind}")))
    seed = rng.randrange(1000)
    relief = painter._fbm_field(cols, rows, 18, seed)
    moisture = painter._fbm_field(cols, rows, 26, seed + 7)
    grass = painter._fbm_field(cols, rows, 4, seed + 13, octaves=2)
    base = GROUND.get(field.terrain, GROUND["plains"])

    def zone_weight(kind, x, y):
        w = 0.0
        for z in field.zones:
            if z.kind == kind:
                d = math.hypot(x - z.x, (y - z.y) * (1.33 if kind == "hill" else 1.0)) / z.r
                w = max(w, math.exp(-d * d * 2.2) if kind == "hill" else max(0.0, min(1.0, (1.15 - d) * 4)))
        return w

    height = []
    for r in range(rows):
        for c in range(cols):
            x, y = c * CELL + 2, r * CELL + 2
            h = (relief[r * cols + c] - 0.5) * 0.16 + 0.9 * zone_weight("hill", x, y)
            if field.terrain == "mountains":
                h += 0.15 * (relief[r * cols + c] - 0.5)
            height.append(h)
    small = pygame.Surface((cols, rows))
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            x, y = c * CELL + 2, r * CELL + 2
            dx = height[i + 1 if c < cols - 1 else i] - height[i - 1 if c > 0 else i]
            dy = height[i + cols if r < rows - 1 else i] - height[i - cols if r > 0 else i]
            shade = max(0.6, min(1.35, 1.0 + 3.2 * (dx * 0.7 + dy * 0.7)))
            wet = moisture[i] - 0.5
            color = [base[0] * (1 - 0.2 * wet), base[1] * (1 + 0.06 * wet), base[2] * (1 - 0.1 * wet)]
            g = (grass[i] - 0.5) * 0.12
            color = [v * (1 + g) for v in color]
            forest = zone_weight("forest", x, y)
            marsh = zone_weight("marsh", x, y)
            if forest:
                color = [v * (1 - 0.3 * forest) for v in color]
            if marsh:
                color = [a + (b - a) * marsh for a, b in zip(color, (80, 96, 80))]
            if field.kind == "assault" and x > WALL_X + 10:
                color = [a + (b - a) * 0.45 for a, b in zip(color, (150, 134, 106))]  # trodden town ground
            small.set_at((c, r), tuple(max(0, min(255, int(v * shade))) for v in color))
    ground = pygame.transform.smoothscale(small, (FIELD_W, FIELD_H))

    for z in field.zones:
        if z.kind == "hill":
            _contours(ground, z, base)
    _tufts(ground, rng, base)
    _road(ground, rng, field)
    for z in field.zones:
        if z.kind == "marsh":
            _pools(ground, rng, z)
    for b in field.blocks:
        if b.kind == "rocks":
            _rocks(ground, rng, b)
    if field.kind == "assault":
        _town(ground, rng)
        for b in field.blocks:
            if b.kind == "wall":
                _wall(ground, b)
        _gates(ground)
    trees = []
    for z in field.zones:
        if z.kind == "forest":
            for _ in range(int(z.r * z.r / 70)):
                a, d = rng.uniform(0, 2 * math.pi), z.r * math.sqrt(rng.random()) * 1.05
                trees.append((z.y + math.sin(a) * d, z.x + math.cos(a) * d, rng.random()))
    for y, x, k in sorted(trees):
        _tree(ground, x, y, k)
    tone = pygame.Surface((FIELD_W, FIELD_H))
    tone.fill((255, 246, 228))
    ground.blit(tone, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return ground


def _contours(ground, z, base):
    """A hill's slopes, ring by ring, as on a general's map."""
    layer = pygame.Surface((FIELD_W, FIELD_H), pygame.SRCALPHA)
    for k, f in enumerate((1.0, 0.78, 0.56, 0.34)):
        rect = pygame.Rect(0, 0, 2 * z.r * f, 1.5 * z.r * f)
        rect.center = (z.x, z.y)
        pygame.draw.ellipse(layer, (*_shade(base, 1.18 + 0.05 * k), 34), rect)
        pygame.draw.ellipse(layer, (*_shade(base, 0.6), 70), rect, 2)
    ground.blit(layer, (0, 0))


def _tufts(ground, rng, base):
    dark, light = _shade(base, 0.72), _shade(base, 1.22)
    for _ in range(3200):
        x, y = rng.uniform(0, FIELD_W), rng.uniform(0, FIELD_H)
        color = dark if rng.random() < 0.6 else light
        for k in range(3):
            pygame.draw.line(ground, color, (x + k * 1.5, y), (x + k * 1.5 + rng.uniform(-1.5, 1.5), y - rng.uniform(2, 4)))
    for _ in range(140):  # wild flowers
        x, y = rng.uniform(0, FIELD_W), rng.uniform(0, FIELD_H)
        ground.fill(rng.choice(((236, 220, 120), (230, 230, 236), (200, 120, 160))), (x, y, 2, 2))


def _road(ground, rng, field):
    if field.terrain in ("marsh", "mountains") and field.kind != "assault":
        return
    y0 = FIELD_H * (0.3 if field.kind == "assault" else rng.uniform(0.25, 0.75))
    points = [(x, y0 + math.sin(x / 170 + rng.random()) * 26) for x in range(-20, FIELD_W + 40, 40)]
    pygame.draw.lines(ground, (150, 128, 92), False, points, 22)
    pygame.draw.lines(ground, (170, 148, 108), False, points, 14)
    for x, y in points[::2]:
        pygame.draw.line(ground, (130, 110, 80), (x - 8, y - 3), (x + 8, y - 3), 1)
        pygame.draw.line(ground, (130, 110, 80), (x - 6, y + 4), (x + 10, y + 4), 1)


def _pools(ground, rng, z):
    for _ in range(int(z.r / 9)):
        a, d = rng.uniform(0, 2 * math.pi), z.r * 0.75 * math.sqrt(rng.random())
        x, y = z.x + math.cos(a) * d, z.y + math.sin(a) * d * 0.7
        w, h = rng.uniform(16, 34), rng.uniform(7, 14)
        pygame.draw.ellipse(ground, (62, 80, 66), (x - w / 2 - 2, y - h / 2 - 1, w + 4, h + 3))
        pygame.draw.ellipse(ground, (82, 112, 120), (x - w / 2, y - h / 2, w, h))
        pygame.draw.ellipse(ground, (130, 160, 162), (x - w / 4, y - h / 3, w / 3, h / 4))
    for _ in range(int(z.r)):
        a, d = rng.uniform(0, 2 * math.pi), z.r * math.sqrt(rng.random())
        x, y = z.x + math.cos(a) * d, z.y + math.sin(a) * d
        pygame.draw.line(ground, (66, 86, 50), (x, y), (x + rng.uniform(-1.5, 1.5), y - rng.uniform(5, 10)), 1)


def _rocks(ground, rng, b):
    shadow = pygame.Surface((b.w + 30, b.h + 30), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 70), (8, 14, b.w + 14, b.h + 10))
    ground.blit(shadow, (b.x - 4, b.y - 4))
    for _ in range(int(b.w * b.h / 260) + 3):
        cx, cy = rng.uniform(b.x + 6, b.x + b.w - 6), rng.uniform(b.y + 6, b.y + b.h - 6)
        r = rng.uniform(9, 18)
        pts = [(cx + math.cos(a) * r * rng.uniform(0.75, 1.1), cy + math.sin(a) * r * rng.uniform(0.6, 0.9))
               for a in (k * math.pi / 4 for k in range(8))]
        pygame.draw.polygon(ground, (96, 92, 88), pts)
        lit = [(x, y) for x, y in pts if x - cx + y - cy < r * 0.3]
        if len(lit) >= 3:
            pygame.draw.polygon(ground, (156, 150, 140), lit + [(cx, cy)])
        pygame.draw.polygon(ground, (62, 58, 56), pts, 1)


def _tree(ground, x, y, k):
    r = 6 + 4 * k
    pygame.draw.ellipse(ground, (34, 40, 26), (x - r + 3, y - r * 0.4 + 2, r * 2.2, r * 1.2))  # shadow
    pygame.draw.rect(ground, (78, 56, 36), (x - 1, y - 2, 3, 5))
    green = (44 + int(26 * k), 74 + int(28 * k), 40 + int(10 * k))
    pygame.draw.circle(ground, _shade(green, 0.8), (x, y - r * 0.8), r)
    pygame.draw.circle(ground, green, (x - r * 0.15, y - r * 0.95), r * 0.8)
    pygame.draw.circle(ground, _shade(green, 1.3), (x - r * 0.4, y - r * 1.2), r * 0.38)


def _town(ground, rng):
    for _ in range(9):
        x, y = rng.uniform(WALL_X + 260, FIELD_W - 30), rng.uniform(30, FIELD_H - 40)
        if any(abs(y - g) < 70 for g in (FIELD_H * 0.3, FIELD_H * 0.7)):
            continue
        w, h = rng.uniform(26, 40), rng.uniform(18, 26)
        pygame.draw.rect(ground, (60, 48, 38), (x + 4, y + 4, w, h))  # shadow
        pygame.draw.rect(ground, (196, 184, 160), (x, y, w, h))
        roof = rng.choice(((150, 64, 48), (120, 88, 60), (96, 70, 56)))
        pygame.draw.polygon(ground, roof, [(x - 3, y + h * 0.45), (x + w / 2, y - 8), (x + w + 3, y + h * 0.45)])
        pygame.draw.polygon(ground, _shade(roof, 0.7), [(x + w / 2, y - 8), (x + w + 3, y + h * 0.45),
                                                         (x + w / 2, y + h * 0.45)])
        pygame.draw.rect(ground, (70, 50, 36), (x + w * 0.4, y + h - 9, 6, 9))


def _wall(ground, b):
    x, y, w, h = b.x, b.y, b.w, b.h
    pygame.draw.rect(ground, (50, 44, 40), (x + 6, y + 4, w + 4, h))  # cast shadow
    pygame.draw.rect(ground, (150, 140, 126), (x, y, w, h))
    pygame.draw.rect(ground, (178, 168, 152), (x, y, w * 0.45, h))  # the sunlit side
    for yy in range(int(y), int(y + h), 9):
        offset = 5 if (yy // 9) % 2 else 0
        pygame.draw.line(ground, (118, 110, 100), (x, yy), (x + w, yy), 1)
        pygame.draw.line(ground, (118, 110, 100), (x + offset + 5, yy), (x + offset + 5, yy + 9), 1)
    for yy in range(int(y) + 2, int(y + h) - 4, 12):  # merlons on the outer edge
        pygame.draw.rect(ground, (196, 186, 170), (x - 4, yy, 6, 7))
        pygame.draw.rect(ground, (96, 88, 80), (x - 4, yy, 6, 7), 1)
    pygame.draw.rect(ground, (84, 76, 70), (x, y, w, h), 2)


def _gates(ground):
    from ..game.realtime import GATE_HALF
    for g in (FIELD_H * 0.3, FIELD_H * 0.7):
        for edge in (g - GATE_HALF, g + GATE_HALF):
            tower = pygame.Rect(0, 0, 36, 36)
            tower.center = (WALL_X, edge)
            pygame.draw.rect(ground, (50, 44, 40), tower.move(6, 5))
            pygame.draw.rect(ground, (160, 150, 136), tower)
            pygame.draw.rect(ground, (186, 176, 160), (tower.x, tower.y, 16, tower.h))
            for k in range(4):
                pygame.draw.rect(ground, (200, 190, 174), (tower.x + k * 9, tower.y - 3, 5, 5))
            pygame.draw.rect(ground, (84, 76, 70), tower, 2)
            door = (WALL_X + 14, edge + (10 if edge < g else -24), 22, 14)
            pygame.draw.rect(ground, (104, 70, 40), door)  # an open gate leaf
            pygame.draw.rect(ground, (60, 40, 26), door, 1)


def clouds():
    """Slow cloud shadows drifting over the field: a tile twice the field's width."""
    rng = random.Random(5)
    small = pygame.Surface((FIELD_W // 8, FIELD_H // 8), pygame.SRCALPHA)
    for _ in range(9):
        x, y = rng.uniform(0, FIELD_W / 8), rng.uniform(0, FIELD_H / 8)
        for _ in range(6):
            r = rng.uniform(6, 14)
            pygame.draw.circle(small, (0, 0, 0, 26), (x + rng.uniform(-14, 14), y + rng.uniform(-6, 6)), r)
    image = pygame.transform.smoothscale(small, (FIELD_W, FIELD_H))
    return pygame.transform.smoothscale(pygame.transform.smoothscale(image, (FIELD_W // 2, FIELD_H // 2)),
                                        (FIELD_W, FIELD_H))
