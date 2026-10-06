"""The legends window: your quests, how far along they are, and the heroes they bring."""

import pygame

from ..game import quests
from . import theme, tips
from .diplomacy_dialog import BOX


class LegendsDialog:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        self.done_rect = pygame.Rect(BOX.right - 150, BOX.bottom - 52, 126, 36)

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_l, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos)
        return False

    def draw(self, surface, mouse):
        game, me = self.game, self.game.player
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 160))
        surface.blit(veil, theme.MAP_RECT)
        theme.frame(surface, BOX)
        x, y = BOX.x + 24, BOX.y + 18
        theme.outlined(surface, "Legends", (x, y - 2), 32, theme.GOLD, anchor="topleft")
        theme.text(surface, "Fulfil a quest and a hero of the old tales rides to your capital.", (x, y + 38), 17,
                   theme.TEXT_DIM)
        y += 70
        for qid in quests.of(game, me):
            y = self._quest(surface, qid, x, y, BOX.width - 48)
        theme.divider(surface, x, BOX.right - 24, y)
        y += 14
        theme.outlined(surface, "Rumours from the other courts", (x, y), 19, theme.GOLD, anchor="topleft", width=1)
        y += 28
        heard = [(fid, qid) for fid in game.turn_order if fid != me for qid in game.quests_done.get(fid, [])]
        if not heard:
            theme.text(surface, "No other legend has fulfilled a quest yet.", (x, y), 17, theme.TEXT_DIM)
        for fid, qid in heard[:5]:
            q = game.data.quests[qid]
            theme.text(surface, f"{game.faction_name(fid)} have won {game.data.units[q['hero']]['name']} "
                                f"({q['title']}).", (x, y), 17, theme.faction_color(game, fid))
            y += 20
        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.text(surface, "Esc or L closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")

    def _quest(self, surface, qid, x, y, width):
        game, me = self.game, self.game.player
        q = game.data.quests[qid]
        hero = game.data.units[q["hero"]]
        done = quests.done(game, me, qid)
        icon = self.assets.get(f"unit_{hero['icon']}", theme.faction_color(game, me), 4)
        surface.blit(icon, (x, y + 4))
        theme.outlined(surface, q["title"], (x + 50, y), 22, theme.GOOD if done else theme.PARCHMENT,
                       anchor="topleft", width=1)
        reward = theme.text(surface, f"Reward: {hero['name']}", (x + width, y + 4), 18, theme.GOLD, anchor="topright")
        theme.tip(reward, tips.unit(game, q["hero"]))
        yy = y + 30
        for line in theme.wrap(q["text"], 17, width - 50):
            theme.text(surface, line, (x + 50, yy), 17, theme.TEXT)
            yy += 19
        have, need = quests.progress(game, me, qid)
        if done:
            theme.text(surface, f"Fulfilled: {hero['name']} has joined you.", (x + 50, yy + 4), 17, theme.GOOD)
        else:
            bar = pygame.Rect(x + 50, yy + 8, 260, 10)
            theme.gauge(surface, bar, have / need if need else 1, theme.GOLD)
            theme.text(surface, f"{have} / {need}", (bar.right + 12, yy + 2), 17, theme.TEXT_DIM)
        return yy + 40
