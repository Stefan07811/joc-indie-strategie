"""The windows of a tactical battle: what is at stake along the top, the clock and its speed, and a card
for each of our regiments along the bottom with its men and its nerve."""

from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

from ..game.rules import UNITS
from .theme import FADED, GOLD, INK, RUBRIC


class BattleHUD:
    def __init__(self, theme, parent, aspect, battle, side, names, actions):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        self.battle, self.side, self.actions = battle, side, actions
        a = aspect
        self.top = theme.panel(parent, -a + 0.02, a - 0.02, 0.84, 0.99)
        theme.heading(self.top, f"Battle of {battle.place}", 0, 0.935, scale=0.05, align=TextNode.ACenter)
        self.sides = theme.label(self.top, "", 0, 0.885, scale=0.032, align=TextNode.ACenter, font=theme.italic)
        self.clock = theme.label(self.top, "", -a + 0.07, 0.93, scale=0.032)
        self.help = theme.label(self.top, "", -a + 0.07, 0.885, scale=0.026, color=FADED)
        x = a - 1.12
        self.buttons = {}
        for key, label, w in (("pause", "Pause", 0.2), ("x1", "×1", 0.1), ("x2", "×2", 0.1), ("x4", "×4", 0.1),
                              ("auto", "Captains, finish it", 0.32)):
            self.buttons[key] = theme.button(self.top, label, x, 0.925, actions[key], width=w, scale=0.03,
                                             align="left")
            x += w + 0.02
        self.retreat = theme.button(self.top, "Sound the retreat", a - 0.42, 0.875, actions["retreat"], width=0.38,
                                    scale=0.028, align="left")
        self.begin = theme.button(parent, "Begin the battle", 0, -0.62, actions["begin"], width=0.6, scale=0.045)
        self.names = names
        self.cards = None
        self.card_units = []
        self.build_cards()

    def build_cards(self):
        if self.cards is not None:
            self.cards.destroy()
        a = self.aspect
        self.cards = DirectFrame(parent=self.parent, frameColor=(0, 0, 0, 0))
        units = [u for u in self.battle.units if u.side == self.side]
        self.card_units = units
        width = min(0.3, (2 * a - 0.1) / max(1, len(units)) - 0.015)
        x = -(len(units) * (width + 0.015)) / 2
        self.bars = {}
        for u in units:
            card = self.theme.panel(self.cards, x, x + width, -0.98, -0.8, alpha=0.93)
            name = UNITS[u.unit].name + (" (general)" if u.general else "")
            self.theme.button(card, name, x + 0.01, -0.835, self.actions["select"], [u.id], width=width - 0.02,
                              scale=0.022, align="left")
            men = self.theme.label(card, "", x + 0.02, -0.89, scale=0.024)
            bar_bg = DirectFrame(parent=card, frameColor=(0.35, 0.3, 0.25, 0.6),
                                 frameSize=(x + 0.02, x + width - 0.02, -0.955, -0.935))
            bar = DirectFrame(parent=card, frameColor=(0.2, 0.5, 0.25, 1),
                              frameSize=(x + 0.02, x + width - 0.02, -0.955, -0.935))
            self.bars[u.id] = (men, bar, x + 0.02, x + width - 0.02, bar_bg)
            x += width + 0.015

    def update(self, speed, paused, selected):
        b = self.battle
        ours = sum(u.men for u in b.units if u.side == self.side and u.alive)
        theirs = sum(u.men for u in b.units if u.side != self.side and u.alive)
        self.sides["text"] = f"{self.names[0]}: {ours:,} men  —  {self.names[1]}: {theirs:,} men"
        minutes = int(b.time // 60)
        self.clock["text"] = ("Deploying" if not b.started else
                              f"{minutes} minutes into the battle" + ("  (paused)" if paused else ""))
        self.help["text"] = ("Choose a regiment, then click where it should stand in your ground."
                             if not b.started else
                             "Left click: choose a regiment. Right click: march there, or attack the enemy clicked.")
        self.buttons["pause"]["text"] = "Go on" if paused else "Pause"
        if b.started:
            self.begin.hide()
        for u in self.card_units:
            men, bar, x0, x1, _ = self.bars[u.id]
            state = {"routing": " — fleeing!", "gone": " — gone", "fighting": " — fighting"}.get(u.state, "")
            men["text"] = f"{u.men:,} men{state}"
            men["text_fg"] = RUBRIC if u.state in ("routing", "gone") else (GOLD if u.id in selected else INK)
            nerve = max(0.0, min(1.0, u.morale / 100.0)) if u.alive else 0.0
            bar["frameSize"] = (x0, x0 + (x1 - x0) * nerve, -0.955, -0.935)
            bar["frameColor"] = (0.2, 0.5, 0.25, 1) if nerve > 0.4 else ((0.75, 0.55, 0.15, 1) if nerve > 0.2
                                                                         else (0.7, 0.15, 0.1, 1))

    def destroy(self):
        for w in (self.top, self.begin, self.cards):
            if w is not None:
                w.destroy()
