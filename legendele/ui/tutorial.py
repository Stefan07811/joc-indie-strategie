"""A guided first campaign: an old advisor explains one thing at a time and waits until you have
tried it. It can be skipped at any moment, and switched back on in the settings."""

import math
import time

import pygame

from . import theme

ADVISOR = "Old Neagu, your advisor"


class Step:
    def __init__(self, text, done=None, target=None):
        self.text = text
        self.done = done  # campaign -> bool; None: wait for "Next"
        self.target = target  # campaign -> screen rect to point at, or None


def _capital(c):
    return c.game.data.factions[c.game.player]["capital"]


def _army_moved(c):
    return any(a.moves_left < c.game.data.map["army_moves"] for a in c.game.armies_of(c.game.player))


def _first_army(c):
    mine = {a.id for a in c.game.armies_of(c.game.player)}
    for rect, army_id in c.map.army_rects:
        if army_id in mine:
            return rect.move(c.map.to_screen((0, 0)))
    return None


def _capital_mark(c):
    p = c.game.provinces[_capital(c)]
    x, y = c.map.to_screen((p.x, p.y))
    return pygame.Rect(x - 50, y - 70, 100, 90)


STEPS = [
    Step("Welcome, my lord. These are the Carpathians: four legends fight over them, and the Heart of the "
         "Mountains beats in the middle. Your lands are washed in your colour. Hold any spot for a moment "
         "and I will tell you what it is."),
    Step("First, your armies. Click your general's standard, or press Tab.",
         done=lambda c: c.selected_army is not None, target=_first_army),
    Step("The circles show where the army can march this season, and what it costs: gold for a free road, "
         "red where a battle or a siege waits. Click a circle to march there.",
         done=_army_moved),
    Step("Now your capital. Click it on the map, then Manage province (or press M) to build and recruit.",
         done=lambda c: type(c.dialog).__name__ == "ProvinceDialog", target=_capital_mark),
    Step("Buildings bring gold, food and order; regiments arrive next season. Choose something, then close "
         "the window with Done.",
         done=lambda c: c.dialog is None),
    Step("The other legends are watched here. Peace closes borders, war opens them. Open Diplomacy (or press D).",
         done=lambda c: type(c.dialog).__name__ == "DiplomacyDialog", target=lambda c: c.panel.diplomacy_rect),
    Step("Close it when you are done. Remember: breaking a truce is treachery, and nobody forgets it.",
         done=lambda c: c.dialog is None),
    Step("When your orders are given, end the turn. The others move, a season passes, and I bring you the news.",
         done=lambda c: c.game.round > 0, target=lambda c: c.panel.end_turn_rect),
    Step("Two roads to victory: hold 21 of the 30 provinces, or hold the Heart of the Mountains and your capital "
         "for 8 seasons. Scroll the map with the arrows or the mouse at its edge. Good fortune, my lord!"),
]


class Tutorial:
    BOX = pygame.Rect(0, 0, 600, 176)

    def __init__(self, campaign):
        self.campaign = campaign
        self.index = 0
        self.box = self.BOX.copy()
        self.box.midtop = (theme.MAP_RECT.centerx, 12)
        self.next_rect = pygame.Rect(0, 0, 120, 32)
        self.skip_rect = pygame.Rect(0, 0, 150, 32)
        self.next_rect.bottomright = (self.box.right - 16, self.box.bottom - 12)
        self.skip_rect.bottomleft = (self.box.x + 16, self.box.bottom - 12)

    @property
    def step(self):
        return STEPS[self.index]

    @property
    def finished(self):
        return self.index >= len(STEPS)

    def update(self):
        """Move on once the player has done what the step asks."""
        while not self.finished and self.step.done and self.step.done(self.campaign):
            self.index += 1

    def handle(self, event):
        """True when the event was the tutorial's own (a click on its buttons)."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.skip_rect.collidepoint(event.pos):
            self.index = len(STEPS)
            return True
        if self.step.done is None and self.next_rect.collidepoint(event.pos):
            self.index += 1
            return True
        return self.box.collidepoint(event.pos)

    def draw(self, surface, mouse):
        if self.finished:
            return
        c = self.campaign
        target = self.step.target(c) if self.step.target else None
        if target:
            pulse = 2 + int(2 * (1 + math.sin(time.monotonic() * 5)))
            pygame.draw.rect(surface, theme.INK, pygame.Rect(target).inflate(10 + pulse, 10 + pulse), 5,
                             border_radius=6)
            pygame.draw.rect(surface, theme.HIGHLIGHT, pygame.Rect(target).inflate(10 + pulse, 10 + pulse), 3,
                             border_radius=6)
        lines = theme.wrap(self.step.text, 18, self.box.width - 44)
        self.box.height = 34 + 19 * len(lines) + 54
        self.next_rect.bottomright = (self.box.right - 16, self.box.bottom - 12)
        self.skip_rect.bottomleft = (self.box.x + 16, self.box.bottom - 12)
        inner = theme.frame(surface, self.box, kind="parchment")
        theme.text(surface, f"{ADVISOR}  ·  {self.index + 1} / {len(STEPS)}", (inner.x + 10, inner.y + 4), 16,
                   (110, 76, 40), lift=False)
        y = inner.y + 24
        for line in lines:
            theme.text(surface, line, (inner.x + 10, y), 18, theme.INK, lift=False)
            y += 19
        theme.button(surface, self.skip_rect, "Skip the advice", self.skip_rect.collidepoint(mouse))
        if self.step.done is None:
            last = self.index == len(STEPS) - 1
            theme.button(surface, self.next_rect, "Farewell" if last else "Next", self.next_rect.collidepoint(mouse))
