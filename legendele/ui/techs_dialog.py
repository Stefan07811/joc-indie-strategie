"""The traditions window: what the realm knows, what it studies, and what it could learn next."""

import pygame

from ..game import techs
from . import theme
from .diplomacy_dialog import BOX

CARD_W, CARD_H, GAP = 266, 92, 12


class TechsDialog:
    def __init__(self, game, audio=None):
        self.game = game
        self.audio = audio
        self.cards = []  # (rect, tech id), rebuilt every frame
        self.message = None
        self.done_rect = pygame.Rect(BOX.right - 150, BOX.bottom - 52, 126, 36)

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_t, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos):
                return True
            for rect, tid in self.cards:
                if rect.collidepoint(event.pos):
                    self.study(tid)
                    break
        return False

    def study(self, tid):
        game = self.game
        try:
            techs.start(game, game.player, tid)
            self.message = (f"The scholars begin {game.data.techs[tid]['name']}.", theme.GOOD)
            if self.audio:
                self.audio.play("build")
        except ValueError as e:
            self.message = (str(e), theme.DANGER)

    def _order(self):
        """Common traditions first, then the realm's own; each list in the order they can be learnt."""
        game, me = self.game, self.game.player
        mine = [t for t, d in game.data.techs.items() if d.get("faction", me) == me]
        depth = {}

        def level(t):
            if t not in depth:
                depth[t] = 1 + max((level(r) for r in game.data.techs[t].get("requires", ())), default=-1)
            return depth[t]
        return sorted(mine, key=lambda t: ("faction" in game.data.techs[t], level(t), game.data.techs[t]["cost"]))

    def draw(self, surface, mouse):
        game, me = self.game, self.game.player
        self.cards = []
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 160))
        surface.blit(veil, theme.MAP_RECT)
        theme.frame(surface, BOX)
        x, y = BOX.x + 24, BOX.y + 18
        theme.outlined(surface, "Traditions", (x, y - 2), 32, theme.GOLD, anchor="topleft")
        theme.text(surface, f"Treasury: {game.treasury[me].gold} gold", (BOX.right - 24, y + 8), 22, theme.GOLD,
                   anchor="topright")
        study = game.studying.get(me)
        if study:
            name = game.data.techs[study["tech"]]["name"]
            line = f"Studying {name}: {study['turns_left']} more season{'s' if study['turns_left'] != 1 else ''}."
        else:
            line = "Nothing is being studied. Choose a tradition: it is paid now and learnt over a few seasons."
        theme.text(surface, line, (x, y + 38), 17, theme.HIGHLIGHT if study else theme.TEXT_DIM)
        top = y + 70
        for i, tid in enumerate(self._order()):
            col, row = i % 3, i // 3
            rect = pygame.Rect(x + col * (CARD_W + GAP), top + row * (CARD_H + 8), CARD_W, CARD_H)
            self._card(surface, rect, tid, mouse)
        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.text(surface, "Esc or T closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")
        if self.message:
            theme.text(surface, self.message[0], (self.done_rect.x - 20, self.done_rect.centery), 18,
                       self.message[1], anchor="midright")

    def _card(self, surface, rect, tid, mouse):
        game, me = self.game, self.game.player
        t = game.data.techs[tid]
        learnt = tid in techs.known(game, me)
        studying = game.studying.get(me, {}).get("tech") == tid
        reason = techs.blocker(game, me, tid)
        ready = reason is None
        hovered = ready and rect.collidepoint(mouse)
        theme.row(surface, rect, hovered, ready or learnt or studying)
        if learnt or studying:
            band = pygame.Surface((rect.width - 4, rect.height - 4), pygame.SRCALPHA)
            band.fill((*(theme.GOOD if learnt else theme.GOLD), 34))
            surface.blit(band, rect.inflate(-4, -4))
        name_color = theme.GOOD if learnt else theme.HIGHLIGHT if studying else (
            theme.PARCHMENT if ready else theme.TEXT_DIM)
        theme.text(surface, t["name"], (rect.x + 10, rect.y + 6), 19, name_color)
        if "faction" in t:
            theme.star(surface, (rect.right - 14, rect.y + 14), 5)
        theme.text(surface, ", ".join(techs.effects(game, tid)), (rect.x + 10, rect.y + 30), 15, theme.GOLD)
        if learnt:
            status, color = "Learnt", theme.GOOD
        elif studying:
            left = game.studying[me]["turns_left"]
            status, color = f"Studying: {left} season{'s' if left != 1 else ''} left", theme.HIGHLIGHT
        elif ready:
            status, color = f"Study: {t['cost']} gold, {t['turns']} seasons", theme.PARCHMENT
        else:
            status, color = reason, theme.DANGER if reason == "Not enough gold" else theme.TEXT_DIM
        theme.text(surface, status, (rect.x + 10, rect.y + 54), 15, color)
        lines = [t["name"], t["description"], (f"{t['cost']} gold  ·  {t['turns']} seasons", theme.GOLD)]
        if t.get("requires"):
            lines.append(("Needs: " + ", ".join(game.data.techs[r]["name"] for r in t["requires"]), theme.TEXT_DIM))
        if "faction" in t:
            lines.append((f"Only for {game.faction_name(me, True)}", theme.HIGHLIGHT))
        theme.tip(rect, lines)
        if ready:
            self.cards.append((rect, tid))
