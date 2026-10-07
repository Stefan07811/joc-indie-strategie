"""Crowns of the Balkans: the campaign on the 3D map.

    python -m crowns                    play (choose a realm on the map)
    python -m crowns --realm wallachia  play straight away as a realm
    python -m crowns --shots DIR        render a few views to DIR and quit (works without a display)

Controls: WASD or the arrows move, the mouse wheel zooms, right-drag or Q/E turns, middle-drag moves.
Left click picks a province, an army or a realm; right click orders the chosen army to march there
(onto an enemy army: give battle; to an enemy town: besiege it). Space ends the month. 1 / 2 switch
between the terrain and the political map. F5 saves, F9 loads. M turns the music off and on.
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

from panda3d.core import loadPrcFileData

ACCENT = {"latin": (0.94, 0.92, 0.86), "vlach": (0.20, 0.30, 0.62), "balkan": (0.85, 0.75, 0.40),
          "greek": (0.55, 0.20, 0.45), "ottoman": (0.94, 0.92, 0.86), "steppe": (0.55, 0.12, 0.10),
          "levant": (0.90, 0.78, 0.30)}
EASTERN = {"ottoman", "steppe", "levant"}


def saves_dir():
    return Path(os.environ.get("CROWNS_HOME", Path.home() / ".crowns")) / "saves"


def configure(offscreen=False, size=None, fullscreen=False):
    lines = ["window-title Crowns of the Balkans", "framebuffer-multisample 1", "multisamples 4",
             "textures-power-2 none", "sync-video 1", "show-frame-rate-meter 0",
             "notify-level-display error", "notify-level-device error", "notify-level-audio error"]
    if offscreen:
        lines += ["window-type offscreen", "sync-video 0", "audio-library-name null"]
    if size:
        lines.append(f"win-size {size[0]} {size[1]}")
    if fullscreen:
        lines.append("fullscreen 1")
    loadPrcFileData("", "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="crowns")
    parser.add_argument("--realm", help="play as this realm (e.g. wallachia, hungary, ott_rum)")
    parser.add_argument("--shots", help="render views to this folder and quit")
    parser.add_argument("--only", nargs="*", help="with --shots: just these views")
    parser.add_argument("--size", default=None, help="window size, e.g. 1920x1080")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--style", default="codex", help="the map's look: codex (the game's) or real (for checks)")
    parser.add_argument("--selftest", metavar="REPORT", help="check the game works, without a window, and quit")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(Path(args.selftest))
    size = tuple(int(v) for v in args.size.split("x")) if args.size else None
    configure(offscreen=bool(args.shots), size=size or ((1600, 900) if args.shots else None),
              fullscreen=args.fullscreen)
    app = MapApp(style=args.style, realm=args.realm)
    if args.shots:
        app.shots(Path(args.shots), args.only)
    else:
        app.run()


def selftest(report):
    """Load everything the game needs and play a few months, without a window (for the build machine,
    which has no graphics card). Writes what happened to `report`; returns 0 when all is well."""
    lines = []
    try:
        from panda3d.core import Filename, MovieAudio

        from .audio import MUSIC, PLAYLISTS
        from .game.campaign import Campaign
        from .game.navigation import NavalNavigation, Navigation
        from .game.realms import load
        from .mapdata import Ground
        from .provinces import ProvinceMap
        started = time.time()
        provmap = ProvinceMap()
        realms, relations = load()
        ground = Ground()
        c = Campaign(provmap, realms, relations, player="wallachia")
        c.attach_ai(Navigation(ground, provmap), NavalNavigation(ground, provmap))
        for _ in range(3):
            c.end_month()
        lines.append(f"campaign: {c.date}, {len(c.armies)} armies, {len(c.people)} people")
        for name in {n for playlist in PLAYLISTS.values() for n in playlist}:
            cursor = MovieAudio.get(Filename.fromOsSpecific(str(MUSIC / f"{name}.ogg"))).open()
            lines.append(f"music {name}: {cursor.length():.0f} s")
        lines.append(f"ok in {time.time() - started:.1f} s")
        code = 0
    except Exception:   # noqa: BLE001 - the report says what failed
        import traceback
        lines.append(traceback.format_exc())
        code = 1
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return code


# Imported after configure(): Panda reads its settings when ShowBase starts.
def _showbase():
    from direct.showbase.ShowBase import ShowBase
    return ShowBase


class MapApp(_showbase()):
    def __init__(self, style="codex", realm=None):
        super().__init__()
        from panda3d.core import WindowProperties

        from . import geo
        from .game.campaign import Campaign
        from .game.navigation import NavalNavigation, Navigation
        from .game.realms import load as load_realms
        from .provinces import ProvinceMap
        from .render.camera import StrategyCamera
        from .render.orders import RouteRibbon
        from .render.political import Labels, Overlay, RealmLabels
        from .render.world import HAZE, MapWorld
        from .ui.panels import Chronicle, Dialog, SidePanel, TopBar
        from .audio import Audio
        from .ui.theme import Theme

        self.geo = geo
        if hasattr(self.win, "getProperties") and not self.win.getProperties().getFullscreen() and self.pipe:
            w, h = self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight()
            if w > 0 and self.win.getXSize() < w * 0.8:
                props = WindowProperties()
                props.setSize(int(w * 0.9), int(h * 0.85))
                self.win.requestProperties(props)
        self.disableMouse()
        self.setBackgroundColor(*HAZE)
        started = time.time()
        from direct.gui.OnscreenText import OnscreenText
        waiting = OnscreenText(text="Crowns of the Balkans\n\nPreparing the map…\n(the first start takes a minute)",
                               scale=0.06, fg=(0.24, 0.15, 0.08, 1), parent=self.aspect2d)
        for _ in range(2):
            self.graphicsEngine.renderFrame()
        self.world = MapWorld(style=style)
        self.world.root.reparentTo(self.render)
        self.provmap = ProvinceMap()
        self.overlay = Overlay(self.provmap)
        self.world.set_provinces(self.overlay.index_texture(), self.overlay.distance_texture())
        self.realms, self.relations = load_realms()
        self.colors = {tag: tuple(r["color"]) for tag, r in self.realms.items()}
        self.campaign = Campaign(self.provmap, self.realms, self.relations, player=None)
        self.nav = Navigation(self.world.ground, self.provmap)
        self.naval_nav = NavalNavigation(self.world.ground, self.provmap)
        self.campaign.nav, self.campaign.naval_nav = self.nav, self.naval_nav
        self.selected = None
        self.hovered = None
        self.mode = "political"
        self.theme = Theme(self.loader)
        self.audio = Audio(self)
        if self.audio.enabled:
            from .audio import SOUNDS
            self.theme.click = self.loader.loadSfx(str(SOUNDS / "click.ogg"))
            self.theme.click.setVolume(0.5)
        self.labels = Labels(self.provmap, self.world.height_at, self.theme.title, self.render)
        self.realm_labels = RealmLabels(self.provmap, self.owners(), {t: r["short"] for t, r in self.realms.items()},
                                        self.world.height_at, self.theme.title, self.render,
                                        capitals={t: r["capital"] for t, r in self.realms.items()})
        self.camera_ctl = StrategyCamera(self.camera, self.camLens, self.world.height_at)
        self.camera_ctl.look_at(*self.world_xy(25.5, 44.0), 1100)
        self.ribbon = RouteRibbon(self.render, self.world.height_at)
        self.chosen = None
        self.figures = {}
        aspect = self.getAspectRatio()
        self.topbar = TopBar(self.theme, self.aspect2d, aspect, self.end_month, self.show_my_realm)
        self.panel = SidePanel(self.theme, self.aspect2d, aspect, {
            "close": self.close_panel, "realm": self.show_realm, "tab": self.set_tab, "build": self.build,
            "recruit": self.recruit, "halt": self.halt, "war": self.ask_war, "diplo": self.diplo,
            "peace": self.offer_peace, "play": self.play_as, "marry": self.marry,
            "realm_tab": self.set_realm_tab, "decide": self.decide, "split": self.split_army,
            "merge": self.merge_armies})
        self.chronicle = Chronicle(self.theme, self.aspect2d, aspect)
        from direct.gui.DirectGui import DirectLabel
        from panda3d.core import TextNode
        self.tooltip = DirectLabel(parent=self.aspect2d, text="", scale=0.032, text_font=self.theme.text,
                                   text_fg=(0.2, 0.13, 0.07, 1), text_align=TextNode.ALeft,
                                   frameColor=(0.95, 0.9, 0.78, 0.92), pad=(0.4, 0.25), sortOrder=50)
        self.tooltip.hide()
        self.dialog = Dialog(self.theme, self.aspect2d)
        self.redraw_overlay()
        from .render.towns import Towns
        from .render.world import SUN
        self.towns = Towns(self.render, self.campaign, self.world.height_at, SUN)
        self.sync_figures()
        self.refresh()
        if realm:
            self.play_as(realm, welcome=False)
        waiting.destroy()
        print(f"map ready in {time.time() - started:.1f} s")
        self.keys = {}
        for key in ("w", "a", "s", "d", "arrow_up", "arrow_down", "arrow_left", "arrow_right", "q", "e"):
            self.accept(key, self.keys.__setitem__, [key, True])
            self.accept(key + "-up", self.keys.__setitem__, [key, False])
        self.accept("wheel_up", self.camera_ctl.zoom_by, [0.85])
        self.accept("wheel_down", self.camera_ctl.zoom_by, [1 / 0.85])
        self.accept("mouse1", self.pick)
        self.accept("mouse2", self._drag, ["pan"])
        self.accept("mouse2-up", self._drag, [None])
        self.accept("mouse3", self._right_down)
        self.accept("mouse3-up", self._right_up)
        self.accept("space", self.end_month)
        self.accept("enter", self.end_month)
        self.accept("1", self.set_mode, ["terrain"])
        self.accept("2", self.set_mode, ["political"])
        self.accept("f5", self.save_game)
        self.accept("f9", self.load_game)
        self.accept("m", self.audio.toggle)
        self.accept("tab", self.next_army)
        self.accept("escape", self.escape)
        self.dragging = None
        self.last_mouse = None
        self.right_from = None
        self.taskMgr.add(self.tick, "tick")

    # --- the campaign ----------------------------------------------------------------------------

    @property
    def c(self):
        return self.campaign

    def owners(self):
        return {p.id: p.owner for p in self.campaign.provinces.values()}

    def play_as(self, tag, welcome=True):
        c = self.campaign
        c.player = tag
        c.attach_ai(self.nav, self.naval_nav)
        self.panel.close()
        self.camera_ctl.look_at(*self.map_to_world(*c.static(c.capital(tag)).town), 520)
        self.refresh()
        if welcome:
            info = c.info[tag]
            self.dialog.show(info["name"], f"{info['situation']}\n\nSeptember 1402. The month is yours.",
                             [("Begin", None)])

    def refresh(self):
        """Bring the bar and the open panel up to date (and the music to the mood of the realm)."""
        from .audio import mood_of
        self.audio.set_mood(mood_of(self.campaign))
        self.topbar.update(self.campaign)
        self.topbar.show_end(self.campaign.player is not None)
        subject = self.panel.subject
        if subject is None:
            return
        kind, key = subject
        if kind == "province":
            self.panel.show_province(self.campaign, key)
        elif kind == "army":
            army = self.army_by_id(key)
            if army is None:
                self.close_panel()
            else:
                self.panel.show_army(self.campaign, army)
        elif kind == "realm":
            self.panel.show_realm(self.campaign, key, choosing=self.campaign.player is None)

    def end_month(self):
        c = self.campaign
        if c.player is None or self.dialog.open:
            return
        before = str(c.date)
        owners = self.owners()
        self.audio.play("month", 0.5)
        c.end_month()
        self.chronicle.add(before, c.messages)
        self.chronicle.show()
        self.sync_figures(animate=True)
        self.towns.rebuild()
        if self.owners() != owners:
            self.realm_labels.rebuild(self.owners())
        self.redraw_overlay()
        if self.chosen is not None and self.chosen not in c.armies:
            self.chosen = None
        self.show_orders()
        self.refresh()
        self.next_proposal()

    def next_proposal(self):
        c = self.campaign
        if self.dialog.open:
            return
        if c.pending:
            return self.next_event()
        if not c.proposals:
            return
        offer = c.proposals[0]
        war = next((w for w in c.wars if w.id == offer["war"]), None)
        if war is None:
            c.proposals.pop(0)
            return self.next_proposal()
        text = f"{c.name(offer['from'])} offers to end {c.war_name(war)}: {c.peace_text(war, offer['terms'])}"

        def answer(yes):
            result = c.answer(offer, yes)
            if result:
                self.chronicle.add(str(c.date), [result])
                self.chronicle.show()
            self.redraw_overlay()
            self.realm_labels.rebuild(self.owners())
            self.refresh()
            self.next_proposal()
        self.dialog.show("An offer of peace", text, [("Accept", lambda: answer(True)),
                                                     ("Refuse", lambda: answer(False))])

    def next_event(self):
        """Ask the player about the next event waiting for an answer."""
        from .game.history import EVENT
        c = self.campaign
        item = c.pending[0]
        event = EVENT[item["event"]]

        def pick(i):
            choice = c.choose(item, i)
            c.messages = []
            self.chronicle.add(str(c.date), [f"{event.title}: {choice.label}."])
            self.chronicle.show()
            self.redraw_overlay()
            self.realm_labels.rebuild(self.owners())
            self.sync_figures()
            self.refresh()
            self.next_proposal()
        self.audio.play("event", 0.6)
        answers = [(ch.label, (lambda i=i: pick(i))) for i, ch in enumerate(event.choices)]
        self.dialog.show(event.title, item["text"], answers, notes=[ch.about for ch in event.choices])

    # --- the panels' actions ---------------------------------------------------------------------

    def close_panel(self):
        self.panel.close()
        self.selected = None
        self.redraw_overlay()

    def show_realm(self, tag):
        self.panel.show_realm(self.campaign, tag, choosing=self.campaign.player is None)

    def show_my_realm(self):
        if self.campaign.player:
            self.show_realm(self.campaign.player)

    def set_tab(self, tab, pid):
        self.panel.tab = tab
        self.panel.show_province(self.campaign, pid)

    def build(self, pid, kind):
        if self.campaign.build(pid, kind):
            self.audio.play("build", 0.6)
            self.refresh()

    def recruit(self, pid, unit):
        if self.campaign.recruit(pid, unit):
            self.audio.play("march", 0.5)
            self.refresh()

    def halt(self, army_id):
        army = self.army_by_id(army_id)
        if army:
            army.halt()
            self.show_orders()
            self.refresh()

    def ask_war(self, tag, goal):
        c = self.campaign
        allies = c.defenders_called(tag, c.player)
        text = f"Declare war on {c.info[tag]['name']}? Our goal: {c.describe_goal(goal, tag)}."
        if allies:
            text += " They will be joined by " + ", ".join(c.name(t) for t in allies) + "."
        self.dialog.show("War", text, [("Declare war", lambda: self.declare(tag, goal)), ("Not yet", None)])

    def declare(self, tag, goal):
        c = self.campaign
        c.messages = []
        c.declare_war(c.player, tag, goal)
        self.chronicle.add(str(c.date), c.messages)
        self.chronicle.show()
        self.refresh()

    def diplo(self, tag, do, amount):
        c = self.campaign
        c.messages = []
        if do == "ally":
            ok, why = c.ally(c.player, tag)
        elif do == "break":
            ok, why = c.break_alliance(c.player, tag), f"The alliance with {c.name(tag)} is broken."
        elif do == "tribute":
            ok, why = c.demand_tribute(c.player, tag)
        else:
            ok = c.send_gift(c.player, tag, amount)
            why = f"{c.name(tag)} thanks us for the gift." if ok else "We cannot afford it."
        self.chronicle.add(str(c.date), [why])
        self.chronicle.show()
        self.refresh()

    def split_army(self, army_id):
        army = self.army_by_id(army_id)
        if army is not None and self.campaign.split_army(army):
            self.sync_figures()
            self.choose(army)

    def merge_armies(self, army_id):
        army = self.army_by_id(army_id)
        if army is not None and self.campaign.merge_armies(army):
            self.sync_figures()
            self.choose(army)

    def next_army(self):
        """Tab: the next of our armies, and the camera to it."""
        c = self.campaign
        mine = c.armies_of(c.player) if c.player else []
        if not mine:
            return
        i = (mine.index(self.chosen) + 1) % len(mine) if self.chosen in mine else 0
        army = mine[i]
        self.camera_ctl.look_at(*self.map_to_world(army.x, army.y), min(self.camera_ctl.distance, 450))
        self.choose(army)

    def set_realm_tab(self, tab):
        self.panel.realm_tab = tab
        self.refresh()

    def decide(self, did):
        c = self.campaign
        c.messages = []
        ok, why = c.take_decision(did, c.player)
        self.chronicle.add(str(c.date), c.messages or [why])
        self.chronicle.show()
        self.redraw_overlay()
        self.refresh()

    def marry(self, ours, theirs):
        c = self.campaign
        c.messages = []
        ok, why = c.propose_marriage(ours, theirs)
        self.chronicle.add(str(c.date), c.messages or [why])
        self.chronicle.show()
        self.refresh()

    def offer_peace(self, war_id, terms):
        c = self.campaign
        war = next((w for w in c.wars if w.id == war_id), None)
        if war is None:
            return
        other = war.target if c.player == war.leader else war.leader
        if c.would_accept(war, terms, other):
            text = c.make_peace(war, terms)
            self.redraw_overlay()
            self.realm_labels.rebuild(self.owners())
        else:
            c.nudge(c.player, other, -3)
            text = f"{c.name(other)} refuses our terms."
        self.chronicle.add(str(c.date), [text])
        self.chronicle.show()
        self.refresh()

    # --- armies ----------------------------------------------------------------------------------

    def figure_spot(self, army, x=None, y=None):
        """Where an army's miniature stands, in world units: at a town it camps outside the walls, the
        armies there side by side."""
        x = army.x if x is None else x
        y = army.y if y is None else y
        prov = self.provmap.at(x, y)
        if prov is not None and math.hypot(prov.town[0] - x, prov.town[1] - y) < 4:
            here = [a for a in self.campaign.armies
                    if math.hypot(a.x - prov.town[0], a.y - prov.town[1]) < 4]
            k = here.index(army) if army in here else 0
            angle = math.radians(-35 + 70 * k)
            x, y = prov.town[0] + 10 * math.sin(angle), prov.town[1] + 10 * math.cos(angle)
        return self.map_to_world(x, y)

    def army_by_id(self, army_id):
        return next((a for a in self.campaign.armies if a.id == army_id), None)

    def sync_figures(self, animate=False):
        """A miniature for every army: new ones raised, the destroyed taken away, marches walked."""
        from .render.figures import ArmyFigure
        from .render.world import SUN
        c = self.campaign
        alive = {a.id for a in c.armies}
        for army_id in list(self.figures):
            if army_id not in alive:
                self.figures.pop(army_id).root.removeNode()
        for army in c.armies:
            figure = self.figures.get(army.id)
            if figure is None:
                tradition = c.tradition(army.owner)
                color = tuple(v / 255 for v in self.colors[army.owner])
                figure = ArmyFigure(self.render, self.world.height_at, color, ACCENT[tradition], SUN,
                                    eastern=tradition in EASTERN)
                figure.place(*self.figure_spot(army))
                self.figures[army.id] = figure
                continue
            walk = army.last_walk if animate else []
            end = self.figure_spot(army)
            if len(walk) > 1:
                figure.march(self._strides(walk) + [end])
            elif math.hypot(figure.pos.x - end[0], figure.pos.y - end[1]) > 0.5:
                figure.march([end]) if animate else figure.place(*end)
            army.last_walk = []

    def army_at(self, p):
        """The army whose miniature is under world point p, if any."""
        reach = max(7.0, self.camera_ctl.distance * 0.025)
        best = None
        for army in self.campaign.armies:
            figure = self.figures.get(army.id)
            if figure is None:
                continue
            d = math.hypot(figure.pos.x - p.x, figure.pos.y - p.y)
            if d < reach:
                best, reach = army, d
        return best

    def choose(self, army):
        self.chosen = army
        self.show_orders()
        if army is not None:
            self.panel.show_army(self.campaign, army)

    def show_orders(self):
        """Show the chosen army's reach this month and its route (for the player's own armies)."""
        from .render.orders import months_of, reach_field
        army = self.chosen
        if army is None or army.owner != self.campaign.player:
            self.world.set_reach(None)
            self.ribbon.hide()
            return
        if army.moves >= 1:
            self.world.set_reach(*reach_field(army.reach(self.campaign.nav_for(army))))
        else:
            self.world.set_reach(None)
        months = months_of(army.route, army.moves, army.march) if army.route else []
        if months:
            self.ribbon.show(months)
        else:
            self.ribbon.hide()

    def order_march(self, army, x, y):
        """March the army towards map pixel (x, y): as far as it can this month, the rest are orders. If it
        ends next to an enemy army, they fight at once."""
        c = self.campaign
        target = None
        for other in c.armies:
            if other is not army and c.hostile(army.owner, other.owner) and math.hypot(other.x - x, other.y - y) < 8:
                target = other
                x, y = other.x, other.y
        if not army.order(c.nav_for(army), x, y):
            return False
        self.audio.play("march", 0.5)
        walked = army.walk()
        if len(walked) > 1:
            self.figures[army.id].march(self._strides(walked) + [self.figure_spot(army)])
        enemy = c.hostile_near(army)
        if enemy is not None and (target is None or enemy is target):
            c.messages = []
            report = c.battle(army, enemy)
            self.chronicle.add(str(c.date), c.messages)
            self.chronicle.show()
            self.sync_figures()
            self.battle_dialog(report)
        return True

    def battle_dialog(self, report):
        c = self.campaign
        won = report["winner"] == c.player
        self.audio.play("victory" if won else "defeat", 0.8)
        title = f"Victory at {report['place']}" if won else f"Defeat at {report['place']}"
        winner, loser = report["armies"]
        text = (f"On the {report['terrain']} of {report['place']}, the {winner} broke the {loser}. "
                f"{c.name(report['winner'])} lost {report['losses'][report['winner']]:,} men, "
                f"{c.name(report['loser'])} {report['losses'][report['loser']]:,}.")
        self.dialog.show(title, text, [("Onward", None)])
        if self.chosen is not None and self.chosen not in c.armies:
            self.choose(None)
            self.panel.close()
        self.refresh()

    def _strides(self, points):
        """World points every few units along a march in map pixels, for the miniature to walk."""
        out = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            steps = max(1, int(math.hypot(bx - ax, by - ay) / 4))
            out += [(ax + (bx - ax) * k / steps, self.geo.HEIGHT - (ay + (by - ay) * k / steps))
                    for k in range(1, steps + 1)]
        return out

    # --- saving -----------------------------------------------------------------------------------

    def save_game(self, name="quick"):
        if self.campaign.player is None:
            return
        folder = saves_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.json"
        path.write_text(json.dumps(self.campaign.to_dict()), encoding="utf-8")
        self.chronicle.add(str(self.campaign.date), [f"Saved ({path.name})."])
        self.chronicle.show()

    def load_game(self, name="quick"):
        from .game.campaign import Campaign
        path = saves_dir() / f"{name}.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.campaign = Campaign.from_dict(data, self.provmap, self.realms, self.relations)
        self.campaign.nav, self.campaign.naval_nav = self.nav, self.naval_nav
        self.campaign.attach_ai(self.nav, self.naval_nav)
        for figure in self.figures.values():
            figure.root.removeNode()
        self.figures = {}
        self.chosen = None
        self.panel.close()
        self.sync_figures()
        self.towns.campaign = self.campaign
        self.towns.rebuild(force=True)
        self.realm_labels.rebuild(self.owners())
        self.redraw_overlay()
        self.show_orders()
        self.refresh()
        self.chronicle.add(str(self.campaign.date), ["Loaded."])
        self.chronicle.show()

    # --- coordinates ----------------------------------------------------------------------------

    def world_xy(self, lon, lat):
        x, y = self.geo.to_map(lon, lat)
        return x, self.geo.HEIGHT - y

    def map_to_world(self, x, y):
        return x, self.geo.HEIGHT - y

    def mouse_ground(self):
        """The world point under the mouse, or None."""
        if not self.mouseWatcherNode.hasMouse():
            return None
        from panda3d.core import Point3
        m = self.mouseWatcherNode.getMouse()
        near, far = Point3(), Point3()
        self.camLens.extrude(m, near, far)
        near = self.render.getRelativePoint(self.camera, near)
        far = self.render.getRelativePoint(self.camera, far)
        d = far - near
        z = 0.0
        for _ in range(4):  # meet the ground: aim at a level plane, then at the ground's height there
            if abs(d.z) < 1e-6:
                return None
            t = (z - near.z) / d.z
            p = near + d * t
            z = self.world.height_at(p.x, p.y)
        return p

    def over_gui(self):
        return self.mouseWatcherNode.hasMouse() and self.mouseWatcherNode.getOverRegion() is not None

    # --- input ----------------------------------------------------------------------------------

    def escape(self):
        if self.dialog.open:
            self.dialog.close()
        elif self.panel.subject is not None:
            self.close_panel()
            self.choose(None)
        else:
            sys.exit()

    def _drag(self, kind):
        self.dragging = kind
        self.last_mouse = None

    def _right_down(self):
        """Right button: drag to turn the view, click to order the chosen army to march."""
        self._drag("turn")
        m = self.mouseWatcherNode.getMouse() if self.mouseWatcherNode.hasMouse() else None
        self.right_from = (m.x, m.y) if m is not None else None

    def _right_up(self):
        self._drag(None)
        army = self.chosen
        if army is None or army.owner != self.campaign.player or self.right_from is None or self.dialog.open:
            return
        if not self.mouseWatcherNode.hasMouse() or self.over_gui():
            return
        m = self.mouseWatcherNode.getMouse()
        if math.hypot(m.x - self.right_from[0], m.y - self.right_from[1]) > 0.02:
            return
        p = self.mouse_ground()
        if p is not None and self.order_march(army, p.x, self.geo.HEIGHT - p.y):
            self.show_orders()
            self.refresh()

    def pick(self):
        if self.over_gui() or self.dialog.open:
            return
        p = self.mouse_ground()
        if p is None:
            return
        army = self.army_at(p)
        if army is not None:
            self.choose(army)
            return
        if self.chosen is not None:
            self.choose(None)
        prov = self.provmap.at(p.x, self.geo.HEIGHT - p.y)
        self.selected = prov.index if prov else None
        self.redraw_overlay()
        if prov is None:
            self.panel.close()
        elif self.campaign.player is None:
            self.show_realm(self.campaign.provinces[prov.id].owner)
        else:
            self.panel.tab = "build"
            self.panel.show_province(self.campaign, prov.id)

    def set_mode(self, mode):
        self.mode = mode
        self.redraw_overlay()

    def redraw_overlay(self):
        c = self.campaign
        pal = self.overlay.palette(lambda p: self.colors.get(c.provinces[p.id].owner))
        held = self.overlay.palette(lambda p: self.colors.get(c.provinces[p.id].controller))
        self.world.set_palette(pal, mix=0.62 if self.mode == "political" else 0.0, held=held)
        self.world.set_highlight(self.selected, self.hovered)

    def tick(self, task):
        dt = min(globalClock.getDt(), 0.1)  # noqa: F821 - Panda's builtin clock
        k = self.keys
        speed = 600 * dt
        dx = (k.get("d") or k.get("arrow_right") or 0) - (k.get("a") or k.get("arrow_left") or 0)
        dy = (k.get("w") or k.get("arrow_up") or 0) - (k.get("s") or k.get("arrow_down") or 0)
        if dx or dy:
            self.camera_ctl.pan(dx * speed, dy * speed)
        turn = (k.get("e") or 0) - (k.get("q") or 0)
        if turn:
            self.camera_ctl.turn(turn * 70 * dt)
        if self.dragging and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            if self.last_mouse is not None:
                mx, my = m.x - self.last_mouse[0], m.y - self.last_mouse[1]
                if self.dragging == "pan":
                    self.camera_ctl.pan(-mx * 900, -my * 600)
                else:
                    self.camera_ctl.turn(mx * 120)
            self.last_mouse = (m.x, m.y)
        self.world.update(self.camera_ctl.position, task.time)
        self.audio.update(dt)
        for figure in self.figures.values():
            figure.update(dt, task.time)
        self.ribbon.update(self.camera_ctl.distance, task.time)
        self.towns.update(self.camera_ctl.distance)
        self.labels.update(self.camera_ctl.distance, self.camera_ctl.heading)
        self.realm_labels.update(self.camera_ctl.distance)
        p = None if self.over_gui() else self.mouse_ground()
        prov = self.provmap.at(p.x, self.geo.HEIGHT - p.y) if p is not None else None
        self.update_tooltip(p, prov)
        hovered = prov.index if prov else None
        if hovered != self.hovered:
            self.hovered = hovered
            self.world.set_highlight(self.selected, hovered)
        return task.cont

    def update_tooltip(self, p, prov):
        """A small label by the mouse: the army or the province under it."""
        if p is None or self.dialog.open or not self.mouseWatcherNode.hasMouse():
            self.tooltip.hide()
            return
        c = self.campaign
        army = self.army_at(p)
        if army is not None:
            text = f"{army.name}\n{army.men:,} men"
            if army.owner != c.player and c.player and c.at_war(c.player, army.owner):
                text += " — enemy"
        elif prov is not None:
            state = c.provinces[prov.id]
            text = f"{prov.name}\n{c.name(state.owner)}"
            if state.controller != state.owner:
                text += f", held by {c.name(state.controller)}"
            if state.siege:
                text += f"\nBesieged ({min(99, state.siege['progress'] * 100):.0f}%)"
        else:
            self.tooltip.hide()
            return
        m = self.mouseWatcherNode.getMouse()
        self.tooltip["text"] = text
        self.tooltip.setPos(m.x * self.getAspectRatio() + 0.04, 0, m.y - 0.06)
        self.tooltip.show()

    # --- pictures for checking the game without a display ----------------------------------------

    def _view(self, lon, lat, dist, heading, mode="political"):
        self.mode = mode
        self.redraw_overlay()
        self.camera_ctl.heading = heading
        self.camera_ctl.look_at(*self.world_xy(lon, lat), dist)

    def _shoot(self, folder, name):
        self.world.update(self.camera_ctl.position, 2.0)
        self.towns.update(self.camera_ctl.distance)
        self.ribbon.update(self.camera_ctl.distance, 2.0)
        self.labels.update(self.camera_ctl.distance, self.camera_ctl.heading)
        self.realm_labels.update(self.camera_ctl.distance)
        for _ in range(2):
            self.graphicsEngine.renderFrame()
        self.win.saveScreenshot(str(folder / f"{name}.png"))
        print("saved", name)

    def shots(self, folder, only=None):
        folder.mkdir(parents=True, exist_ok=True)
        want = (lambda name: not only or name in only or (name == "towns" and any(o.startswith("towns")
                                                                                   for o in only)))
        c = self.campaign
        # choosing a realm
        if want("choose"):
            self._view(26.0, 43.5, 1500, 0)
            self.show_realm("wallachia")
            self._shoot(folder, "choose")
        self.play_as("wallachia", welcome=False)
        if want("welcome"):
            info = c.info["wallachia"]
            self.dialog.show(info["name"], f"{info['situation']}\n\nSeptember 1402. The month is yours.",
                             [("Begin", None)])
            self._view(25.5, 44.6, 520, 0)
            self._shoot(folder, "welcome")
        self.dialog.close()
        if want("towns"):
            self.panel.close()
            for lon, lat, dist, heading, label in ((25.45, 44.93, 120, 20, "towns"),
                                                   (28.95, 41.02, 110, 330, "towns_city"),
                                                   (26.55, 41.68, 100, 0, "towns_edirne")):
                self._view(lon, lat, dist, heading)
                self._shoot(folder, label)
        if want("province"):
            self._view(25.5, 44.6, 420, 0)
            self.selected = self.provmap.provinces["targoviste"].index
            self.panel.show_province(c, "targoviste")
            self.redraw_overlay()
            self._shoot(folder, "province")
        if want("realm"):
            self.panel.show_realm(c, "ott_rum")
            self._view(25.5, 43.0, 900, 0)
            self._shoot(folder, "realm")
        army = c.armies_of("wallachia")[0]
        if want("army"):
            self.choose(army)
            army.order(c.nav_for(army), *c.static("nikopol").town)
            self.show_orders()
            self.panel.show_army(c, army)
            self._view(25.0, 44.2, 520, 0)
            self._shoot(folder, "army")
        if want("missions"):
            self.choose(None)
            self.panel.realm_tab = "missions"
            self.panel.show_realm(c, "wallachia")
            self._view(25.5, 44.6, 700, 0)
            self._shoot(folder, "missions")
            self.panel.realm_tab = "decisions"
            self.panel.show_realm(c, "wallachia")
            self._shoot(folder, "decisions")
            self.panel.realm_tab = "treasury"
        if want("event"):
            from .game.history import EVENT
            c.provinces["arges"].unrest = 9
            c.fire(EVENT["revolt"], "wallachia")
            self.next_proposal()
            self._shoot(folder, "event")
            self.dialog.close()
            c.pending = []
            c.provinces["arges"].unrest = 0
        # a war, a few months on
        c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
        army.order(c.nav_for(army), *c.static("nikopol").town)
        army.walk()
        for _ in range(4):
            self.end_month()
            self.dialog.close()
            self._settle()
        if want("war"):
            self.choose(army if army in c.armies else None)
            self.panel.show_realm(c, "ott_rum")
            self._view(25.0, 43.7, 480, 0)
            self._shoot(folder, "war")
        if want("years"):
            for _ in range(18):
                self.end_month()
                self.dialog.close()
            self._settle()
            self.panel.close()
            self.choose(None)
            self._view(27.0, 42.5, 1700, 0)
            self._shoot(folder, "years")

    def _settle(self):
        """Let the miniatures finish their marches (for the pictures)."""
        for _ in range(4000):
            if not any(f.marching for f in self.figures.values()):
                break
            for f in self.figures.values():
                f.update(0.05, 1.0)


if __name__ == "__main__":
    sys.exit(main())
