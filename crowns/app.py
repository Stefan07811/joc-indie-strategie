"""Crowns of the Balkans: the 3D map application.

    python -m crowns                  play (a window at the desktop's resolution)
    python -m crowns --shots DIR      render a few views to DIR and quit (works without a display)

Controls: WASD or the arrows move, the mouse wheel zooms, right-drag or Q/E turns, middle-drag moves,
left click picks a province, 1 / 2 switch between the terrain and the political map.
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
    parser.add_argument("--size", default=None, help="window size, e.g. 1920x1080")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--style", default="codex", help="the map's look: codex (the game's) or real (for checks)")
    args = parser.parse_args(argv)
    size = tuple(int(v) for v in args.size.split("x")) if args.size else None
    configure(offscreen=bool(args.shots), size=size or ((1600, 900) if args.shots else None),
              fullscreen=args.fullscreen)
    app = MapApp(style=args.style)
    if args.shots:
        app.shots(Path(args.shots))
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
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        from history_1402 import REALM_COLORS, REALM_NAMES

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
        self.colors = REALM_COLORS
        self.owner_of = {p.id: p.owner for p in self.provmap.provinces.values()}
        self.selected = None
        self.mode = "political"
        self.font = self.loader.loadFont(str(FONTS / "EBGaramond.ttf"))
        self.title_font = self.loader.loadFont(str(FONTS / "Cinzel.ttf"))
        for f in (self.font, self.title_font):
            f.setPixelsPerUnit(64)
        self.labels = Labels(self.provmap, self.world.height_at, self.title_font, self.render)
        self.realm_labels = RealmLabels(self.provmap, self.owner_of, REALM_NAMES, self.world.height_at,
                                        self.title_font, self.render)
        self.hovered = None
        self.camera_ctl = StrategyCamera(self.camera, self.camLens, self.world.height_at)
        self.camera_ctl.look_at(*self.world_xy(25.5, 44.0), 1100)
        self.info = OnscreenText(text="", pos=(-1.7, 0.9), scale=0.05, align=TextNode.ALeft, fg=(1, 0.95, 0.85, 1),
                                 shadow=(0, 0, 0, 0.8), font=self.font, mayChange=True, parent=self.aspect2d)
        self.redraw_overlay()
        self.armies = self.demo_armies()
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
        self.accept("mouse3", self._drag, ["turn"])
        self.accept("mouse3-up", self._drag, [None])
        self.accept("1", self.set_mode, ["terrain"])
        self.accept("2", self.set_mode, ["political"])
        self.accept("escape", sys.exit)
        self.dragging = None
        self.last_mouse = None
        self.Vec3 = Vec3
        self.taskMgr.add(self.tick, "tick")

    def demo_armies(self):
        """A few armies marching between towns, until the campaign (B3) moves them for real."""
        from .render.figures import ArmyFigure
        from .render.world import SUN
        towns = {p.id: (p.town[0], self.geo.HEIGHT - p.town[1]) for p in self.provmap.provinces.values()}
        routes = [  # realm, accent, eastern dress, the towns it marches through
            ("wallachia", (0.20, 0.30, 0.62), False, ["targoviste", "vlasia", "giurgiu"]),
            ("ott_rum", (0.94, 0.92, 0.86), True, ["edirne", "philippopolis", "sofia"]),
            ("hungary", (0.94, 0.92, 0.86), False, ["buda", "kalocsa", "szeged"]),
            ("serbia", (0.85, 0.75, 0.40), False, ["krusevac", "novo_brdo"]),
            ("moldavia", (0.85, 0.72, 0.30), False, ["suceava", "iasi", "roman"]),
        ]
        armies = []
        for realm, accent, eastern, stops in routes:
            color = tuple(c / 255 for c in self.colors[realm])
            army = ArmyFigure(self.render, self.world.height_at, color, accent, SUN, eastern=eastern)
            army.place(*towns[stops[0]])
            army.route = [towns[s] for s in stops]
            army.leg = 0
            armies.append(army)
        return armies

    def _march_on(self, army):
        """Send a demo army on to the next town of its route, and back again at the end."""
        army.leg = (army.leg + 1) % (2 * len(army.route) - 2 or 1)
        i = army.leg if army.leg < len(army.route) else 2 * len(army.route) - 2 - army.leg
        (x0, y0), (x1, y1) = (army.pos.x, army.pos.y), army.route[i]
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) / 6))
        army.march([(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps) for k in range(1, steps + 1)])

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

    def pick(self):
        p = self.mouse_ground()
        if p is None:
            return
        prov = self.provmap.at(p.x, self.geo.HEIGHT - p.y)
        self.selected = prov.index if prov else None
        self.redraw_overlay()
        if prov:
            self.info.setText(f"{prov.name}\nHeld by {prov.owner}\n{prov.terrain}, {prov.culture}, {prov.religion}\n"
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
        for army in self.armies:
            if not army.marching:
                self._march_on(army)
            army.update(dt, task.time)
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

    def shots(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        views = {
            "overview": (28.0, 42.0, 1900, 0, "political"),
            "balkans": (22.5, 42.5, 700, 0, "political"),
            "wallachia": (25.5, 44.6, 380, 0, "political"),
            "carpathians_terrain": (25.0, 45.6, 330, 20, "terrain"),
            "constantinople": (28.9, 41.0, 160, 330, "political"),
            "armies": (25.6, 44.4, 140, 20, "political"),
            "armies_close": (26.0, 44.45, 95, 330, "political"),
        }
        for army in self.armies:  # half way along their first march
            self._march_on(army)
            for _ in range(40):
                army.update(0.05, 1.0)
        for name, (lon, lat, dist, heading, mode) in views.items():
            self.mode = mode
            if name == "wallachia":
                self.selected = self.provmap.provinces["targoviste"].index
            self.redraw_overlay()
            self.camera_ctl.heading = heading
            self.camera_ctl.look_at(*self.world_xy(lon, lat), dist)
            self.world.update(self.camera_ctl.position, 2.0)
            self.labels.update(self.camera_ctl.distance, self.camera_ctl.heading)
            self.realm_labels.update(self.camera_ctl.distance)
            for _ in range(2):
                self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(str(folder / f"{name}.png"))
            print("saved", name)


if __name__ == "__main__":
    main()
