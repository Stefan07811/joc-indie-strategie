"""The diplomacy window: how the other legends feel about you, and what you can offer them."""

import pygame

from ..game import MoveError, diplomacy
from . import theme

BOX = pygame.Rect(0, 0, 880, 660)
BOX.center = theme.MAP_RECT.center
ROW = 164
BRIBE = 100


def mood_word(score):
    if score >= 30:
        return "Friendly", theme.GOOD
    if score >= 0:
        return "Cordial", theme.HIGHLIGHT
    if score >= -30:
        return "Wary", theme.GOLD
    return "Hostile", theme.DANGER


class DiplomacyDialog:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        self.actions = []  # (rect, label, callable) rebuilt every frame
        self.feedback = {}  # faction -> (message, colour)
        self.done_rect = pygame.Rect(BOX.right - 150, BOX.bottom - 52, 126, 36)

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_d, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos):
                return True
            for rect, _, action in self.actions:
                if rect.collidepoint(event.pos):
                    action()
                    break
        return False

    # --- actions -----------------------------------------------------------------------------

    def _act(self, other, deed):
        try:
            message, colour = deed()
        except MoveError as e:
            message, colour = str(e), theme.DANGER
        self.feedback[other] = (message, colour)

    def _offer(self, kind, other, gold=0):
        def deed():
            accepted = self.game.propose(kind, self.game.player, other, gold)
            return ("They accept!", theme.GOOD) if accepted else ("They refuse.", theme.DANGER)
        self._act(other, deed)

    def _war(self, other):
        def deed():
            self.game.declare_war(self.game.player, other)
            return "War is declared.", theme.DANGER
        self._act(other, deed)

    def _break(self, other):
        def deed():
            self.game.break_alliance(self.game.player, other)
            return "The alliance is over.", theme.GOLD
        self._act(other, deed)

    # --- drawing ---------------------------------------------------------------------------

    def draw(self, surface, mouse):
        game = self.game
        self.actions = []
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 160))
        surface.blit(veil, theme.MAP_RECT)
        theme.frame(surface, BOX)
        x, y = BOX.x + 24, BOX.y + 18
        theme.outlined(surface, "Diplomacy", (x, y - 2), 32, theme.GOLD, anchor="topleft")
        theme.text(surface, f"Treasury: {game.treasury[game.player].gold} gold", (BOX.right - 24, y + 8), 22,
                   theme.GOLD, anchor="topright")
        theme.text(surface, "Peace closes borders. Breaking a truce or an alliance is treachery, and every "
                            "legend remembers it.", (x, y + 38), 17, theme.TEXT_DIM)
        y += 66
        others = [f for f, d in game.data.factions.items() if d["playable"] and f != game.player]
        for fid in others:
            theme.divider(surface, x, BOX.right - 24, y)
            self._row(surface, fid, x, y + 10, mouse)
            y += ROW
        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.text(surface, "Esc or D closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")

    def _row(self, surface, fid, x, y, mouse):
        game = self.game
        me = game.player
        width = BOX.width - 48
        color = theme.faction_color(game, fid)
        banner = self.assets.get(f"army_{fid}", color)
        surface.blit(banner, (x, y))
        theme.outlined(surface, game.faction_name(fid), (x + 44, y - 2), 22, color, anchor="topleft")
        if fid in game.eliminated:
            theme.text(surface, "Destroyed", (x + width, y + 4), 22, theme.TEXT_DIM, anchor="topright")
            return
        rel = diplomacy.relation(game, me, fid)
        status = {"war": ("At war", theme.DANGER), "peace": ("At peace", theme.PARCHMENT),
                  "alliance": ("Allies", theme.GOOD)}[rel]
        label = status[0]
        truce = game.truce_until.get(diplomacy.key(me, fid), 0) - game.round
        if rel != "war" and truce > 0:
            label += f"  ·  truce for {truce} more season{'s' if truce > 1 else ''}"
        theme.text(surface, label, (x + width, y + 4), 22, status[1], anchor="topright")

        ai = game.data.factions[fid].get("ai", {})
        theme.text(surface, f"{ai.get('personality', '')}: {ai.get('summary', '')}", (x + 44, y + 28), 17,
                   theme.TEXT_DIM)
        score, parts = diplomacy.attitude(game, fid, me)
        word, wcolor = mood_word(score)
        theme.text(surface, f"Attitude towards you: {word} ({score:+})", (x + 44, y + 50), 19, wcolor)
        reasons = ", ".join(f"{name} {points:+}" for name, points in parts) or "nothing in particular"
        for i, line in enumerate(theme.wrap(reasons, 16, width - 44)[:2]):
            theme.text(surface, line, (x + 44, y + 72 + 17 * i), 16, theme.TEXT_DIM)
        wars = [game.faction_name(f) for f in diplomacy.at_war_with(game, fid) if f != me]
        allies = [game.faction_name(f) for f in diplomacy.allies_of(game, fid) if f != me]
        line = "At war with: " + (", ".join(wars) or "no one else")
        if allies:
            line += "  ·  Allied with: " + ", ".join(allies)
        theme.text(surface, line, (x + 44, y + 106), 16, theme.TEXT_DIM)

        buttons = []
        if rel == "war":
            buttons = [("Offer peace", lambda: self._offer("peace", fid)),
                       (f"Peace + {BRIBE} gold", lambda: self._offer("peace", fid, BRIBE))]
        elif rel == "peace":
            buttons = [("Propose alliance", lambda: self._offer("alliance", fid)),
                       ("Declare war" + (" (treachery!)" if truce > 0 else ""), lambda: self._war(fid))]
        elif rel == "alliance":
            buttons = [("Break alliance", lambda: self._break(fid))]
        bx = x + 44
        for label, action in buttons:
            w = theme.serif(16).size(label)[0] + 50
            rect = pygame.Rect(bx, y + 124, w, 30)
            self._button(surface, rect, label, mouse)
            self.actions.append((rect, label, action))
            bx += w + 10
        if fid in self.feedback:
            message, colour = self.feedback[fid]
            theme.text(surface, message, (x + width, y + 130), 19, colour, anchor="topright")

    def _button(self, surface, rect, label, mouse):
        theme.button(surface, rect, label, rect.collidepoint(mouse))
