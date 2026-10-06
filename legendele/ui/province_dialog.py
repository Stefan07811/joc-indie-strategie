"""The province window: construct buildings and train regiments."""

import pygame

from ..game import MoveError, economy
from . import theme, tips

BOX = pygame.Rect(0, 0, 880, 600)
BOX.center = theme.MAP_RECT.center
COLUMN = 404


class ProvinceDialog:
    def __init__(self, game, pid, audio=None, assets=None):
        self.game = game
        self.pid = pid
        self.audio = audio
        self.assets = assets
        self.actions = []  # (rect, callable) rebuilt every frame
        self.done_rect = pygame.Rect(BOX.right - 150, BOX.bottom - 52, 126, 36)

    def handle(self, event):
        """Returns True when the window should close."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_rect.collidepoint(event.pos) or not BOX.collidepoint(event.pos):
                return True
            for rect, action in self.actions:
                if rect.collidepoint(event.pos):
                    try:
                        action()
                    except MoveError:
                        pass
                    break
        return False

    def draw(self, surface, mouse):
        game, p = self.game, self.game.provinces[self.pid]
        self.actions = []
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 160))
        surface.blit(veil, theme.MAP_RECT)
        theme.frame(surface, BOX, accent=theme.faction_color(game, p.owner))

        x, y = BOX.x + 24, BOX.y + 18
        theme.outlined(surface, p.name, (x, y - 2), 32, theme.GOLD, anchor="topleft")
        gold, food = economy.province_yield(game, p)
        terrain = game.data.terrain[p.terrain]["name"]
        theme.text(surface, f"{terrain}  ·  yields {gold} gold and {food} food a season", (x, y + 36), 19,
                   theme.TEXT_DIM)
        t = game.treasury[game.player]
        theme.text(surface, f"Treasury: {t.gold} gold  ·  {t.food} food", (BOX.right - 24, y + 8), 22, theme.GOLD,
                   anchor="topright")
        blocked = economy.can_manage(game, game.player, p.id)
        if blocked:
            theme.text(surface, blocked, (BOX.right - 24, y + 36), 19, theme.DANGER, anchor="topright")
        top = y + 70
        theme.divider(surface, x, BOX.right - 24, top - 6)

        self._buildings(surface, p, x, top, mouse)
        self._recruitment(surface, p, x + COLUMN + 24, top, mouse)

        theme.button(surface, self.done_rect, "Done", self.done_rect.collidepoint(mouse))
        theme.text(surface, "Esc or M closes this window", (x, BOX.bottom - 34), 17, theme.TEXT_DIM, anchor="midleft")

    # --- left: buildings -------------------------------------------------------------------

    def _buildings(self, surface, p, x, y, mouse):
        game = self.game
        slots = game.rules["building_slots"]
        theme.text(surface, f"Buildings  ({len(p.buildings)} / {slots} slots)", (x, y), 24, theme.PARCHMENT)
        y += 28
        for bid in p.buildings:
            theme.text(surface, f"• {game.data.buildings[bid]['name']}", (x, y), 19, theme.GOOD)
            y += 21
        if p.construction:
            c = p.construction
            theme.text(surface, f"• {game.data.buildings[c['building']]['name']}  (ready in {c['turns_left']} "
                                f"season{'s' if c['turns_left'] > 1 else ''})", (x, y), 19, theme.HIGHLIGHT)
            y += 21
        if not p.buildings and not p.construction:
            theme.text(surface, "Nothing built yet.", (x, y), 19, theme.TEXT_DIM)
            y += 21
        y += 10
        theme.text(surface, "Construct", (x, y), 22, theme.GOLD)
        y += 26
        for bid, b in game.data.buildings.items():
            if bid in p.buildings or (p.construction and p.construction["building"] == bid):
                continue
            if b.get("faction", game.player) != game.player:
                continue  # another legend's wonder
            reason = economy.building_blocker(game, game.player, p.id, bid)
            rect = pygame.Rect(x, y, COLUMN, 46)
            self._row(surface, rect, f"{b['name']}", f"{b['cost']} gold · {b['turns']} season"
                      + ("s" if b["turns"] > 1 else ""), b["description"], reason, mouse)
            theme.tip(rect, tips.building(game, bid) + ([(reason, theme.DANGER)] if reason else []))
            if reason is None:
                self.actions.append((rect, self._sounding(lambda bid=bid: game.build(game.player, p.id, bid), "build")))
            y += 50

    # --- right: recruitment ----------------------------------------------------------------

    def _recruitment(self, surface, p, x, y, mouse):
        game = self.game
        units = game.data.units
        theme.text(surface, "Recruit", (x, y), 24, theme.PARCHMENT)
        theme.text(surface, "arrive next season", (x + COLUMN, y + 6), 17, theme.TEXT_DIM, anchor="topright")
        y += 30
        for uid in economy.recruitable_units(game, game.player):
            u = units[uid]
            reason = economy.unit_blocker(game, game.player, p.id, uid)
            rect = pygame.Rect(x, y, COLUMN, 42)
            stats = f"A{u['attack']} D{u['defense']} HP{u['hp']} · upkeep {u['upkeep']} · food {economy.appetite(game, uid)}"
            if u["ability"] and u["ability"] != "hero":
                stats += f" · {game.data.abilities[u['ability']]['name']}"
            self._row(surface, rect, u["name"] + ("  (hero)" if u["ability"] == "hero" else ""), f"{u['cost']} gold",
                      stats, reason, mouse, icon=f"unit_{u['icon']}")
            theme.tip(rect, tips.unit(game, uid) + ([(reason, theme.DANGER)] if reason else []))
            if reason is None:
                self.actions.append((rect, self._sounding(lambda uid=uid: game.recruit(game.player, p.id, uid),
                                                          "recruit")))
            y += 46
        y += 6
        limit = game.rules["recruits_per_turn"]
        theme.text(surface, f"In training  ({len(p.recruits)} / {limit})", (x, y), 22, theme.GOLD)
        y += 26
        if not p.recruits:
            theme.text(surface, "No one. Click a regiment above to train it.", (x, y), 18, theme.TEXT_DIM)
        for i, uid in enumerate(p.recruits):
            rect = pygame.Rect(x, y, COLUMN, 24)
            hovered = rect.collidepoint(mouse)
            theme.text(surface, f"• {units[uid]['name']}", (x, y), 19, theme.HIGHLIGHT)
            theme.text(surface, "click to cancel (refund)" if hovered else "", (x + COLUMN, y + 2), 17,
                       theme.DANGER, anchor="topright")
            self.actions.append((rect, self._sounding(lambda i=i: game.cancel_recruit(p.id, i), "click")))
            y += 24

    def _sounding(self, action, sound):
        def act():
            action()  # raises MoveError when refused, and then there is no sound
            if self.audio:
                self.audio.play(sound)
        return act

    def _row(self, surface, rect, title, price, detail, reason, mouse, icon=None):
        enabled = reason is None
        hovered = enabled and rect.collidepoint(mouse)
        theme.row(surface, rect, hovered, enabled)
        left = rect.x + 10
        if icon and self.assets:
            image = self.assets.get(icon, theme.faction_color(self.game, self.game.player), 3)
            if not enabled:
                image = image.copy()
                image.set_alpha(110)
            surface.blit(image, image.get_rect(center=(rect.x + 22, rect.centery)))
            left = rect.x + 42
        color = theme.PARCHMENT if enabled else theme.TEXT_DIM
        theme.text(surface, title, (left, rect.y + 5), 20, color)
        theme.text(surface, price, (rect.right - 10, rect.y + 6), 18, theme.GOLD if enabled else theme.TEXT_DIM,
                   anchor="topright")
        if enabled:
            theme.text(surface, detail, (left, rect.y + 25), 16, theme.TEXT_DIM)
        else:
            theme.text(surface, reason, (left, rect.y + 25), 16, theme.DANGER)
