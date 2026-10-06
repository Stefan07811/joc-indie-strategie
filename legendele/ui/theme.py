"""Colours, fonts, layout and the drawing kit shared by the screens: dark wood panels in gilded
frames, parchment ribbons for titles, bevelled buttons, gauges and book-face (serif) lettering."""

import math
import random
from pathlib import Path

import pygame

WINDOW_SIZE = (1280, 720)
MAP_RECT = pygame.Rect(0, 0, 960, 720)
PANEL_RECT = pygame.Rect(960, 0, 320, 720)

INK = (40, 30, 24)
PARCHMENT = (234, 222, 192)
PANEL_BG = (38, 31, 27)
PANEL_LINE = (88, 72, 58)
TEXT = (232, 220, 190)
TEXT_DIM = (160, 146, 122)
GOLD = (218, 172, 74)
GOLD_DARK = (134, 98, 40)
GOLD_LIGHT = (250, 220, 140)
WOOD = (66, 46, 32)
HIGHLIGHT = (255, 236, 140)
DANGER = (236, 86, 70)
GOOD = (126, 196, 104)
NEUTRAL = (150, 144, 134)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SERIF = {"regular": "LiberationSerif-Regular.ttf", "bold": "LiberationSerif-Bold.ttf",
         "italic": "LiberationSerif-Italic.ttf"}

_fonts = {}
_outlined = {}


def font(size):
    """The text face: the book serif, scaled so the old layouts (sized for pygame's own font) still fit."""
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(str(FONT_DIR / SERIF["regular"]), max(8, round(size * 0.8)))
    return _fonts[size]


def serif(size, style="bold"):
    """The book-face used for names and titles (bundled Liberation Serif)."""
    key = ("serif", size, style)
    if key not in _fonts:
        _fonts[key] = pygame.font.Font(str(FONT_DIR / SERIF[style]), size)
    return _fonts[key]


def outlined(surface, string, pos, size, color=PARCHMENT, outline=INK, anchor="center", style="bold", width=2):
    """Serif text with a dark outline, readable on any ground (map labels, titles)."""
    key = (string, size, color, outline, style, width)
    if key not in _outlined:
        f = serif(size, style)
        core = f.render(string, True, color)
        edge = f.render(string, True, outline)
        image = pygame.Surface((core.get_width() + 2 * width, core.get_height() + 2 * width), pygame.SRCALPHA)
        for dx in range(-width, width + 1):
            for dy in range(-width, width + 1):
                if dx * dx + dy * dy <= width * width + 1:
                    image.blit(edge, (dx + width, dy + width))
        image.blit(core, (width, width))
        _outlined[key] = image
    image = _outlined[key]
    rect = image.get_rect(**{anchor: pos})
    surface.blit(image, rect)
    return rect


def readable(color):
    """Text sits on dark wood: lift colours too dark to read there (such as a realm's deep red)."""
    lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
    if lum >= 120:
        return color
    k = (120 - lum) / (255 - lum)
    return tuple(round(c + (255 - c) * k) for c in color[:3])


def text(surface, string, pos, size=20, color=TEXT, anchor="topleft", shadow=None, lift=True):
    """Draw `string` with its `anchor` point at `pos`; returns the rect it covered. Colours too dark
    for the wood are lifted, unless `lift` is off (dark ink on parchment)."""
    img = font(size).render(string, True, readable(color) if lift and shadow is None else color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surface.blit(font(size).render(string, True, shadow), rect.move(1, 1))
    surface.blit(img, rect)
    return rect


def wrap(string, size, width):
    lines, line = [], ""
    for word in string.split():
        candidate = f"{line} {word}".strip()
        if font(size).size(candidate)[0] <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# --- the drawing kit --------------------------------------------------------------------------

_textures = {}
_gradients = {}


def _texture(kind):
    """A 256 px tile: dark wood ("wood") or old parchment ("parchment")."""
    if kind not in _textures:
        rng = random.Random(kind)
        base = (58, 42, 31) if kind == "wood" else (226, 210, 172)
        small = pygame.Surface((24, 24))
        for y in range(24):
            for x in range(24):
                k = 1 + rng.uniform(-0.09, 0.09)
                small.set_at((x, y), tuple(min(255, int(c * k)) for c in base))
        tile = pygame.transform.smoothscale(small, (256, 256))
        if kind == "wood":
            for _ in range(260):  # the grain
                y = rng.uniform(0, 256)
                k = rng.uniform(0.82, 1.12)
                color = tuple(min(255, int(c * k)) for c in base)
                points = [(x, y + 2.5 * math.sin(x / rng.uniform(18, 40) + y)) for x in range(-8, 266, 8)]
                pygame.draw.lines(tile, color, False, points, 1)
        else:
            for _ in range(900):  # fibres and stains
                x, y = rng.uniform(0, 256), rng.uniform(0, 256)
                k = rng.uniform(0.86, 1.04)
                tile.fill(tuple(min(255, int(c * k)) for c in base), (x, y, rng.choice((1, 2, 3)), 1))
        _textures[kind] = tile
    return _textures[kind]


def _fill_texture(surface, rect, kind):
    tile = _texture(kind)
    clip = surface.get_clip()
    surface.set_clip(rect.clip(clip) if clip else rect)
    for x in range(rect.x, rect.right, 256):
        for y in range(rect.y, rect.bottom, 256):
            surface.blit(tile, (x, y))
    surface.set_clip(clip)


def _corner(surface, x, y, sx, sy):
    """A gilded corner ornament; (sx, sy) point into the frame."""
    pygame.draw.line(surface, GOLD_LIGHT, (x, y), (x + 16 * sx, y), 2)
    pygame.draw.line(surface, GOLD_LIGHT, (x, y), (x, y + 16 * sy), 2)
    diamond = [(x + 6 * sx, y + 2 * sy), (x + 10 * sx, y + 6 * sy), (x + 6 * sx, y + 10 * sy), (x + 2 * sx, y + 6 * sy)]
    pygame.draw.polygon(surface, GOLD, diamond)
    pygame.draw.polygon(surface, GOLD_DARK, diamond, 1)


def frame(surface, rect, accent=None, kind="wood", corners=True):
    """A panel: dark wood (or parchment) in a gilded frame; `accent` colours a band along the top."""
    rect = pygame.Rect(rect)
    key = ("shadow", rect.size)
    if key not in _gradients:
        shadow = pygame.Surface((rect.width + 12, rect.height + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), shadow.get_rect(), border_radius=10)
        _gradients[key] = shadow
    surface.blit(_gradients[key], (rect.x - 2, rect.y + 4))
    _fill_texture(surface, rect, kind)
    inner = rect.inflate(-10, -10)
    if accent:
        band = pygame.Surface((inner.width, 6), pygame.SRCALPHA)
        band.fill((*accent, 200))
        surface.blit(band, (inner.x, inner.y))
    pygame.draw.rect(surface, INK, rect, 3)
    pygame.draw.rect(surface, GOLD_DARK, rect.inflate(-4, -4), 2)
    pygame.draw.rect(surface, GOLD, rect.inflate(-6, -6), 1)
    pygame.draw.rect(surface, (24, 18, 14) if kind == "wood" else (150, 124, 84), inner, 1)
    if corners and rect.width > 60 and rect.height > 60:
        _corner(surface, rect.x + 5, rect.y + 5, 1, 1)
        _corner(surface, rect.right - 6, rect.y + 5, -1, 1)
        _corner(surface, rect.x + 5, rect.bottom - 6, 1, -1)
        _corner(surface, rect.right - 6, rect.bottom - 6, -1, -1)
    return inner


def ribbon(surface, center, label, size=28, width=None, color=None):
    """A parchment ribbon with folded ends, for titles; returns its rect."""
    words = serif(size, "bold").size(label)
    w = width or words[0] + 70
    h = words[1] + 14
    rect = pygame.Rect(0, 0, w, h)
    rect.center = center
    for side in (-1, 1):  # the folded tails
        x = rect.left if side < 0 else rect.right
        tail = [(x - side * 6, rect.y + 8), (x + side * 22, rect.y + 8), (x + side * 12, rect.centery + 8),
                (x + side * 22, rect.bottom + 8), (x - side * 6, rect.bottom + 8)]
        pygame.draw.polygon(surface, (176, 150, 106), tail)
        pygame.draw.polygon(surface, INK, tail, 2)
    _fill_texture(surface, rect, "parchment")
    if color:
        pygame.draw.line(surface, color, (rect.x + 4, rect.bottom - 5), (rect.right - 5, rect.bottom - 5), 3)
    pygame.draw.rect(surface, INK, rect, 2)
    pygame.draw.rect(surface, (176, 150, 106), rect.inflate(-6, -6), 1)
    outlined(surface, label, (rect.centerx, rect.centery - 1), size, INK, (238, 226, 196), width=1)
    return rect


def divider(surface, x0, x1, y):
    """A gilded rule with a diamond in the middle."""
    pygame.draw.line(surface, GOLD_DARK, (x0, y + 1), (x1, y + 1), 1)
    pygame.draw.line(surface, GOLD, (x0, y), (x1, y), 1)
    cx = (x0 + x1) // 2
    pygame.draw.polygon(surface, GOLD, [(cx - 6, y), (cx, y - 4), (cx + 6, y), (cx, y + 4)])
    pygame.draw.polygon(surface, GOLD_DARK, [(cx - 6, y), (cx, y - 4), (cx + 6, y), (cx, y + 4)], 1)


def gauge(surface, rect, share, color):
    """A bar in a dark inset, with a glint along its top."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (20, 16, 12), rect.inflate(2, 2))
    pygame.draw.rect(surface, (52, 42, 34), rect)
    fill = rect.copy()
    fill.width = round(rect.width * max(0.0, min(1.0, share)))
    if fill.width:
        pygame.draw.rect(surface, color, fill)
        pygame.draw.line(surface, tuple(min(255, c + 60) for c in color), fill.topleft,
                         (fill.right - 1, fill.top))
    pygame.draw.rect(surface, GOLD_DARK, rect.inflate(2, 2), 1)


def _gradient(size, top, bottom):
    key = (size, top, bottom)
    if key not in _gradients:
        w, h = size
        small = pygame.Surface((1, 2))
        small.set_at((0, 0), top)
        small.set_at((0, 1), bottom)
        _gradients[key] = pygame.transform.smoothscale(small, (w, h))
    return _gradients[key]


def button(surface, rect, label, hovered=False, enabled=True):
    """A bevelled wooden button with gilt edges and book-face lettering."""
    rect = pygame.Rect(rect)
    if not enabled:
        top, bottom = (74, 64, 56), (48, 42, 38)
    elif hovered:
        top, bottom = (136, 98, 56), (84, 58, 34)
    else:
        top, bottom = (104, 74, 46), (60, 42, 28)
    pygame.draw.rect(surface, (14, 10, 8), rect.move(0, 2), border_radius=5)
    surface.blit(_gradient(rect.size, top, bottom), rect)
    pygame.draw.line(surface, tuple(min(255, c + 50) for c in top), (rect.x + 3, rect.y + 2), (rect.right - 4, rect.y + 2))
    edge = (GOLD_LIGHT if hovered else GOLD) if enabled else PANEL_LINE
    pygame.draw.rect(surface, INK, rect, 2, border_radius=5)
    pygame.draw.rect(surface, edge, rect.inflate(-4, -4), 1, border_radius=4)
    if rect.width > 70 and rect.height > 26:
        for x in (rect.x + 9, rect.right - 10):  # brass studs
            pygame.draw.circle(surface, GOLD_DARK, (x, rect.centery), 3)
            pygame.draw.circle(surface, edge, (x - 1, rect.centery - 1), 1)
    size = 20 if rect.height >= 34 else 16
    while size > 12 and serif(size).size(label)[0] > rect.width - 30:
        size -= 1
    outlined(surface, label, rect.center, size, (PARCHMENT if hovered else TEXT) if enabled else TEXT_DIM,
             (20, 14, 10), width=1)


def faction_color(game, fid):
    return tuple(game.data.factions[fid]["color"]) if fid else NEUTRAL


def row(surface, rect, hovered=False, enabled=True):
    """A choice in a list: a dark inset that lights up under the mouse."""
    rect = pygame.Rect(rect)
    top, bottom = ((96, 72, 46), (62, 46, 32)) if hovered else ((44, 34, 27), (32, 25, 20))
    surface.blit(_gradient(rect.size, top, bottom), rect)
    pygame.draw.rect(surface, (16, 12, 10), rect, 1)
    pygame.draw.rect(surface, GOLD_LIGHT if hovered else (GOLD_DARK if enabled else PANEL_LINE), rect.inflate(-2, -2), 1)


# --- tooltips --------------------------------------------------------------------------------
# Screens register areas while they draw (tip); the main loop clears them before each frame
# (clear_tips) and shows the one under the mouse after it has rested there a moment (draw_tip).

TIP_DELAY = 0.35
TIP_WIDTH = 300
_tips = []
_tip_hover = {"key": None, "since": 0.0}


def tip(rect, lines):
    """Explain an area of the screen. `lines` is a string or a list of strings / (string, colour);
    the first line is the title."""
    if isinstance(lines, str):
        lines = [lines]
    _tips.append((pygame.Rect(rect), lines))


def clear_tips():
    _tips.clear()


def tip_at(pos):
    for rect, lines in reversed(_tips):
        if rect.collidepoint(pos):
            return rect, lines
    return None


def draw_tip(surface, mouse, now=None):
    import time
    now = time.monotonic() if now is None else now
    hit = tip_at(mouse)
    key = (tuple(hit[0]), str(hit[1])) if hit else None
    if key != _tip_hover["key"]:
        _tip_hover.update(key=key, since=now)
    if hit is None or now - _tip_hover["since"] < TIP_DELAY:
        return None
    rows = []
    for i, line in enumerate(hit[1]):
        string, color = (line, TEXT if i else GOLD) if isinstance(line, str) else line
        size = 19 if i == 0 else 16
        for part in wrap(string, size, TIP_WIDTH - 24) or [""]:
            rows.append((part, color, size))
    height = sum(font(size).get_linesize() for _, _, size in rows) + 18
    width = max(font(size).size(s)[0] for s, _, size in rows) + 26
    box = pygame.Rect(mouse[0] + 16, mouse[1] + 18, max(120, width), height)
    box.clamp_ip(surface.get_rect())
    if box.collidepoint(mouse):
        box.bottom = mouse[1] - 6
        box.clamp_ip(surface.get_rect())
    pygame.draw.rect(surface, (14, 10, 8), box.move(3, 4))
    pygame.draw.rect(surface, (34, 26, 21), box)
    pygame.draw.rect(surface, GOLD_DARK, box, 2)
    pygame.draw.rect(surface, GOLD, box.inflate(-4, -4), 1)
    y = box.y + 9
    for string, color, size in rows:
        text(surface, string, (box.x + 13, y), size, color)
        y += font(size).get_linesize()
    return box


def star(surface, center, r=5, color=GOLD):
    """A small five-pointed star (a general's rank)."""
    cx, cy = center
    points = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        points.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(surface, INK, [(x + 1, y + 1) for x, y in points])
    pygame.draw.polygon(surface, color, points)


def chevrons(surface, pos, n, color=GOLD_LIGHT):
    """A veteran regiment's stripes, stacked upwards from `pos` (bottom-left)."""
    x, y = pos
    for k in range(n):
        yy = y - k * 4
        pygame.draw.lines(surface, INK, False, [(x, yy + 1), (x + 4, yy - 3), (x + 8, yy + 1)], 3)
        pygame.draw.lines(surface, color, False, [(x, yy), (x + 4, yy - 4), (x + 8, yy)], 2)
