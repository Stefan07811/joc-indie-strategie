"""The ledger (every army, every province, the treasury month by month), the alerts that call the player's
eye to what matters, and the guide through the first months of a campaign."""

from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

from ..game.rules import BUILDINGS
from .theme import FADED, GOLD, INK, RUBRIC

TABS = [("armies", "Armies"), ("provinces", "Provinces"), ("treasury", "Treasury")]
ROWS = 16


def armies_rows(c, tag):
    rows = []
    for a in c.armies_of(tag):
        prov = c.provmap.at(a.x, a.y)
        where = prov.name if prov else "at sea"
        if a.route is not None:
            end = c.provmap.at(*a.route.end)
            doing = f"marching to {end.name}" if end else "marching"
        elif prov is not None and c.provinces[prov.id].siege and c.provinces[prov.id].siege["by"] == tag:
            doing = "besieging"
        else:
            doing = "camped"
        cmd = c.commander_of(a)
        rows.append((a.id, [a.name, f"{a.men:,}", where, doing, cmd.name if cmd else "-", f"{a.upkeep:,.0f}"]))
    return rows


def province_rows(c, tag):
    rows = []
    for p in sorted(c.provinces_of(tag), key=lambda p: -sum(c.income(p.id))):
        info = c.static(p.id)
        income = sum(c.income(p.id)) + c.trade_income(p.id)
        held = "" if p.controller == tag else f"held by {c.name(p.controller)}"
        works = len(p.buildings)
        rows.append((p.id, [info.name, f"{income:,.0f}", f"{p.population:,.0f}k", f"{p.unrest:.1f}",
                            f"{works}/{len(BUILDINGS)}", held or ("besieged" if p.siege else "")]))
    return rows


class Ledger:
    def __init__(self, theme, parent, aspect, on_army, on_province):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        self.on_army, self.on_province = on_army, on_province
        self.frame = None
        self.tab = "armies"

    @property
    def open(self):
        return self.frame is not None

    def close(self):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

    def toggle(self, c):
        if self.open:
            self.close()
        else:
            self.show(c)

    def show(self, c, tab=None):
        self.close()
        self.tab = tab or self.tab
        a = self.aspect
        self.frame = self.theme.panel(self.parent, -a + 0.35, a - 0.35, -0.82, 0.8)
        left, right = -a + 0.42, a - 0.42
        self.theme.heading(self.frame, f"The Ledger of {c.name(c.player)}", 0, 0.71, scale=0.055,
                           align=TextNode.ACenter)
        x = -0.5
        for key, label in TABS:
            b = self.theme.button(self.frame, label, x, 0.62, self.show, [c, key], width=0.3, scale=0.034)
            b["text_fg"] = GOLD if key == self.tab else INK
            x += 0.34
        self.theme.button(self.frame, "Close (L)", right - 0.15, 0.71, self.close, width=0.26, scale=0.03)
        if self.tab == "treasury":
            return self._treasury(c, left, right)
        if self.tab == "armies":
            heads = ["Army", "Men", "Where", "Doing", "Captain", "Upkeep"]
            widths = [0.42, 0.14, 0.3, 0.28, 0.34, 0.14]
            rows, act = armies_rows(c, c.player), self.on_army
        else:
            heads = ["Province", "Income", "People", "Unrest", "Buildings", ""]
            widths = [0.36, 0.16, 0.16, 0.14, 0.18, 0.5]
            rows, act = province_rows(c, c.player), self.on_province
        scale = (right - left) / sum(widths)
        xs = [left]
        for w in widths[:-1]:
            xs.append(xs[-1] + w * scale)
        y = 0.52
        for x, h in zip(xs, heads):
            self.theme.label(self.frame, h, x, y, scale=0.03, color=FADED)
        y -= 0.07
        for key, cells in rows[:ROWS]:
            self.theme.button(self.frame, cells[0], xs[0], y + 0.012, self._pick, [act, key], width=widths[0] * scale - 0.02,
                              scale=0.026, align="left")
            for x, cell in zip(xs[1:], cells[1:]):
                self.theme.label(self.frame, cell, x, y, scale=0.027,
                                 color=RUBRIC if cell.startswith(("held", "besieged")) else INK)
            y -= 0.075
        if len(rows) > ROWS:
            self.theme.label(self.frame, f"... and {len(rows) - ROWS} more", xs[0], y, scale=0.026, color=FADED)
        if not rows:
            self.theme.label(self.frame, "Nothing to show.", 0, y, scale=0.03, align=TextNode.ACenter)

    def _pick(self, act, key):
        self.close()
        act(key)

    def _treasury(self, c, left, right):
        """The treasury month by month (bars), and this month's accounts."""
        log = c.treasury_log[-48:]
        top, bottom = 0.5, -0.18
        if log:
            most = max(1.0, max(abs(t) for _, _, t, _ in log))
            width = (right - left - 0.6) / max(1, len(log))
            zero = bottom + (top - bottom) * 0.5 if any(t < 0 for _, _, t, _ in log) else bottom
            span = top - zero
            for k, (year, month, treasury, balance) in enumerate(log):
                x = left + k * width
                h = treasury / most * span
                DirectFrame(parent=self.frame, frameColor=(0.62, 0.48, 0.18, 0.9) if treasury >= 0 else
                            (0.65, 0.18, 0.12, 0.9), frameSize=(x, x + width * 0.8, min(zero, zero + h),
                                                                max(zero, zero + h)))
                if month == 1:
                    self.theme.label(self.frame, str(year), x, bottom - 0.05, scale=0.022, color=FADED)
            self.theme.label(self.frame, f"{most:,.0f}", left - 0.02, top, scale=0.022, color=FADED,
                             align=TextNode.ARight)
        else:
            self.theme.label(self.frame, "The ledger fills as the months pass.", left, 0.3, scale=0.03)
        from .model import budget_lines
        lines, balance = budget_lines(c, c.player)
        y = 0.5
        for name, value in lines + [("Each month", balance)]:
            self.theme.label(self.frame, f"{name}: {value:+,.0f}", right - 0.52, y, scale=0.027,
                             color=RUBRIC if value < 0 else INK)
            y -= 0.055


ALERT_WORDS = ("declares war", "besieged by", "lays siege", "falls to", "is born", " dies", "fell in battle",
               "taken in battle", "rise", "crusade", "is no more", "Civil war", "storms", "Mission accomplished",
               "is destroyed", "peace")


STEP = 0.1


class Alerts:
    """Short notes down the right side for what must not be missed; they fade by themselves, and a click
    sends one away."""

    def __init__(self, theme, parent, aspect):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        self.cards = []           # [frame, seconds left, the slot it was drawn in]

    def push(self, text, urgent=False):
        a = self.aspect
        if len(self.cards) >= 4:
            self.cards.pop(0)[0].destroy()
            self._restack()
        slot = len(self.cards)
        y = 0.8 - STEP * slot
        frame = self.theme.panel(self.parent, a - 0.72, a - 0.03, y - 0.085, y, alpha=0.94)
        short = text if len(text) < 120 else text[:117] + "..."
        self.theme.label(frame, short, a - 0.69, y - 0.035, scale=0.026, color=RUBRIC if urgent else INK,
                         wrap=0.64 / 0.026)
        frame.bind("press-mouse1", lambda _: self._dismiss(frame))
        self.cards.append([frame, 12.0, slot])

    def _dismiss(self, frame):
        for card in list(self.cards):
            if card[0] is frame:
                frame.destroy()
                self.cards.remove(card)
        self._restack()

    def _restack(self):
        """Close the gaps: each card moves up to its place in the column."""
        for k, card in enumerate(self.cards):
            card[0].setZ(STEP * (card[2] - k))

    def update(self, dt):
        gone = False
        for card in list(self.cards):
            card[1] -= dt
            if card[1] <= 0:
                card[0].destroy()
                self.cards.remove(card)
                gone = True
        if gone:
            self._restack()

    def from_messages(self, messages):
        for text in messages:
            if any(w in text for w in ALERT_WORDS):
                urgent = any(w in text for w in ("declares war", "besieged", "falls to", "is no more", "rise",
                                                 "Civil war"))
                self.push(text, urgent)

    def clear(self):
        for card in self.cards:
            card[0].destroy()
        self.cards = []


GUIDE = [
    ("The Map", "This is the Balkans in September 1402. Bayezid has just lost everything to Timur at Ankara, "
                "and every prince from Buda to Trebizond is weighing his chances. Drag with the middle button "
                "(or W A S D) to move, the wheel to come closer, Q and E or the right button to turn."),
    ("Your Realm", "Click a province to see its towns, its people and what can be built there. The Realm button "
                   "at the top shows your court, your treasury, your missions and the decisions open to you."),
    ("Armies", "Click one of your armies, then right-click where it should march: the line shows the road, and "
               "the shaded land how far it can go this month. An army that stops at an enemy town besieges it; "
               "when the siege is far enough along you may storm the walls."),
    ("The Month", "Nothing moves until you end the month (Space). Then every realm acts, armies march, sieges "
                  "press on, and the chronicle at the bottom right tells what happened."),
    ("Battles", "When your army meets the enemy you choose: command the battle yourself on the field, leave it "
                "to the captains, or draw off. In battle: choose regiments, right-click to march or attack, "
                "drag with the right button to lay out a line."),
    ("Friends and Foes", "Other realms' opinions of you show in their panel: send gifts, marry your children "
                         "into their houses, make alliances, demand tribute, declare war. Keep an eye on your own "
                         "great men too: if they grow angry, they rise."),
    ("The Ledger", "Press L for the ledger of your armies, provinces and treasury, and 1-6 for the ways of "
                   "looking at the map: realms, the land, faiths, peoples, friends and foes, trade roads. "
                   "Escape opens the menu (save, load, settings). Good fortune."),
]
