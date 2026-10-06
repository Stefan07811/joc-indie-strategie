"""The foreign courts: the powers beyond the border, their raids, their tribute and their mercenaries."""

import pygame

from ..game import foreign
from . import theme
from .diplomacy_dialog import BOX

ROW = 136


class ForeignDialog:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        self.actions = []  # (rect, callable) rebuilt every frame
        self.feedback = {}  # power -> (message, colour)
        self.done_rect = pygame.Rect(BOX.right - 150, BOX.bottom - 52, 126, 36)

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_f, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos):
                return True
            for rect, action in self.actions:
                if rect.collidepoint(event.pos):
                    action()
                    break
        return False

    def _do(self, power, deed):
        try:
            self.feedback[power] = deed()
        except ValueError as e:
            self.feedback[power] = (str(e), theme.DANGER)

    def _tribute(self, power, pay):
        def deed():
            if pay:
                foreign.start_tribute(self.game, self.game.player, power)
                return "Tribute will be paid each season.", theme.GOLD
            foreign.stop_tribute(self.game, self.game.player, power)
            return "No more tribute.", theme.DANGER
        self._do(power, deed)

    def _hire(self, power, uid):
        def deed():
            foreign.hire(self.game, self.game.player, power, uid)
            return f"The {self.game.data.units[uid]['name']} are on their way.", theme.GOOD
        self._do(power, deed)

    def draw(self, surface, mouse):
        game = self.game
        self.actions = []
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 160))
        surface.blit(veil, theme.MAP_RECT)
        theme.frame(surface, BOX)
        x, y = BOX.x + 24, BOX.y + 18
        theme.outlined(surface, "Foreign Courts", (x, y - 2), 32, theme.GOLD, anchor="topleft")
        theme.text(surface, f"Treasury: {game.treasury[game.player].gold} gold", (BOX.right - 24, y + 8), 22,
                   theme.GOLD, anchor="topright")
        theme.text(surface, "The kingdoms beyond the border do not want the Carpathians, only their gold. "
                            "Pay them, or guard your borders.", (x, y + 38), 17, theme.TEXT_DIM)
        y += 66
        for power in foreign.powers(game):
            theme.divider(surface, x, BOX.right - 24, y)
            self._row(surface, power, x, y + 10, mouse)
            y += ROW
        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.text(surface, "Esc or F closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")

    def _row(self, surface, power, x, y, mouse):
        game = self.game
        me = game.player
        width = BOX.width - 48
        f = game.data.factions[power]
        color = tuple(f["color"])
        surface.blit(self.assets.get(f"army_{power}", color), (x, y))
        theme.outlined(surface, f["name"], (x + 44, y - 2), 22, color, anchor="topleft")
        theme.text(surface, f["description"], (x + 44, y + 26), 16, theme.TEXT_DIM)
        raids = game.raided.get(power, {}).get(me, 0)
        touching = power in foreign.neighbours_of(game, me)
        cost = foreign.tribute_cost(game, power)
        if foreign.pays(game, me, power):
            status, colour = f"You pay {cost} gold a season: their raiders leave you alone", theme.GOLD
        elif touching:
            status, colour = "Their lands touch yours: they may raid you", theme.DANGER
        else:
            status, colour = "Their lands do not touch yours", theme.TEXT_DIM
        theme.text(surface, status, (x + 44, y + 48), 18, colour)
        theme.text(surface, f"Raids on you so far: {raids}", (x + width, y + 4), 18,
                   theme.DANGER if raids else theme.TEXT_DIM, anchor="topright")
        buttons = []
        if foreign.pays(game, me, power):
            buttons.append(("Stop the tribute", lambda: self._tribute(power, False)))
        elif touching:
            buttons.append((f"Pay tribute ({cost} a season)", lambda: self._tribute(power, True)))
        for uid, price in foreign.mercenaries(game, me, power):
            buttons.append((f"Hire {game.data.units[uid]['name']} ({price})", lambda uid=uid: self._hire(power, uid)))
        bx = x + 44
        for label, action in buttons:
            w = theme.serif(16).size(label)[0] + 50
            rect = pygame.Rect(bx, y + 74, w, 30)
            theme.button(surface, rect, label, rect.collidepoint(mouse))
            self.actions.append((rect, action))
            bx += w + 10
        if power in self.feedback:
            message, colour = self.feedback[power]
            theme.text(surface, message, (x + width, y + 80), 18, colour, anchor="topright")
