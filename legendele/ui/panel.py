"""The right-hand side panel: date, selection details, chronicle and the End Turn button."""

import pygame

from . import theme

PAD = 16


class Panel:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        rect = theme.PANEL_RECT
        self.end_turn_rect = pygame.Rect(rect.x + PAD, rect.bottom - 64, rect.width - 2 * PAD, 44)

    def draw(self, surface, *, province=None, army=None, mouse=(0, 0)):
        game = self.game
        rect = theme.PANEL_RECT
        pygame.draw.rect(surface, theme.PANEL_BG, rect)
        pygame.draw.line(surface, theme.PANEL_LINE, rect.topleft, rect.bottomleft, 3)
        x, y = rect.x + PAD, rect.y + PAD
        width = rect.width - 2 * PAD

        theme.text(surface, game.date, (x, y), 30, theme.GOLD)
        y += 30
        color = theme.faction_color(game, game.player)
        pygame.draw.rect(surface, color, (x, y + 3, 12, 12))
        owned = len(game.provinces_of(game.player))
        theme.text(surface, f"{game.faction_name(game.player)}  ·  {owned} provinces", (x + 18, y), 20)
        y += 30
        y = self._rule(surface, y)

        if army is not None:
            y = self._army(surface, army, x, y, width)
        elif province is not None:
            y = self._province(surface, game.provinces[province], x, y, width)
        else:
            for line in ("Click one of your banners to select an army,",
                         "then click a highlighted province to march.",
                         "Click any province to inspect it."):
                theme.text(surface, line, (x, y), 18, theme.TEXT_DIM)
                y += 20
            y += 6
        y = self._rule(surface, y)

        self._chronicle(surface, x, y, width, self.end_turn_rect.top - 34)
        theme.text(surface, "Enter: end turn  ·  Right-click / Esc: deselect", (rect.centerx, rect.bottom - 82),
                   16, theme.TEXT_DIM, anchor="center")
        theme.button(surface, self.end_turn_rect, "End Turn", self.end_turn_rect.collidepoint(mouse))

    def _rule(self, surface, y):
        rect = theme.PANEL_RECT
        pygame.draw.line(surface, theme.PANEL_LINE, (rect.x + PAD, y + 4), (rect.right - PAD, y + 4))
        return y + 14

    def _province(self, surface, p, x, y, width):
        game = self.game
        terrain = game.data.terrain[p.terrain]
        theme.text(surface, p.name, (x, y), 28, theme.PARCHMENT)
        y += 28
        theme.text(surface, f"Owner: {game.faction_name(p.owner)}", (x, y), 20,
                   theme.faction_color(game, p.owner) if p.owner else theme.TEXT_DIM)
        y += 22
        theme.text(surface, f"Terrain: {terrain['name']}  ·  march cost {game.enter_cost(game.player, p.id)}",
                   (x, y), 20)
        y += 22
        if p.special == "heart":
            for line in theme.wrap("Hold the Heart and your capital for 8 turns to win a Legendary Victory.",
                                   18, width):
                theme.text(surface, line, (x, y), 18, theme.GOLD)
                y += 19
        capital_of = [f for f in game.turn_order if game.capital_of(f) == p.id]
        if capital_of:
            theme.text(surface, f"Capital of {game.faction_name(capital_of[0])}", (x, y), 18, theme.GOLD)
            y += 20
        armies = game.armies_in(p.id)
        if armies:
            y += 4
            theme.text(surface, "Armies here:", (x, y), 20, theme.TEXT_DIM)
            y += 20
            for a in armies:
                theme.text(surface, f"• {a.general} ({len(a.regiments)} regiments)", (x, y), 18,
                           theme.faction_color(game, a.faction))
                y += 19
        return y + 6

    def _army(self, surface, army, x, y, width):
        game = self.game
        units = game.data.units
        theme.text(surface, army.general, (x, y), 28, theme.PARCHMENT)
        y += 28
        theme.text(surface, f"{game.faction_name(army.faction)}  ·  in {game.provinces[army.province].name}",
                   (x, y), 18, theme.faction_color(game, army.faction))
        y += 22
        if army.faction == game.player:
            theme.text(surface, f"Movement left: {army.moves_left} / {game.data.map['army_moves']}", (x, y), 20)
            y += 24
        counts = {}
        for uid in army.regiments:
            counts[uid] = counts.get(uid, 0) + 1
        for uid, n in counts.items():
            u = units[uid]
            theme.text(surface, f"{n}×  {u['name']}", (x, y), 20)
            theme.text(surface, f"A{u['attack']} D{u['defense']} HP{u['hp']}", (x + width, y + 2), 16,
                       theme.TEXT_DIM, anchor="topright")
            y += 21
        return y + 6

    def _chronicle(self, surface, x, y, width, bottom):
        theme.text(surface, "Chronicle", (x, y), 22, theme.GOLD)
        y += 24
        lines = []
        for entry in reversed(self.game.log):
            lines.extend((line, entry is self.game.log[-1]) for line in theme.wrap(entry, 17, width))
            if len(lines) * 18 > bottom - y:
                break
        for line, latest in lines:
            if y + 18 > bottom:
                break
            theme.text(surface, line, (x, y), 17, theme.TEXT if latest else theme.TEXT_DIM)
            y += 18
