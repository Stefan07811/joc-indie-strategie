"""The diplomacy window: how the other legends feel about you, and what you can offer them."""

import pygame

from ..game import MoveError, diplomacy
from . import theme, tips

BOX = pygame.Rect(0, 0, 900, 700)
BOX.center = theme.MAP_RECT.center
ROW = 110
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
        self.foreign_rect = pygame.Rect(BOX.right - 380, BOX.bottom - 52, 214, 36)
        self.switch = None  # "foreign" to open the foreign courts on closing

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_d, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos):
                return True
            if self.foreign_rect.collidepoint(event.pos):
                self.switch = "foreign"
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
        x, y = BOX.x + 24, BOX.y + 14
        theme.outlined(surface, "Diplomacy", (x, y - 2), 32, theme.GOLD, anchor="topleft")
        theme.text(surface, f"Treasury: {game.treasury[game.player].gold} gold", (BOX.right - 24, y + 8), 22,
                   theme.GOLD, anchor="topright")
        theme.text(surface, "Peace closes borders. Breaking a truce or an alliance is treachery, and every "
                            "legend remembers it.", (x, y + 36), 17, theme.TEXT_DIM)
        y += 60
        others = [f for f in game.factions if f != game.player]
        for fid in others:
            theme.divider(surface, x, BOX.right - 24, y)
            self._row(surface, fid, x, y + 10, mouse)
            y += ROW
        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.button(surface, self.foreign_rect, "Foreign courts  (F)", self.foreign_rect.collidepoint(mouse))
        theme.text(surface, "Esc or D closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")

    def _row(self, surface, fid, x, y, mouse):
        game = self.game
        me = game.player
        width = BOX.width - 48
        color = theme.faction_color(game, fid)
        banner = self.assets.get(f"army_{fid}", color)
        surface.blit(banner, (x, y))
        name = theme.outlined(surface, game.faction_name(fid), (x + 44, y - 4), 21, color, anchor="topleft")
        if fid in game.eliminated:
            theme.text(surface, "Destroyed", (x + width, y), 20, theme.TEXT_DIM, anchor="topright")
            return
        rel = diplomacy.relation(game, me, fid)
        status = {"war": ("At war", theme.DANGER), "peace": ("At peace", theme.PARCHMENT),
                  "alliance": ("Allies", theme.GOOD)}[rel]
        label = status[0]
        truce = game.truce_until.get(diplomacy.key(me, fid), 0) - game.round
        if rel != "war" and truce > 0:
            label += f"  ·  truce for {truce} more season{'s' if truce > 1 else ''}"
        r = theme.text(surface, label, (x + width, y), 20, status[1], anchor="topright")
        theme.tip(r, tips.RELATIONS[rel])

        ai = game.data.factions[fid].get("ai", {})
        r = theme.text(surface, ai.get("personality", ""), (name.right + 12, y + 2), 16, theme.TEXT_DIM)
        theme.tip(r, [ai.get("personality", ""), ai.get("summary", "")])
        score, parts = diplomacy.attitude(game, fid, me)
        word, wcolor = mood_word(score)
        r = theme.text(surface, f"Attitude towards you: {word} ({score:+})", (x + 44, y + 22), 18, wcolor)
        theme.tip(r, tips.attitude(game, fid))
        reasons = ", ".join(f"{name} {points:+}" for name, points in parts) or "nothing in particular"
        reasons = theme.wrap(reasons, 15, width - r.width - 70)
        theme.text(surface, reasons[0] + (" ..." if len(reasons) > 1 else ""), (r.right + 14, y + 25), 15,
                   theme.TEXT_DIM)
        wars = [game.faction_name(f) for f in diplomacy.at_war_with(game, fid) if f != me]
        allies = [game.faction_name(f) for f in diplomacy.allies_of(game, fid) if f != me]
        line = "At war with: " + (", ".join(wars) or "no one else")
        if allies:
            line += "  ·  Allied with: " + ", ".join(allies)
        bonds = []
        k = diplomacy.key(me, fid)
        if k in game.trade:
            bonds.append(f"trade +{diplomacy.trade_income(game, me, fid)} gold a season")
        if k in game.marriages:
            bonds.append("royal marriage")
        if game.vassals.get(fid) == me:
            bonds.append("your vassal")
        elif game.vassals.get(me) == fid:
            bonds.append("your overlord")
        if bonds:
            line += "  ·  " + ", ".join(bonds).capitalize()
        theme.text(surface, line, (x + 44, y + 44), 15, theme.GOLD if bonds else theme.TEXT_DIM)

        buttons = []
        treachery = truce > 0 or k in game.marriages
        if rel == "war":
            buttons = [("Offer peace", lambda: self._offer("peace", fid)),
                       (f"Peace + {BRIBE} gold", lambda: self._offer("peace", fid, BRIBE))]
            if diplomacy.proposal_blocker(game, diplomacy.Proposal("vassal", me, fid)) is None:
                buttons.append(("Demand they kneel", lambda: self._offer("vassal", fid)))
        elif rel == "peace":
            buttons = [("Propose alliance", lambda: self._offer("alliance", fid))]
        elif rel == "alliance":
            buttons = [("Break alliance", lambda: self._break(fid))]
        if rel != "war":
            if k not in game.trade:
                buttons.append(("Trade agreement", lambda: self._offer("trade", fid)))
            if k not in game.marriages and "strigoi" not in (me, fid):
                buttons.append(("Royal marriage", lambda: self._offer("marriage", fid)))
        if rel == "peace":
            buttons.append(("Declare war" + (" (treachery!)" if treachery else ""), lambda: self._war(fid)))
        bx = x + 44
        for label, action in buttons:
            w = theme.serif(16).size(label)[0] + 44
            rect = pygame.Rect(bx, y + 64, w, 28)
            self._button(surface, rect, label, mouse)
            self.actions.append((rect, label, action))
            bx += w + 10
        if fid in self.feedback:
            message, colour = self.feedback[fid]
            theme.text(surface, message, (x + width, y + 68), 18, colour, anchor="topright")

    def _button(self, surface, rect, label, mouse):
        theme.button(surface, rect, label, rect.collidepoint(mouse))
