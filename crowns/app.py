"""Crowns of the Balkans: the 3D map application.

    python -m crowns                  play (a window at the desktop's resolution)
    python -m crowns --shots DIR      render a few views to DIR and quit (works without a display)

Controls: WASD or the arrows move, the mouse wheel zooms, right-drag or Q/E turns, middle-drag moves,
left click picks a province or an army, right click orders the chosen army to march there, space or
enter ends the month, 1 / 2 switch between the terrain and the political map.
"""

import argparse
import math
import sys
import time
from pathlib import Path

from panda3d.core import loadPrcFileData

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"


def configure(offscreen=False, size=None, fullscreen=False):
    lines = ["window-title Crowns of the Balkans", "framebuffer-multisample 1", "multisamples 4",
             "textures-power-2 none", "audio-library-name null", "sync-video 1", "show-frame-rate-meter 0",
             "notify-level-display error", "notify-level-device error"]
    if offscreen:
        lines += ["window-type offscreen", "sync-video 0"]
    if size:
        lines.append(f"win-size {size[0]} {size[1]}")
    if fullscreen:
        lines.append("fullscreen 1")
    loadPrcFileData("", "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="crowns")
    parser.add_argument("--shots", help="render views to this folder and quit")
    parser.add_argument("--only", nargs="*", help="with --shots: just these views")
    parser.add_argument("--size", default=None, help="window size, e.g. 1920x1080")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--style", default="codex", help="the map's look: codex (the game's) or real (for checks)")
    args = parser.parse_args(argv)
    size = tuple(int(v) for v in args.size.split("x")) if args.size else None
    configure(offscreen=bool(args.shots), size=size or ((1600, 900) if args.shots else None),
              fullscreen=args.fullscreen)
    app = MapApp(style=args.style)
    if args.shots:
        app.shots(Path(args.shots), args.only)
    else:
        app.run()


# Imported after configure(): Panda reads its settings when ShowBase starts.
def _showbase():
    from direct.showbase.ShowBase import ShowBase
    return ShowBase


class MapApp(_showbase()):
    def __init__(self, style="codex"):
        super().__init__()
        from direct.gui.OnscreenText import OnscreenText
        from panda3d.core import TextNode, Vec3, WindowProperties

        from . import geo
        from .provinces import ProvinceMap
        from .render.camera import StrategyCamera
        from .render.political import Labels, Overlay, RealmLabels
        from .render.world import HAZE, MapWorld
        from .game.realms import load as load_realms

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
        self.world = MapWorld(style=style)
        self.world.root.reparentTo(self.render)
        self.provmap = ProvinceMap()
        self.overlay = Overlay(self.provmap)
        self.world.set_provinces(self.overlay.index_texture(), self.overlay.distance_texture())
        self.realms, self.relations = load_realms()
        REALM_NAMES = {tag: r["short"] for tag, r in self.realms.items()}
        self.colors = {tag: tuple(r["color"]) for tag, r in self.realms.items()}
        self.owner_of = {p.id: p.owner for p in self.provmap.provinces.values()}
        self.selected = None
        self.mode = "political"
        self.font = self.loader.loadFont(str(FONTS / "EBGaramond.ttf"))
        self.title_font = self.loader.loadFont(str(FONTS / "Cinzel.ttf"))
        for f in (self.font, self.title_font):
            f.setPixelsPerUnit(64)
        self.labels = Labels(self.provmap, self.world.height_at, self.title_font, self.render)
        self.realm_labels = RealmLabels(self.provmap, self.owner_of, REALM_NAMES, self.world.height_at,
                                        self.title_font, self.render,
                                        capitals={tag: r["capital"] for tag, r in self.realms.items()})
        self.hovered = None
        self.camera_ctl = StrategyCamera(self.camera, self.camLens, self.world.height_at)
        self.camera_ctl.look_at(*self.world_xy(25.5, 44.0), 1100)
        self.info = OnscreenText(text="", pos=(-1.7, 0.9), scale=0.05, align=TextNode.ALeft, fg=(1, 0.95, 0.85, 1),
                                 shadow=(0, 0, 0, 0.8), font=self.font, mayChange=True, parent=self.aspect2d)
        self.redraw_overlay()
        from .game.calendar import START
        from .game.navigation import Navigation
        from .render.orders import RouteRibbon
        self.date = START
        self.nav = Navigation(self.world.ground, self.provmap)
        self.ribbon = RouteRibbon(self.render, self.world.height_at)
        self.chosen = None
        self.realm_names = REALM_NAMES
        self.armies, self.figures = self.first_armies()
        self.date_text = OnscreenText(text=str(self.date), pos=(0, 0.9), scale=0.065, fg=(0.24, 0.15, 0.08, 1),
                                      shadow=(0.96, 0.9, 0.75, 0.9), font=self.title_font, mayChange=True,
                                      parent=self.aspect2d)
        self.army_text = OnscreenText(text="", pos=(-1.7, -0.75), scale=0.05, align=TextNode.ALeft,
                                      fg=(1, 0.95, 0.85, 1), shadow=(0, 0, 0, 0.8), font=self.font, mayChange=True,
                                      parent=self.aspect2d)
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
        self.accept("escape", sys.exit)
        self.dragging = None
        self.last_mouse = None
        self.Vec3 = Vec3
        self.taskMgr.add(self.tick, "tick")

    def first_armies(self):
        """The armies in the field in August 1402 (until the campaign raises them for real)."""
        from .game.armies import HORSE_MARCH_KM, Army
        from .render.figures import ArmyFigure
        from .render.world import SUN
        hosts = [  # realm, town, men, light horse, accent, eastern dress
            ("wallachia", "targoviste", 9000, True, (0.20, 0.30, 0.62), False),
            ("ott_rum", "edirne", 14000, False, (0.94, 0.92, 0.86), True),
            ("hungary", "buda", 12000, False, (0.94, 0.92, 0.86), False),
            ("serbia", "krusevac", 6000, False, (0.85, 0.75, 0.40), False),
            ("moldavia", "suceava", 7000, True, (0.85, 0.72, 0.30), False),
        ]
        armies, figures = [], {}
        for realm, town, men, horse, accent, eastern in hosts:
            x, y = self.provmap.provinces[town].town
            army = Army(f"{realm}-1", realm, f"Army of {self.realm_names[realm]}", x, y, men)
            if horse:
                army.march_km = army.moves = HORSE_MARCH_KM
            color = tuple(c / 255 for c in self.colors[realm])
            figure = ArmyFigure(self.render, self.world.height_at, color, accent, SUN, eastern=eastern)
            figure.place(x, self.geo.HEIGHT - y)
            armies.append(army)
            figures[army.id] = figure
        return armies, figures

    # --- armies and their orders ----------------------------------------------------------------

    def army_at(self, p):
        """The army whose miniature is under world point p, if any."""
        reach = max(7.0, self.camera_ctl.distance * 0.025)
        best = None
        for army in self.armies:
            figure = self.figures[army.id]
            d = math.hypot(figure.pos.x - p.x, figure.pos.y - p.y)
            if d < reach:
                best, reach = army, d
        return best

    def choose(self, army):
        self.chosen = army
        self.show_orders()

    def show_orders(self):
        """Show the chosen army's reach this month, its route, and what it is about."""
        from .render.orders import months_of, reach_field
        army = self.chosen
        if army is None:
            self.world.set_reach(None)
            self.ribbon.hide()
            self.army_text.setText("")
            return
        if army.moves >= 1:
            self.world.set_reach(*reach_field(army.reach(self.nav)))
        else:
            self.world.set_reach(None)
        months = months_of(army.route, army.moves, army.march_km) if army.route else []
        if months:
            self.ribbon.show(months)
        else:
            self.ribbon.hide()
        lines = [army.name, f"{army.men:,} men",
                 f"Can still march {army.moves:.0f} of {army.march_km:.0f} km this month"]
        if army.route:
            more = math.ceil(max(0.0, army.route.cost - army.moves) / army.march_km)
            lines.append("Arrives this month" if more == 0 else f"Arrives in {more} more month{'s' * (more > 1)}")
        self.army_text.setText("\n".join(lines))

    def order_march(self, army, x, y):
        """March the army towards map pixel (x, y): as far as it can this month, the rest are orders."""
        if not army.order(self.nav, x, y):
            return False
        self.walk(army)
        return True

    def walk(self, army):
        walked = army.march()
        if len(walked) > 1:
            self.figures[army.id].march(self._strides(walked))

    def _strides(self, points):
        """World points every few units along a march in map pixels, for the miniature to walk."""
        out = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            steps = max(1, int(math.hypot(bx - ax, by - ay) / 4))
            out += [(ax + (bx - ax) * k / steps, self.geo.HEIGHT - (ay + (by - ay) * k / steps))
                    for k in range(1, steps + 1)]
        return out

    def end_month(self):
        """The month is over: every army gets its movement back and carries on with its orders."""
        import random
        self.date = self.date.next()
        self.date_text.setText(str(self.date))
        towns = [p for p in self.provmap.provinces.values()]
        for army in self.armies:
            army.new_month()
            if army.route is None and army is not self.chosen:
                # until there is an AI: wander to a town of the realm or of its neighbours
                own = [p for p in towns if p.owner == army.owner]
                if own:
                    target = random.choice(own)
                    army.order(self.nav, *target.town)
            self.walk(army)
        self.show_orders()

    # --- coordinates ----------------------------------------------------------------------------

    def world_xy(self, lon, lat):
        x, y = self.geo.to_map(lon, lat)
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

    # --- input ----------------------------------------------------------------------------------

    def _drag(self, kind):
        self.dragging = kind
        self.last_mouse = None

    def _right_down(self):
        """Right button: drag to turn the view, click to order the chosen army to march."""
        self._drag("turn")
        m = self.mouseWatcherNode.getMouse() if self.mouseWatcherNode.hasMouse() else None
        self.right_from = (m.x, m.y) if m is not None else None
        self.turned = 0.0

    def _right_up(self):
        self._drag(None)
        if self.chosen is None or self.right_from is None or not self.mouseWatcherNode.hasMouse():
            return
        m = self.mouseWatcherNode.getMouse()
        if math.hypot(m.x - self.right_from[0], m.y - self.right_from[1]) > 0.02:
            return
        p = self.mouse_ground()
        if p is not None and self.order_march(self.chosen, p.x, self.geo.HEIGHT - p.y):
            self.show_orders()

    def pick(self):
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
        if prov:
            realm = self.realms.get(prov.owner, {})
            ruler = realm.get("ruler", {})
            self.info.setText(f"{prov.name}\n{realm.get('name', prov.owner)}\n{realm.get('title', '')} "
                              f"{ruler.get('name', '')}\n{prov.terrain}, {prov.culture}, "
                              f"{prov.religion.replace('_', ' ')}\n{prov.population * 1000:,.0f} people, "
                              f"{prov.area:,} km²")
        else:
            self.info.setText("")

    def set_mode(self, mode):
        self.mode = mode
        self.redraw_overlay()

    def redraw_overlay(self):
        pal = self.overlay.palette(lambda p: self.colors.get(self.owner_of.get(p.id)))
        self.world.set_palette(pal, mix=0.62 if self.mode == "political" else 0.0)
        self.world.set_highlight(self.selected, getattr(self, "hovered", None))

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
        for figure in self.figures.values():
            figure.update(dt, task.time)
        self.ribbon.update(self.camera_ctl.distance, task.time)
        self.labels.update(self.camera_ctl.distance, self.camera_ctl.heading)
        self.realm_labels.update(self.camera_ctl.distance)
        p = self.mouse_ground()
        prov = self.provmap.at(p.x, self.geo.HEIGHT - p.y) if p is not None else None
        hovered = prov.index if prov else None
        if hovered != self.hovered:
            self.hovered = hovered
            self.world.set_highlight(self.selected, hovered)
        return task.cont

    # --- pictures for checking the map without a display ----------------------------------------

    def shots(self, folder, only=None):
        folder.mkdir(parents=True, exist_ok=True)
        views = {
            "overview": (28.0, 42.0, 1900, 0, "political"),
            "balkans": (22.5, 42.5, 700, 0, "political"),
            "wallachia": (25.5, 44.6, 380, 0, "political"),
            "carpathians_terrain": (25.0, 45.6, 330, 20, "terrain"),
            "constantinople": (28.9, 41.0, 160, 330, "political"),
            "march": (24.6, 43.9, 760, 0, "political"),
            "march_close": (24.9, 44.0, 260, 340, "political"),
            "march_next": (24.2, 43.3, 600, 0, "political"),
        }
        wallachia = next(a for a in self.armies if a.owner == "wallachia")
        for name, (lon, lat, dist, heading, mode) in views.items():
            if name == "march":   # the plan, before the first step
                wallachia.march_km = wallachia.moves = 220.0
                wallachia.order(self.nav, *self.provmap.provinces["sofia"].town)
                self.choose(wallachia)
            if name == "march_next":
                self.walk(wallachia)
                self._settle()
                self.end_month()
                self._settle()
            if only and name not in only:
                continue
            self.mode = mode
            self.selected = self.provmap.provinces["targoviste"].index if name == "wallachia" else None
            self.redraw_overlay()
            self.camera_ctl.heading = heading
            self.camera_ctl.look_at(*self.world_xy(lon, lat), dist)
            self.world.update(self.camera_ctl.position, 2.0)
            self.ribbon.update(self.camera_ctl.distance, 2.0)
            self.labels.update(self.camera_ctl.distance, self.camera_ctl.heading)
            self.realm_labels.update(self.camera_ctl.distance)
            for _ in range(2):
                self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(str(folder / f"{name}.png"))
            print("saved", name)

    def _settle(self):
        """Let the miniatures finish their marches (for the pictures)."""
        for _ in range(4000):
            if not any(f.marching for f in self.figures.values()):
                break
            for f in self.figures.values():
                f.update(0.05, 1.0)


if __name__ == "__main__":
    main()
