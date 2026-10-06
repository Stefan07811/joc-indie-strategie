"""Custom battle: any two armies, on any ground, in any weather, outside the campaign."""

import random

import pygame

from ..game import Game
from ..game.battle import Regiment, Side
from ..game.realtime import WEATHER, Battlefield
from . import theme
from .battle_screen import BattleScreen

TERRAINS = ("plains", "hills", "forest", "marsh", "mountains")
WORKS = ("none", "ladders", "ram")
MAX_REGIMENTS = 12
COLUMN = 520


class CustomBattle:
    music = "menu"

    def __init__(self, app, back):
        self.app = app
        self.back = back
        data = app.data
        self.choices = [f for f, d in data.factions.items() if d["playable"]]
        self.enemies = [f for f in data.factions if any(u["faction"] == f for u in data.units.values())]
        self.sides = [{"faction": self.choices[0], "army": []}, {"faction": self.choices[1], "army": []}]
        for side in self.sides:
            side["army"] = self._starter(side["faction"])
        self.terrain = "plains"
        self.kind = "field"
        self.weather = "clear"
        self.night = False
        self.works = "ram"
        self.you = 0  # the side the player leads
        self.result = None
        self.actions = []  # (rect, callable), rebuilt each frame
        cx = theme.WINDOW_SIZE[0] // 2
        self.fight_rect = pygame.Rect(cx + 20, 650, 220, 48)
        self.back_rect = pygame.Rect(cx - 240, 650, 220, 48)

    def _starter(self, fid):
        units = [u for u, d in self.app.data.units.items() if d["faction"] == fid]
        return (units * 3)[:6]

    def _units(self, fid):
        return [u for u, d in self.app.data.units.items() if d["faction"] == fid]

    # --- input -------------------------------------------------------------------------------

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.scene = self.back
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.back_rect.collidepoint(event.pos):
            self.app.audio.play("click")
            self.app.scene = self.back
        elif self.fight_rect.collidepoint(event.pos):
            self.app.audio.play("click")
            if all(side["army"] for side in self.sides):
                self.result = self.fight()
        else:
            for rect, action in self.actions:
                if rect.collidepoint(event.pos):
                    self.app.audio.play("click")
                    action()
                    break

    def _cycle(self, values, current):
        return values[(values.index(current) + 1) % len(values)]

    def set_faction(self, i):
        options = self.choices if i == self.you else self.enemies
        side = self.sides[i]
        side["faction"] = self._cycle(options, side["faction"]) if side["faction"] in options else options[0]
        side["army"] = self._starter(side["faction"])

    def build(self):
        """The two sides, ready for the field: (attacker, defender, the player's side)."""
        units = self.app.data.units
        sides = []
        for i, s in enumerate(self.sides):
            regiments = [Regiment(u, units[u]["hp"]) for u in s["army"]]
            defending = i == 1
            walls = defending and self.kind == "assault"
            side = Side(s["faction"], regiments, "Commander", defense_mult=1.5 if walls else 1.0, walls=walls,
                        creature=self.app.data.factions[s["faction"]]["creature"],
                        storm=self.app.data.factions[s["faction"]].get("traits", {}).get("weather_lords", 1.0))
            if i == 0 and self.kind == "assault":
                side.equipment = {"ladders": self.works != "none", "ram": self.works == "ram"}
            sides.append(side)
        return sides[0], sides[1], self.you

    def field(self, rng=None):
        attacker, defender, you = self.build()
        return Battlefield(attacker, defender, self.app.data.units, self.terrain, self.kind, rng or random.Random(),
                           province="", player_side=you, weather=self.weather, night=self.night)

    def fight(self):
        player = self.sides[self.you]["faction"]
        game = Game.new(self.app.data, player if self.app.data.factions[player]["playable"] else self.choices[0])
        title = "Custom battle: " + ("assault" if self.kind == "assault" else self.terrain)
        return BattleScreen(self.app, game, self.field(), title=title).run()

    # --- drawing -----------------------------------------------------------------------------

    def draw(self, surface):
        from .menus import _backdrop
        _backdrop(self.app, surface, 200)
        mouse = pygame.mouse.get_pos()
        self.actions = []
        cx = theme.WINDOW_SIZE[0] // 2
        theme.outlined(surface, "Custom Battle", (cx, 34), 40, theme.GOLD, width=2)
        for i in (0, 1):
            self._side(surface, i, 40 + i * (COLUMN + 160), 70, mouse)
        self._ground(surface, cx, 470, mouse)
        theme.button(surface, self.back_rect, "Back", self.back_rect.collidepoint(mouse))
        ready = all(side["army"] for side in self.sides)
        theme.button(surface, self.fight_rect, "Fight!", self.fight_rect.collidepoint(mouse) and ready, enabled=ready)
        if self.result:
            won = self.result.attacker_won == (self.you == 0)
            theme.outlined(surface, "Last battle: " + ("victory" if won else "defeat"), (cx, 620), 20,
                           theme.GOOD if won else theme.DANGER)

    def _side(self, surface, i, x, y, mouse):
        data = self.app.data
        side = self.sides[i]
        fid = side["faction"]
        box = pygame.Rect(x, y, COLUMN, 380)
        inner = theme.frame(surface, box, accent=tuple(data.factions[fid]["color"]))
        role = ("Attacker" if i == 0 else "Defender") + ("  (you)" if i == self.you else "")
        theme.text(surface, role, (inner.x + 12, inner.y + 10), 18, theme.TEXT_DIM)
        rect = pygame.Rect(inner.x + 120, inner.y + 4, 260, 32)
        theme.button(surface, rect, data.factions[fid]["name"], rect.collidepoint(mouse))
        self.actions.append((rect, lambda i=i: self.set_faction(i)))
        theme.tip(rect, ["Faction", "Click to change." + ("" if i == self.you else
                                                           " Your foe may also be a foreign power or the Rebels.")])
        # the regiments picked
        theme.text(surface, f"Army ({len(side['army'])} / {MAX_REGIMENTS})  ·  click to remove",
                   (inner.x + 12, inner.y + 46), 16, theme.GOLD)
        for k, uid in enumerate(side["army"]):
            r = pygame.Rect(inner.x + 12 + (k % 3) * 164, inner.y + 68 + (k // 3) * 30, 158, 26)
            hovered = r.collidepoint(mouse)
            theme.row(surface, r, hovered)
            icon = self.app.assets.get(f"unit_{data.units[uid]['icon']}", tuple(data.factions[fid]["color"]), 2)
            surface.blit(icon, icon.get_rect(center=(r.x + 12, r.centery)))
            theme.text(surface, data.units[uid]["name"], (r.x + 24, r.y + 5), 15,
                       theme.DANGER if hovered else theme.PARCHMENT)
            self.actions.append((r, lambda i=i, k=k: self.sides[i]["army"].pop(k)))
        # the units on offer
        theme.text(surface, "Add a regiment", (inner.x + 12, inner.y + 196), 16, theme.GOLD)
        for k, uid in enumerate(self._units(fid)):
            r = pygame.Rect(inner.x + 12 + (k % 3) * 164, inner.y + 218 + (k // 3) * 32, 158, 28)
            full = len(side["army"]) >= MAX_REGIMENTS
            theme.button(surface, r, data.units[uid]["name"], r.collidepoint(mouse) and not full, enabled=not full)
            theme.tip(r, [data.units[uid]["name"], data.units[uid].get("description", "")])
            if not full:
                self.actions.append((r, lambda i=i, uid=uid: self.sides[i]["army"].append(uid)))

    def _ground(self, surface, cx, y, mouse):
        options = [
            ("Ground", self.app.data.terrain[self.terrain]["name"],
             lambda: setattr(self, "terrain", self._cycle(TERRAINS, self.terrain))),
            ("Battle", "Assault on walls" if self.kind == "assault" else "Field battle",
             lambda: setattr(self, "kind", "field" if self.kind == "assault" else "assault")),
            ("Weather", WEATHER[self.weather]["name"],
             lambda: setattr(self, "weather", self._cycle(list(WEATHER), self.weather))),
            ("Hour", "Night" if self.night else "Day", lambda: setattr(self, "night", not self.night)),
            ("You lead", "the attackers" if self.you == 0 else "the defenders", self._swap),
        ]
        if self.kind == "assault":
            options.append(("Siege works", self.works.capitalize(),
                            lambda: setattr(self, "works", self._cycle(WORKS, self.works))))
        width = 196
        left = cx - (len(options) * (width + 8)) // 2
        for k, (label, value, action) in enumerate(options):
            x = left + k * (width + 8)
            theme.text(surface, label, (x + width // 2, y), 17, theme.TEXT_DIM, anchor="midtop")
            r = pygame.Rect(x, y + 22, width, 36)
            theme.button(surface, r, value, r.collidepoint(mouse))
            self.actions.append((r, action))

    def _swap(self):
        self.you = 1 - self.you
        mine = self.sides[self.you]
        if mine["faction"] not in self.choices:
            mine["faction"] = self.choices[0]
            mine["army"] = self._starter(mine["faction"])
