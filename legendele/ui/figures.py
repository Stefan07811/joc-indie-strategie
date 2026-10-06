"""Painted figures for the campaign map: castles, villages, the Heart's shrine and army standards.

Each is drawn at twice its size and smoothed down, which gives soft, painted-looking edges.
"""

import math
import random

import pygame

from .assets import PATTERNS

SS = 2  # supersampling
STONE, STONE_DARK, STONE_LIGHT = (176, 168, 154), (118, 110, 100), (208, 200, 186)
ROOF, ROOF_DARK = (150, 64, 48), (104, 42, 34)
INK = (36, 28, 22)
CASTLE_SIZE = (60, 50)
VILLAGE_SIZE = (52, 34)


def _finish(surface, size):
    return pygame.transform.smoothscale(surface, size)


def _canvas(size):
    return pygame.Surface((size[0] * SS, size[1] * SS), pygame.SRCALPHA)


def _shadow(s, cx, cy, w, h, alpha=70):
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (20, 14, 8, alpha), shadow.get_rect())
    s.blit(shadow, (cx - w / 2, cy - h / 2))


def _tower(s, x, base, w, h, roof=ROOF):
    body = pygame.Rect(x - w / 2, base - h, w, h)
    pygame.draw.rect(s, STONE, body)
    pygame.draw.rect(s, STONE_DARK, (body.centerx, body.y, w / 2, h))  # shaded side
    pygame.draw.rect(s, STONE_LIGHT, (body.x, body.y, w * 0.22, h))
    pygame.draw.rect(s, INK, body, 2)
    cone = [(body.x - 4, body.y + 2), (body.centerx, body.y - h * 0.55), (body.right + 4, body.y + 2)]
    pygame.draw.polygon(s, roof, cone)
    pygame.draw.polygon(s, tuple(int(c * 0.7) for c in roof), [(body.centerx, body.y - h * 0.55), cone[2], (body.centerx, body.y + 2)])
    pygame.draw.polygon(s, INK, cone, 2)
    pygame.draw.rect(s, INK, (body.centerx - 2, body.y + h * 0.3, 4, 8))  # arrow slit
    return body.centerx, body.y - h * 0.55


def castle(variant=0.0):
    w, h = CASTLE_SIZE
    s = _canvas(CASTLE_SIZE)
    W, H = w * SS, h * SS
    _shadow(s, W / 2 + 6, H - 10, W * 0.95, 22)
    base = H - 10
    # curtain wall with crenellations
    wall = pygame.Rect(W * 0.1, base - 34, W * 0.8, 34)
    pygame.draw.rect(s, STONE, wall)
    pygame.draw.rect(s, STONE_DARK, (wall.centerx + 20, wall.y, wall.width / 2 - 20, wall.height))
    for x in range(int(wall.x), int(wall.right) - 6, 12):
        pygame.draw.rect(s, STONE, (x, wall.y - 7, 7, 8))
        pygame.draw.rect(s, INK, (x, wall.y - 7, 7, 8), 1)
    pygame.draw.rect(s, INK, wall, 2)
    gate = pygame.Rect(0, 0, 18, 22)
    gate.midbottom = (wall.centerx, base)
    pygame.draw.rect(s, (52, 38, 28), gate, border_top_left_radius=9, border_top_right_radius=9)
    pygame.draw.rect(s, INK, gate, 2, border_top_left_radius=9, border_top_right_radius=9)
    # keep and towers
    _tower(s, W * 0.5 + (variant - 0.5) * 8, base - 30, 30, 44)
    _tower(s, W * 0.14, base, 22, 48, ROOF_DARK)
    _tower(s, W * 0.86, base, 22, 48, ROOF_DARK)
    return _finish(s, CASTLE_SIZE)


def flag_top(kind):
    """Where a settlement's flag pole stands, relative to its midbottom."""
    return {"castle": (0, -CASTLE_SIZE[1] + 2), "village": (8, -VILLAGE_SIZE[1] + 4), "shrine": (0, -40)}[kind]


def village(variant=0.0, terrain="plains"):
    rng = random.Random(int(variant * 1000))
    s = _canvas(VILLAGE_SIZE)
    W, H = VILLAGE_SIZE[0] * SS, VILLAGE_SIZE[1] * SS
    _shadow(s, W / 2 + 4, H - 8, W * 0.95, 18, 55)
    roof = (96, 92, 90) if terrain in ("mountains", "hills") and rng.random() < 0.5 else ROOF
    houses = sorted(((rng.uniform(10, W - 34), rng.uniform(H - 40, H - 14)) for _ in range(5)), key=lambda p: p[1])
    church_x = W * 0.62
    for x, y in houses:
        hw, hh = rng.uniform(18, 24), rng.uniform(12, 16)
        body = pygame.Rect(x, y - hh, hw, hh)
        pygame.draw.rect(s, (226, 212, 184), body)
        pygame.draw.rect(s, (178, 162, 136), (body.centerx, body.y, hw / 2, hh))
        pygame.draw.rect(s, INK, body, 2)
        top = [(body.x - 3, body.y + 1), (body.x + hw * 0.3, body.y - hh * 0.75), (body.right - hw * 0.3, body.y - hh * 0.75),
               (body.right + 3, body.y + 1)]
        pygame.draw.polygon(s, roof, top)
        pygame.draw.polygon(s, INK, top, 2)
        pygame.draw.rect(s, (60, 44, 32), (body.x + 4, body.bottom - 7, 4, 7))
    # the church
    nave = pygame.Rect(church_x - 10, H - 34, 20, 22)
    pygame.draw.rect(s, (236, 226, 204), nave)
    pygame.draw.rect(s, (190, 178, 156), (nave.centerx, nave.y, 10, 22))
    pygame.draw.rect(s, INK, nave, 2)
    spire = [(nave.x - 2, nave.y + 1), (nave.centerx, nave.y - 30), (nave.right + 2, nave.y + 1)]
    pygame.draw.polygon(s, (70, 72, 78), spire)
    pygame.draw.polygon(s, INK, spire, 2)
    pygame.draw.line(s, (220, 190, 90), (nave.centerx, nave.y - 30), (nave.centerx, nave.y - 38), 2)
    pygame.draw.line(s, (220, 190, 90), (nave.centerx - 3, nave.y - 35), (nave.centerx + 3, nave.y - 35), 2)
    return _finish(s, VILLAGE_SIZE)


def shrine():
    size = (54, 44)
    s = _canvas(size)
    W, H = size[0] * SS, size[1] * SS
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    for r, a in ((40, 30), (28, 50), (18, 80)):
        pygame.draw.circle(glow, (255, 120, 90, a), (W / 2, H - 34), r)
    s.blit(glow, (0, 0))
    _shadow(s, W / 2 + 4, H - 10, W * 0.9, 18)
    for k in range(7):
        a = math.pi + k * math.pi / 6
        x, y = W / 2 + math.cos(a) * 38, H - 18 + math.sin(a) * 12
        stone = pygame.Rect(0, 0, 9, 22 + (k % 2) * 6)
        stone.midbottom = (x, y + 8)
        pygame.draw.rect(s, STONE, stone, border_radius=3)
        pygame.draw.rect(s, STONE_DARK, (stone.centerx, stone.y, 4, stone.height), border_radius=2)
        pygame.draw.rect(s, INK, stone, 2, border_radius=3)
    crystal = [(W / 2, H - 70), (W / 2 + 10, H - 46), (W / 2, H - 24), (W / 2 - 10, H - 46)]
    pygame.draw.polygon(s, (214, 50, 60), crystal)
    pygame.draw.polygon(s, (255, 150, 140), [crystal[0], crystal[3], (W / 2, H - 46)])
    pygame.draw.polygon(s, INK, crystal, 2)
    return _finish(s, size)


def pennant(color):
    """A small owner's flag for a settlement."""
    s = _canvas((20, 22))
    pygame.draw.line(s, (70, 50, 34), (4, 4), (4, 44), 3)
    flag = [(6, 6), (36, 12), (6, 20)]
    pygame.draw.polygon(s, color, flag)
    pygame.draw.polygon(s, tuple(int(c * 0.7) for c in color), [(6, 13), (36, 12), (6, 20)])
    pygame.draw.polygon(s, INK, flag, 2)
    return _finish(s, (20, 22))


# --- army standards ----------------------------------------------------------------------------

ARMY_SIZE = (40, 50)
SKIN = (226, 186, 150)


def army(faction, color, emblem=None):
    """A general beside the army's standard: the campaign map's army marker."""
    s = _canvas(ARMY_SIZE)
    W, H = ARMY_SIZE[0] * SS, ARMY_SIZE[1] * SS
    dark = tuple(int(c * 0.62) for c in color)
    _shadow(s, W / 2, H - 6, 64, 14, 90)
    # the standard
    pole_x = W - 22
    pygame.draw.line(s, (84, 60, 38), (pole_x, H - 6), (pole_x, 8), 4)
    pygame.draw.circle(s, (230, 190, 80), (pole_x, 8), 4)
    cloth = [(pole_x - 2, 12), (pole_x - 46, 12), (pole_x - 46, 58), (pole_x - 24, 48), (pole_x - 2, 58)]
    pygame.draw.polygon(s, color, cloth)
    pygame.draw.polygon(s, dark, [(pole_x - 46, 40), (pole_x - 46, 58), (pole_x - 24, 48), (pole_x - 2, 58), (pole_x - 2, 40)])
    pygame.draw.polygon(s, INK, cloth, 2)
    if emblem:
        rows = PATTERNS.get(f"emblem_{emblem}")
        if rows:
            px = 6
            ox, oy = pole_x - 24 - len(rows[0]) * px / 2, 16
            palette = {"w": (246, 240, 226), "y": (236, 190, 80), "r": (200, 40, 40), "b": (110, 74, 44)}
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if ch in palette:
                        s.fill(palette[ch], (ox + x * px, oy + y * px, px, px))
    # the general
    fx, base = 30, H - 8
    pygame.draw.line(s, (60, 44, 30), (fx - 6, base), (fx - 4, base - 18), 6)  # legs
    pygame.draw.line(s, (60, 44, 30), (fx + 6, base), (fx + 4, base - 18), 6)
    body = [(fx - 12, base - 18), (fx - 9, base - 46), (fx + 9, base - 46), (fx + 12, base - 18)]
    cloak = (40, 36, 44) if faction == "strigoi" else dark
    pygame.draw.polygon(s, cloak, [(fx - 14, base - 14), (fx - 10, base - 48), (fx + 10, base - 48), (fx + 14, base - 14)])
    pygame.draw.polygon(s, color if faction != "strigoi" else (70, 76, 70), body)
    pygame.draw.polygon(s, INK, body, 2)
    head = (fx, base - 54)
    skin = (214, 218, 206) if faction == "strigoi" else (206, 160, 92) if faction == "zmei" else SKIN
    pygame.draw.circle(s, skin, head, 8)
    pygame.draw.circle(s, INK, head, 8, 2)
    if faction == "voievodat":
        pygame.draw.polygon(s, (150, 152, 160), [(fx - 9, head[1] - 1), (fx, head[1] - 16), (fx + 9, head[1] - 1)])
        pygame.draw.polygon(s, INK, [(fx - 9, head[1] - 1), (fx, head[1] - 16), (fx + 9, head[1] - 1)], 2)
    elif faction == "zmei":
        for side in (-1, 1):
            pygame.draw.line(s, (236, 214, 150), (fx + side * 6, head[1] - 5), (fx + side * 12, head[1] - 15), 3)
    elif faction == "iele":
        pygame.draw.arc(s, dark, (fx - 11, head[1] - 12, 22, 24), 0, math.pi, 5)  # hood
        for k in range(5):
            pygame.draw.circle(s, (250, 236, 120) if k % 2 else (250, 250, 250), (fx - 8 + k * 4, head[1] - 9), 2)
    elif faction == "strigoi":
        pygame.draw.circle(s, INK, (fx - 3, head[1] - 1), 2)
        pygame.draw.circle(s, INK, (fx + 3, head[1] - 1), 2)
    elif faction == "outlaws":  # a tall sheepskin cap with a feather
        pygame.draw.rect(s, (70, 54, 38), (fx - 8, head[1] - 17, 16, 11), border_radius=4)
        pygame.draw.line(s, (236, 230, 210), (fx + 6, head[1] - 14), (fx + 13, head[1] - 24), 2)
    elif faction == "solomonari":  # a wizard's pointed hat and a white beard
        hat = [(fx - 10, head[1] - 4), (fx + 2, head[1] - 26), (fx + 10, head[1] - 4)]
        pygame.draw.polygon(s, dark, hat)
        pygame.draw.polygon(s, INK, hat, 2)
        pygame.draw.polygon(s, (236, 232, 222), [(fx - 5, head[1] + 4), (fx + 5, head[1] + 4), (fx, head[1] + 14)])
    else:
        pygame.draw.ellipse(s, (90, 64, 40), (fx - 12, head[1] - 12, 24, 8))
        pygame.draw.line(s, (200, 60, 50), (fx + 6, head[1] - 10), (fx + 12, head[1] - 20), 2)
    # shield and spear
    pygame.draw.line(s, (96, 70, 44), (fx + 16, base - 4), (fx + 16, base - 72), 3)
    pygame.draw.polygon(s, (200, 204, 210), [(fx + 13, base - 72), (fx + 16, base - 82), (fx + 19, base - 72)])
    shield = pygame.Rect(fx - 22, base - 44, 18, 22)
    pygame.draw.ellipse(s, color, shield)
    pygame.draw.ellipse(s, (226, 186, 90), shield, 3)
    pygame.draw.ellipse(s, INK, shield.inflate(2, 2), 1)
    return _finish(s, ARMY_SIZE)
