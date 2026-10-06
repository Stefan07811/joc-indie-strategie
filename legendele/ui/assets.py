"""Sprites: a PNG from assets/ if one exists, otherwise a small pixel pattern drawn in code.

To replace a placeholder with real pixel art, drop a PNG with the same name into
legendele/assets/ (e.g. assets/army_zmei.png). See assets/README.md for the names.
"""

from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
PIXEL = 3  # screen pixels per pattern pixel
EMBLEM_AT = (3, 2)  # where a faction's emblem sits on its army banner

# Pattern legend: '.' transparent, '#' outline, 'X' faction colour, 'x' darker faction colour,
# 'w' white, 'y' gold, 's' stone, 'S' dark stone, 'r' red, 'b' brown, 'g' green.
PATTERNS = {
    "army": [
        "y...........",
        "#XXXXXXXXX#.",
        "#XXXXXXXXX#.",
        "#XXXXXXXXX#.",
        "#XXXXXXXXX#.",
        "#XXXXXXXXX#.",
        "#XXXXXXXXX#.",
        "#xXXXXXXXx#.",
        "#.xXXXXXx#..",
        "#..xXXXx#...",
        "#...xXx#....",
        "#....#......",
        "#...........",
        "b...........",
    ],
    # faction emblems (5x5), drawn on banners and shown large on the faction screen
    "emblem_voievodat": ["..w..", "wwwww", "..w..", "..w..", "..w.."],
    "emblem_zmei": ["..r..", ".rr..", ".rry.", "rryrr", ".rrr."],
    "emblem_iele": ["..w..", ".wyw.", "wyyyw", ".wyw.", "..w.."],
    "emblem_strigoi": [".www.", "wwwww", "w.w.w", "wwwww", ".w.w."],
    "emblem_haiduci": ["..ww.", ".www.", "wwww.", "..b..", "..b.."],
    # unit icons (see "icon" in units.json)
    "unit_spear": ["...w...", "..www..", "...b...", "...b...", "...b...", "...b...", "...b...", "...b..."],
    "unit_bow": ["..bbw..", ".b..w..", "b...w..", "b.yyyyy", "b...w..", ".b..w..", "..bbw.."],
    "unit_horse": ["..##....", ".#ss#...", "#ssss##.", "#s#sssss", ".##sssss", "...#ssss", "...#sss.",
                   "...#ss.."],
    "unit_stake": ["...y...", "..yyy..", "...y...", "...b...", "..bbb..", "...b...", "...b...", "...b..."],
    "unit_gun": ["SSSSSS#.", "SSSSSSS#", "SSSSSS#.", "..bbb...", ".b.b.b..", "..bbb..."],
    "unit_whelp": [".X....X.", ".XX..XX.", "..XXXX..", ".XwXXwX.", ".XXXXXX.", "..XrrX..", "...XX..."],
    "unit_mace": ["..y.y..", ".yyyyy.", "..yyy..", ".yyyyy.", "..y.y..", "...b...", "...b...", "...b..."],
    "unit_wyrm": ["X...X...X", "XX.XX.XX.", ".X..X..X.", ".XX.X.XX.", "..XXXXX..", "...XXX...",
                  "..XX.XX.."],
    "unit_imp": [".X.....X.", ".XX...XX.", "..XXXXX..", "..XwXwX..", "..XXXXX..", "...XrX...", "..X...X.."],
    "unit_crown": ["y..y..y", "yy.y.yy", "yyyyyyy", "yryyyry", "yyyyyyy"],
    "unit_flower": ["...w...", "..wyw..", ".wyyyw.", "..wyw..", "...w...", "...g...", "..gg...", "...g..."],
    "unit_tree": ["...g...", "..ggg..", ".ggggg.", "..ggg..", ".ggggg.", "ggggggg", "...b...", "...b..."],
    "unit_star": ["...y...", "...y...", "yyyyyyy", ".yyyyy.", "..yyy..", ".yy.yy.", "yy...yy"],
    "unit_bolt": ["....yy", "...yy.", "..yy..", ".yyyy.", "...yy.", "..yy..", ".yy...", "yy...."],
    "unit_skull": [".wwwww.", "wwwwwww", "w##w##w", "wwwwwww", ".wwwww.", ".w.w.w."],
    "unit_fang": ["#######", "#w###w#", ".w...w.", ".w...w.", "..r....", "..r...."],
    "unit_ghost": ["..www..", ".wwwww.", ".w#w#w.", ".wwwww.", ".wwwww.", ".wwwww.", ".w.w.w."],
    "unit_wolf": ["S.....S", "SS...SS", "SSSSSSS", "SyS.SyS", "SSSSSSS", ".SSSSS.", "..SwS.."],
    "unit_axe": ["..sss..", ".sssss.", ".sss.b.", "..s..b.", ".....b.", ".....b.", ".....b."],
    "castle": [
        "s.s.s...s.s.s",
        "sssss...sssss",
        "sSsss...ssSss",
        "sssssssssssss",
        "ssSsssXsssSss",
        "sssssXXXsssss",
        "ssssSXXXSssss",
    ],
    "camp": [
        "....#....",
        "...#X#...",
        "..#XXX#..",
        ".#XXwXX#.",
        "#XXXwXXX#",
        "#########",
    ],
    "siege": [
        "w.......w",
        ".w.....w.",
        "..w...w..",
        "...w.w...",
        "....w....",
        "...w.w...",
        "..b...b..",
        ".b.....b.",
        "b.......b",
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

    def get(self, name, color=(200, 200, 200), scale=PIXEL):
        """Sprite `name` (tinted placeholders are keyed by colour and size too)."""
        key = (name, tuple(color), scale)
        if key not in self._cache:
            image = self._load(name)
            if image is not None and scale != PIXEL:
                w, h = image.get_size()
                image = pygame.transform.scale(image, (w * scale // PIXEL, h * scale // PIXEL))
            self._cache[key] = image or self._draw(name, color, scale)
        return self._cache[key]

    def _load(self, name):
        path = self.asset_dir / f"{name}.png"
        if not path.exists():
            return None
        image = pygame.image.load(str(path))
        return image.convert_alpha() if pygame.display.get_surface() else image

    def _draw(self, name, color, scale):
        palette = {
            "#": (34, 26, 22), "X": color, "x": _shade(color, 0.7), "w": (246, 240, 226),
            "y": (232, 186, 70), "s": (176, 168, 156), "S": (128, 120, 110), "r": (210, 52, 60),
            "b": (110, 74, 44), "g": (70, 150, 80),
        }
        if name in PATTERNS:
            return _paint(PATTERNS[name], palette, scale)
        base, _, detail = name.partition("_")
        surf = _paint(PATTERNS[base], palette, scale)
        emblem = PATTERNS.get(f"emblem_{detail}") if base == "army" else None
        if emblem:
            surf.blit(_paint(emblem, palette, scale), (EMBLEM_AT[0] * scale, EMBLEM_AT[1] * scale))
        return surf


def _paint(rows, palette, scale):
    width = max(len(row) for row in rows)
    surf = pygame.Surface((width * scale, len(rows) * scale), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.fill(palette[ch], (x * scale, y * scale, scale, scale))
    return surf
