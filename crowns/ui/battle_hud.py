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
        # the orders for the chosen regiments
        self.orders = DirectFrame(parent=parent, frameColor=(0, 0, 0, 0))
        self.order_buttons = {}
        row = [("line", "Line", 0.13), ("deep", "Deep", 0.13), ("wedge", "Wedge", 0.15), ("square", "Square", 0.15),
               ("loose", "Loose", 0.14), ("run", "Run (R)", 0.17), ("hold", "Hold (H)", 0.17),
               ("skirmish", "Skirmish (G)", 0.22), ("halt", "Halt", 0.12)]
        x = -sum(w + 0.012 for _, _, w in row) / 2
        for key, label, w in row:
            if key in ("line", "deep", "wedge", "square", "loose"):
                command, args = actions["formation"], [key]
            else:
                command, args = actions[key], []
            self.order_buttons[key] = theme.button(self.orders, label, x, -0.765, command, args, width=w,
                                                   scale=0.024, align="left")
            x += w + 0.012
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
            men = self.theme.label(card, "", x + 0.02, -0.878, scale=0.022)
            tags = self.theme.label(card, "", x + 0.02, -0.912, scale=0.019, color=FADED)
            bar_bg = DirectFrame(parent=card, frameColor=(0.35, 0.3, 0.25, 0.6),
                                 frameSize=(x + 0.02, x + width - 0.02, -0.955, -0.935))
            bar = DirectFrame(parent=card, frameColor=(0.2, 0.5, 0.25, 1),
                              frameSize=(x + 0.02, x + width - 0.02, -0.955, -0.935))
            self.bars[u.id] = (men, bar, x + 0.02, x + width - 0.02, tags)
            x += width + 0.015

    def update(self, speed, paused, selected):
        b = self.battle
        ours = sum(u.men for u in b.units if u.side == self.side and u.alive)
        theirs = sum(u.men for u in b.units if u.side != self.side and u.alive)
        self.sides["text"] = f"{self.names[0]}: {ours:,} men  —  {self.names[1]}: {theirs:,} men"
        minutes = int(b.time // 60)
        self.clock["text"] = ("Deploying" if not b.started else
                              f"{minutes} minutes into the battle" + ("  (paused)" if paused else ""))
        self.help["text"] = ("Choose regiments (click, shift-click or drag a box), then click where they should "
                             "stand. Right-drag: lay out a line." if not b.started else
                             "Choose: click, shift-click, drag a box, ctrl+A, ctrl+1-9 to keep a group. "
                             "Right click: march or attack. Right-drag: form a line.")
        self.buttons["pause"]["text"] = "Go on" if paused else "Pause"
        if b.started:
            self.begin.hide()
        chosen = [u for u in self.card_units if u.id in selected and u.standing]
        for key, button in self.order_buttons.items():
            if key in ("line", "deep", "wedge", "square", "loose"):
                usable = any(key in u.formations() for u in chosen)
                on = bool(chosen) and all(u.formation == key for u in chosen if key in u.formations())
            elif key == "skirmish":
                usable = any(u.ranged() for u in chosen)
                on = usable and all(u.stance == "skirmish" for u in chosen if u.ranged())
            elif key == "run":
                usable, on = bool(chosen), bool(chosen) and all(u.run for u in chosen)
            elif key == "hold":
                usable, on = bool(chosen), bool(chosen) and all(u.stance == "hold" for u in chosen)
            else:
                usable, on = bool(chosen) and b.started, False
            button["text_fg"] = GOLD if on else (INK if usable else FADED)
            if usable:
                button.show()
            else:
                button.hide()
        if not chosen:
            self.orders.hide()
        else:
            self.orders.show()
        for u in self.card_units:
            men, bar, x0, x1, tags = self.bars[u.id]
            flags = [u.formation] + (["at the run"] if u.run else []) + \
                ([u.stance] if u.stance != "free" else []) + (["tired"] if u.stamina < 35 else [])
            tags["text"] = ", ".join(flags)
            state = {"routing": " — fleeing!", "gone": " — gone", "fighting": " — fighting"}.get(u.state, "")
            men["text"] = f"{u.men:,} men{state}"
            men["text_fg"] = RUBRIC if u.state in ("routing", "gone") else (GOLD if u.id in selected else INK)
            nerve = max(0.0, min(1.0, u.morale / 100.0)) if u.alive else 0.0
            bar["frameSize"] = (x0, x0 + (x1 - x0) * nerve, -0.955, -0.935)
            bar["frameColor"] = (0.2, 0.5, 0.25, 1) if nerve > 0.4 else ((0.75, 0.55, 0.15, 1) if nerve > 0.2
                                                                         else (0.7, 0.15, 0.1, 1))

    def destroy(self):
        for w in (self.top, self.begin, self.cards, self.orders):
            if w is not None:
                w.destroy()
