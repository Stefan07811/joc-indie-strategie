"""Sprites: a PNG from assets/ if one exists, otherwise a small pixel pattern drawn in code.

To replace a placeholder with real pixel art, drop a PNG with the same name into
legendele/assets/ (e.g. assets/army_zmei.png). See assets/README.md for the names.
"""

from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
PIXEL = 3  # screen pixels per pattern pixel

# Pattern legend: '.' transparent, '#' outline, 'X' faction colour, 'x' darker faction colour,
# 'w' white, 'y' gold, 's' stone, 'S' dark stone, 'r' red, 'b' brown.
PATTERNS = {
    "army": [
        "y.........",
        "#XXXXXXX#.",
        "#XXXXXXX#.",
        "#XXwwwXX#.",
        "#XXwwwXX#.",
        "#XXXwXXX#.",
        "#xXXXXXx#.",
        "#.xXXXx#..",
        "#..xXx#...",
        "#...#.....",
        "#.........",
        "b.........",
    ],
    "castle": [
        "s.s.s...s.s.s",
        "sssss...sssss",
        "sSsss...ssSss",
        "sssssssssssss",
        "ssSsssXsssSss",
        "sssssXXXsssss",
        "ssssSXXXSssss",
    ],
    "heart": [
        "....y....",
        "...yry...",
        "..yrrry..",
        ".yrrwrry.",
        "yrrwrrrry",
        ".yrrrrry.",
        "..yrrry..",
        "...yry...",
        "....y....",
    ],
}


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


class Assets:
    def __init__(self, asset_dir=ASSET_DIR):
        self.asset_dir = Path(asset_dir)
        self._cache = {}

    def get(self, name, color=(200, 200, 200)):
        """Sprite `name` (tinted placeholders are keyed by colour too)."""
        key = (name, tuple(color))
        if key not in self._cache:
            self._cache[key] = self._load(name) or self._draw(name.split("_")[0], color)
        return self._cache[key]

    def _load(self, name):
        path = self.asset_dir / f"{name}.png"
        if not path.exists():
            return None
        image = pygame.image.load(str(path))
        return image.convert_alpha() if pygame.display.get_surface() else image

    def _draw(self, pattern_name, color):
        rows = PATTERNS[pattern_name]
        palette = {
            "#": (34, 26, 22), "X": color, "x": _shade(color, 0.7), "w": (246, 240, 226),
            "y": (232, 186, 70), "s": (176, 168, 156), "S": (128, 120, 110), "r": (210, 52, 60),
            "b": (110, 74, 44),
        }
        surf = pygame.Surface((len(rows[0]) * PIXEL, len(rows) * PIXEL), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    surf.fill(palette[ch], (x * PIXEL, y * PIXEL, PIXEL, PIXEL))
        return surf
