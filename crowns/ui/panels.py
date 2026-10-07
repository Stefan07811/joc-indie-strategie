"""The campaign's windows: the bar along the top, the side panel (a province, an army or a realm), the
month's chronicle, and dialogs (offers of peace, battles, the choice of a realm)."""

from panda3d.core import TextNode

from . import model
from .theme import FADED, GOLD, INK, RUBRIC

LINE = 0.042


class TopBar:
    def __init__(self, theme, parent, aspect, on_end_month, on_realm):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        a = aspect
        self.frame = theme.panel(parent, -a + 0.02, a - 0.02, 0.87, 0.99)
        self.realm = theme.heading(self.frame, "", -a + 0.07, 0.935, scale=0.042)
        self.ruler = theme.label(self.frame, "", -a + 0.07, 0.897, scale=0.032, font=theme.italic)
        self.date = theme.heading(self.frame, "", 0, 0.918, scale=0.06, align=TextNode.ACenter)
        self.money = theme.label(self.frame, "", a - 0.07, 0.932, scale=0.036, align=TextNode.ARight)
        self.men = theme.label(self.frame, "", a - 0.07, 0.897, scale=0.032, align=TextNode.ARight, color=FADED)
        self.end = theme.button(parent, "End the month  (Space)", a - 0.33, -0.93, on_end_month, width=0.56,
                                scale=0.04)
        self.realm_button = theme.button(self.frame, "Realm", -0.62, 0.918, on_realm, width=0.2, scale=0.032)

    def update(self, c):
        if c.player is None:
            self.realm.setText("Choose your realm")
            self.ruler.setText("Click a land on the map, then 'Play as'")
            self.date["text"] = str(c.date)
            self.money["text"] = ""
            self.men["text"] = ""
            return
        t = model.top_bar(c)
        self.realm["text"] = t["realm"]
        self.ruler["text"] = t["ruler"]
        self.date["text"] = t["date"]
        self.money["text"] = f"Treasury {t['treasury']} ducats ({t['balance']} a month)"
        war = f" · at war ({t['wars']})" if t["wars"] else ""
        self.men["text"] = f"{t['manpower']} men to call · prestige {t['prestige']}{war}"
        self.men["text_fg"] = RUBRIC if t["wars"] else FADED

    def show_end(self, on):
        if on:
            self.end.show()
        else:
            self.end.hide()


class SidePanel:
    """One sheet on the left of the screen, rebuilt whenever what it shows changes."""

    def __init__(self, theme, parent, aspect, actions):
        self.theme, self.parent, self.aspect, self.actions = theme, parent, aspect, actions
        self.frame = None
        self.subject = None
        self.tab = "build"
        self.realm_tab = "treasury"

    @property
    def left(self):
        return -self.aspect + 0.02

    @property
    def right(self):
        return -self.aspect + 1.02

    def close(self):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None
        self.subject = None

    def _open(self):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = self.theme.panel(self.parent, self.left, self.right, -0.97, 0.85)
        self.y = 0.78
        self.theme.button(self.frame, "×", self.right - 0.06, 0.8, self.actions["close"], width=0.06, scale=0.04)

    def _text(self, text, scale=0.034, color=INK, font=None, wrap=0.9, gap=None):
        lab = self.theme.label(self.frame, text, self.left + 0.05, self.y, scale=scale, color=color, font=font,
                               wrap=wrap / scale)
        try:
            lines = max(1, lab.component("text0").textNode.getNumRows())
        except Exception:   # noqa: BLE001 - an estimate will do
            lines = max(1, text.count("\n") + 1, int(len(text) * scale * 0.48 / wrap) + 1)
        self.y -= max(gap or 0.0, scale * 1.2 * lines + 0.008)
        return lab

    def _heading(self, text, scale=0.05):
        self.theme.heading(self.frame, text, self.left + 0.05, self.y, scale=scale)
        self.y -= scale * 1.3

    def _rule(self):
        self.theme.rule(self.frame, self.left + 0.05, self.right - 0.05, self.y + 0.018, 0.002, color=GOLD)
        self.y -= 0.02

    def _button(self, text, command, args=(), ok=True, why=None, scale=0.03):
        """A full-width button; when it cannot be pressed, the reason is written small beneath it."""
        self.theme.button(self.frame, text, self.left + 0.05, self.y, command, args, width=0.9, scale=scale,
                          enabled=ok, align="left")
        self.y -= 0.05
        if not ok and why:
            self.theme.label(self.frame, why, (self.left + self.right) / 2, self.y + 0.012, scale=0.022,
                             color=FADED, align=TextNode.ACenter)
            self.y -= 0.022

    # --- a province ------------------------------------------------------------------------------

    def show_province(self, c, pid):
        self.subject = ("province", pid)
        v = model.province_view(c, pid)
        self._open()
        self._heading(v["name"])
        self._text(v["owner"], font=self.theme.italic)
        if v["held"]:
            self._text(v["held"], color=RUBRIC)
        for line in v["lines"]:
            self._text(line, scale=0.03)
        if v["siege"]:
            self._text(v["siege"], color=RUBRIC, scale=0.032)
        self._rule()
        self._text("Buildings: " + (", ".join(v["buildings"]) if v["buildings"] else "none yet") +
                   f"  ({v['slots']})", scale=0.03)
        if v["works"]:
            self._text(v["works"], scale=0.03, color=GOLD)
        owner = c.provinces[pid].owner
        self._button(f"About {c.name(owner)}", self.actions["realm"], [owner], scale=0.03)
        if not v["mine"]:
            return
        self._rule()
        self.theme.button(self.frame, "Build", self.left + 0.05, self.y, self.actions["tab"], ["build", pid],
                          width=0.43, scale=0.032, enabled=self.tab != "build", align="left")
        self.theme.button(self.frame, "Raise troops", self.left + 0.52, self.y, self.actions["tab"],
                          ["recruit", pid], width=0.43, scale=0.032, enabled=self.tab != "recruit", align="left")
        self.y -= 0.065
        rows = v["build"] if self.tab == "build" else v["recruit"]
        for row in rows:
            if self.y < -0.92:
                break
            if self.tab == "build":
                self._button(row["label"], self.actions["build"], [pid, row["kind"]], row["ok"], row["why"])
            else:
                self._button(row["label"], self.actions["recruit"], [pid, row["unit"]], row["ok"], row["why"])

    # --- an army ---------------------------------------------------------------------------------

    def show_army(self, c, army):
        self.subject = ("army", army.id)
        v = model.army_view(c, army)
        self._open()
        self._heading(v["name"], scale=0.045)
        self._text(v["owner"], font=self.theme.italic)
        self._text(v["men"] + " · " + v["upkeep"], scale=0.032)
        self._text(v["commander"], scale=0.028, color=FADED)
        self._rule()
        for row in v["rows"]:
            self._text(row, scale=0.03)
        self._rule()
        self._text(v["march"], scale=0.032)
        if v["orders"]:
            self._text(v["orders"], scale=0.032, color=GOLD)
        if v["mine"]:
            self._text("Right-click on the map to march. Stop at an enemy town to besiege it; march onto an "
                       "enemy army to give battle.", scale=0.028, color=FADED, font=self.theme.italic)
            if army.route is not None:
                self._button("Halt", self.actions["halt"], [army.id])
        else:
            self._button(f"About {c.name(army.owner)}", self.actions["realm"], [army.owner], scale=0.03)

    # --- a realm ---------------------------------------------------------------------------------

    def show_realm(self, c, tag, choosing=False):
        self.subject = ("realm", tag)
        viewer = c.player or tag
        v = model.realm_view(c, tag, viewer)
        self._open()
        self._heading(v["name"], scale=0.042 if len(v["name"]) > 26 else 0.05)
        self._text(v["ruler"], font=self.theme.italic)
        court = v["court"]
        for line in (court["character"], court["spouse"], court["heir"]):
            if line:
                self._text(line, scale=0.026)
        if court["children"]:
            self._text("; ".join(court["children"]), scale=0.025, color=FADED)
        if c.player:
            self._text(v["relation"], scale=0.03, color=RUBRIC if c.player and c.at_war(c.player, tag) else INK)
        self._text(v["facts"], scale=0.028, color=FADED)
        self._rule()
        self._text(v["situation"], scale=0.03, font=self.theme.italic)
        if choosing:
            info = c.info[tag]
            for n in info["notable"][:3]:
                self._text(f"{n['year']}: {n['event']}", scale=0.028, color=FADED)
            self._rule()
            self._button(f"Play as {info['short']}", self.actions["play"], [tag], scale=0.036)
            return
        if tag == c.player:
            self._rule()
            for i, (key, name) in enumerate((("treasury", "Treasury"), ("missions", "Missions"),
                                             ("decisions", "Decisions"))):
                self.theme.button(self.frame, name, self.left + 0.05 + i * 0.305, self.y, self.actions["realm_tab"],
                                  [key], width=0.285, scale=0.03, enabled=self.realm_tab != key, align="left")
            self.y -= 0.065
            if self.realm_tab == "missions":
                for m in c.missions_view(tag):
                    mark = {"done": "Done: ", "open": "", "locked": "Later: "}[m["state"]]
                    color = GOLD if m["state"] == "done" else (FADED if m["state"] == "locked" else INK)
                    self._text(f"{mark}{m['title']}", scale=0.031, color=color, gap=0.04)
                    if m["state"] != "done" and self.y > -0.8:
                        self._text(m["text"], scale=0.025, color=FADED, font=self.theme.italic)
                        self._text(f"Reward: {m['reward']}", scale=0.025, color=GOLD, gap=0.04)
                    if self.y < -0.9:
                        break
                return
            if self.realm_tab == "decisions":
                for d, ok, why in c.decisions_for(tag):
                    if self.y < -0.85:
                        break
                    self._text(d.text, scale=0.025, color=FADED, font=self.theme.italic)
                    self._button(d.title, self.actions["decide"], [d.id], ok, why, scale=0.028)
                return
            lines, balance = model.budget_lines(c, tag)
            for name, amount in lines:
                self._text(f"{name}: {model.signed(amount)}", scale=0.028, gap=0.034)
            self._text(f"Each month: {model.signed(balance)} ducats", scale=0.032, color=GOLD)
            for war in c.wars_of(tag):
                self._button(c.war_name(war), self.actions["realm"],
                             [war.target if tag == war.leader else war.leader], scale=0.028)
            return
        self._rule()
        for w in v["wars"]:
            self._text(w["name"], scale=0.034, color=RUBRIC)
            self._text(w["goal"] + " · " + w["score"], scale=0.028)
            for line in w["log"][-2:]:
                self._text(line, scale=0.026, color=FADED)
            for offer in w["offers"]:
                hint = "they would agree" if offer["ok"] else "they would refuse"
                self._button(f"{offer['label']}  ({hint})", self.actions["peace"], [w["id"], offer["terms"]],
                             scale=0.028)
            self._rule()
        for act in v["actions"]:
            if self.y < -0.92:
                break
            if act["do"] == "war":
                self._button(act["label"], self.actions["war"], [tag, act["goal"]], act["ok"], act["why"], 0.028)
            elif act["do"] == "marry":
                self._button(act["label"], self.actions["marry"], list(act["pair"]), act["ok"], act["why"], 0.028)
            else:
                self._button(act["label"], self.actions["diplo"], [tag, act["do"], act.get("amount", 0)],
                             act["ok"], act["why"], 0.028)


class Chronicle:
    """The month's news, bottom right."""

    def __init__(self, theme, parent, aspect):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        self.frame = None
        self.lines = []

    def add(self, date, messages):
        for m in messages:
            self.lines.append(f"{date}: {m}")
        self.lines = self.lines[-60:]

    def show(self, count=7):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None
        recent = self.lines[-count:]
        if not recent:
            return
        a = self.aspect
        height = 0.06 + 0.075 * len(recent)
        self.frame = self.theme.panel(self.parent, a - 1.12, a - 0.02, -0.86, -0.86 + height, alpha=0.9)
        y = -0.86 + height - 0.06
        for line in recent:
            self.theme.label(self.frame, line, a - 1.08, y, scale=0.027, wrap=1.02 / 0.027,
                             color=RUBRIC if "Battle" in line or "war" in line.lower() else INK)
            y -= 0.075

    def hide(self):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None


class Dialog:
    """A sheet in the middle of the screen with a text and a few answers."""

    def __init__(self, theme, parent):
        self.theme, self.parent = theme, parent
        self.frame = None

    def show(self, title, text, answers, notes=None):
        """answers: [(label, callback)]; with notes (one per answer), the answers are stacked, each with
        a line saying what it will bring."""
        self.close()
        stacked = notes is not None
        bottom = -0.4 - (0.1 * len(answers) if stacked else 0)
        self.frame = self.theme.panel(self.parent, -0.75, 0.75, bottom, 0.4)
        self.theme.heading(self.frame, title, 0, 0.3, scale=0.05, align=TextNode.ACenter)
        self.theme.label(self.frame, text, -0.66, 0.2, scale=0.034, wrap=1.32 / 0.034, font=self.theme.italic)
        if stacked:
            y = -0.22
            for (label, callback), note in zip(answers, notes):
                self.theme.button(self.frame, label, -0.66, y, self._answer, [callback], width=1.32, scale=0.036,
                                  align="left")
                if note:
                    self.theme.label(self.frame, note, 0, y - 0.055, scale=0.027, color=FADED,
                                     align=TextNode.ACenter)
                y -= 0.13
            return
        x = -0.66
        width = (1.32 - 0.04 * (len(answers) - 1)) / max(1, len(answers))
        for label, callback in answers:
            self.theme.button(self.frame, label, x, -0.3, self._answer, [callback], width=width, scale=0.034,
                              align="left")
            x += width + 0.04

    def _answer(self, callback):
        self.close()
        if callback:
            callback()

    def close(self):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

    @property
    def open(self):
        return self.frame is not None
