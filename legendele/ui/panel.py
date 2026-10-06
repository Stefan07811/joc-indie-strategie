"""The right-hand side panel: date, victory progress, selection details, chronicle and buttons."""

import pygame

from . import theme

PAD = 16


class Panel:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        rect = theme.PANEL_RECT
        self.end_turn_rect = pygame.Rect(rect.x + PAD, rect.bottom - 64, rect.width - 2 * PAD, 44)
        self.assault_rect = None  # set while the selected army can storm walls

    def draw(self, surface, *, province=None, army=None, target=None, mouse=(0, 0)):
        game = self.game
        rect = theme.PANEL_RECT
        pygame.draw.rect(surface, theme.PANEL_BG, rect)
        pygame.draw.line(surface, theme.PANEL_LINE, rect.topleft, rect.bottomleft, 3)
        x, y = rect.x + PAD, rect.y + PAD
        width = rect.width - 2 * PAD
        self.assault_rect = None

        theme.text(surface, game.date, (x, y), 30, theme.GOLD)
        y += 30
        y = self._progress(surface, x, y, width)
        y = self._rule(surface, y)

        if army is not None:
            y = self._army(surface, army, x, y, width, target, mouse)
        elif province is not None:
            y = self._province(surface, game.provinces[province], x, y, width)
        else:
            for line in ("Click one of your banners to select an army,",
                         "then click a highlighted province to march.",
                         "Red circles mean a battle or a siege."):
                theme.text(surface, line, (x, y), 18, theme.TEXT_DIM)
                y += 20
            y += 6
        y = self._rule(surface, y)

        self._chronicle(surface, x, y, width, self.end_turn_rect.top - 34)
        theme.text(surface, "Enter: end turn  ·  Tab: next army  ·  Esc: deselect", (rect.centerx, rect.bottom - 82),
                   16, theme.TEXT_DIM, anchor="center")
        theme.button(surface, self.end_turn_rect, "End Turn", self.end_turn_rect.collidepoint(mouse),
                     enabled=not game.over)

    def _progress(self, surface, x, y, width):
        game = self.game
        rules = game.victory_rules
        color = theme.faction_color(game, game.player)
        pygame.draw.rect(surface, color, (x, y + 3, 12, 12))
        theme.text(surface, game.faction_name(game.player), (x + 18, y), 20)
        y += 22
        owned = len(game.provinces_of(game.player))
        theme.text(surface, f"Provinces {owned} / {rules['conquest_provinces']}", (x, y), 18, theme.TEXT_DIM)
        heart = game.heart_turns.get(game.player, 0)
        theme.text(surface, f"Heart held {heart} / {rules['heart_turns']}", (x + width, y), 18,
                   theme.GOLD if heart else theme.TEXT_DIM, anchor="topright")
        return y + 22

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
        bonus = round((terrain["defense"] - 1) * 100)
        theme.text(surface, f"{terrain['name']}  ·  march cost {game.enter_cost(game.player, p.id)}"
                            + (f"  ·  defence +{bonus}%" if bonus else ""), (x, y), 18)
        y += 22
        if p.special == "heart":
            for line in theme.wrap("Hold the Heart and your capital for 8 turns to win a Legendary Victory.",
                                   18, width):
                theme.text(surface, line, (x, y), 18, theme.GOLD)
                y += 19
        capital_of = [f for f in game.data.factions if game.capital_of(f) == p.id]
        if capital_of:
            theme.text(surface, f"Capital of {game.faction_name(capital_of[0])}  ·  walled", (x, y), 18, theme.GOLD)
            y += 20
        if p.garrison:
            who = "Haiduc rebels" if p.owner is None else "Garrison"
            y = self._regiments(surface, f"{who} ({len(p.garrison)}):", p.garrison, x, y, width)
        if p.besieged_by is not None and p.besieged_by in game.armies:
            besieger = game.armies[p.besieged_by]
            theme.text(surface, f"Besieged by {besieger.general}", (x, y), 18, theme.DANGER)
            y += 20
        for a in game.armies_in(p.id):
            theme.text(surface, f"• {a.general} ({len(a.regiments)} regiments)", (x, y), 18,
                       theme.faction_color(game, a.faction))
            y += 19
        return y + 6

    def _army(self, surface, army, x, y, width, target, mouse):
        game = self.game
        theme.text(surface, army.general, (x, y), 28, theme.PARCHMENT)
        y += 28
        theme.text(surface, f"{game.faction_name(army.faction)}  ·  in {game.provinces[army.province].name}",
                   (x, y), 18, theme.faction_color(game, army.faction))
        y += 22
        mine = army.faction == game.player
        if mine:
            theme.text(surface, f"Movement left: {army.moves_left} / {game.data.map['army_moves']}", (x, y), 18)
            y += 22
        y = self._regiments(surface, None, army.regiments, x, y, width)

        if mine and game.besieging(army):
            p = game.provinces[army.province]
            for line in theme.wrap(f"Besieging {p.name}: the defenders starve each season.", 17, width):
                theme.text(surface, line, (x, y), 17, theme.TEXT_DIM)
                y += 18
            y += 4
            self.assault_rect = pygame.Rect(x, y, width, 34)
            theme.button(surface, self.assault_rect, "Assault the walls",
                         self.assault_rect.collidepoint(mouse), enabled=army.moves_left > 0 and not game.over)
            y += 40
            y = self._forecast(surface, game.forecast(army, army.province), x, y)
        elif mine and target is not None:
            y = self._forecast(surface, game.forecast(army, target), x, y, game.provinces[target].name)
        return y + 6

    def _forecast(self, surface, forecast, x, y, place=None):
        if forecast is None:
            return y
        wins, share = forecast
        if wins and share >= 0.7:
            verdict, color = "Decisive victory", theme.GOOD
        elif wins:
            verdict, color = "Costly victory", theme.HIGHLIGHT
        else:
            verdict, color = "Likely defeat", theme.DANGER
        theme.text(surface, f"Forecast{' at ' + place if place else ''}: {verdict}", (x, y), 18, color)
        return y + 22

    def _regiments(self, surface, title, regiments, x, y, width):
        units = self.game.data.units
        if title:
            theme.text(surface, title, (x, y), 18, theme.TEXT_DIM)
            y += 20
        for r in regiments:
            u = units[r.unit]
            theme.text(surface, u["name"], (x, y), 18)
            bar = pygame.Rect(x + width - 90, y + 4, 90, 8)
            share = max(0.0, min(1.0, r.hp / u["hp"]))
            pygame.draw.rect(surface, theme.PANEL_LINE, bar)
            pygame.draw.rect(surface, theme.GOOD if share > 0.5 else theme.HIGHLIGHT if share > 0.25 else theme.DANGER,
                             (bar.x, bar.y, round(bar.width * share), bar.height))
            y += 19
        return y + 4

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
