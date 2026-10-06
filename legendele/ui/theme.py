"""Colours, fonts, layout and small drawing helpers shared by the screens."""

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
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
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


def text(surface, string, pos, size=20, color=TEXT, anchor="topleft", shadow=None):
    """Draw `string` with its `anchor` point at `pos`; returns the rect it covered."""
    img = font(size).render(string, True, color)
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


def button(surface, rect, label, hovered=False, enabled=True):
    fill = (92, 70, 44) if hovered and enabled else (66, 52, 38)
    pygame.draw.rect(surface, fill, rect, border_radius=4)
    pygame.draw.rect(surface, GOLD if enabled else PANEL_LINE, rect, 2, border_radius=4)
    text(surface, label, rect.center, 24, TEXT if enabled else TEXT_DIM, anchor="center")


def faction_color(game, fid):
    return tuple(game.data.factions[fid]["color"]) if fid else NEUTRAL
