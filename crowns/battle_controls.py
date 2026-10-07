"""The player's hand on a tactical battle: choosing regiments (a click, shift-click, a box dragged over them,
control+number groups), marching them as a body or along a line dragged with the right button, and the
orders of the moment: formation, at the run, hold, skirmish, halt."""

import math

from direct.gui.DirectGui import DirectFrame
from panda3d.core import ModifierButtons, Point2, Point3

from .render.battlefield import UNIT

CLICK = 0.02          # how far (screen units) the mouse may move and still be a click
GAP = 12.0            # metres between regiments marching side by side


class BattleControls:
    """Mixed into the app. Needs: self.battle, self.battle_scene, self.battle_side, self.battle_cam."""

    def init_battle_controls(self):
        # modifiers are read by hand, so that shift-click and control+number reach us as plain events
        if self.mouseWatcherNode is not None and self.buttonThrowers:
            self.mouseWatcherNode.setModifierButtons(ModifierButtons())
            self.buttonThrowers[0].node().setModifierButtons(ModifierButtons())
        self.box_from = None
        self.box = None
        self.groups = {}
        self.line_from = None
        for key, call in (("r", self.toggle_run), ("h", self.toggle_hold), ("g", self.toggle_skirmish),
                          ("f", self.cycle_formation), ("backspace", self.halt_selected)):
            self.accept(key, self._in_battle, [call])
        self.accept("a", self._select_all_key)
        for n in range(10):
            self.accept(str(n), self._digit, [n])

    # --- helpers -------------------------------------------------------------------------------------

    def _in_battle(self, call):
        if self.in_battle:
            call()

    def _down(self, key):
        return self.mouseWatcherNode is not None and self.mouseWatcherNode.isButtonDown(key)

    def _chosen(self):
        b = self.battle
        return [b.units[uid] for uid in self.battle_scene.selected if b.units[uid].standing]

    def _mouse(self):
        if not self.mouseWatcherNode.hasMouse():
            return None
        m = self.mouseWatcherNode.getMouse()
        return (m.x, m.y)

    def _ground_m(self):
        """The point under the mouse, in metres on the field."""
        p = self.mouse_ground(self.battle_scene.height)
        return None if p is None else (p.x / UNIT, p.y / UNIT)

    def _screen(self, u):
        x, y = u.x * UNIT, u.y * UNIT
        p = self.cam.getRelativePoint(self.render, Point3(x, y, self.battle_scene.height(x, y) + 0.5))
        s = Point2()
        return (s.x, s.y) if self.camLens.project(p, s) else None

    # --- keys -----------------------------------------------------------------------------------------

    def _digit(self, n):
        if not self.in_battle:
            from .ui.mapmodes import MODES
            order = ["terrain", "political", "religion", "culture", "diplomacy", "trade"]
            if 1 <= n <= len(order):
                self.set_mode(order[n - 1])
            return
        if self._down("control"):
            self.groups[n] = set(self.battle_scene.selected)
        elif n in self.groups:
            self.battle_scene.selected = {uid for uid in self.groups[n] if self.battle.units[uid].standing}
            chosen = self._chosen()
            if chosen:
                self.battle_cam.look_at(sum(u.x for u in chosen) / len(chosen) * UNIT,
                                        sum(u.y for u in chosen) / len(chosen) * UNIT)

    def _select_all_key(self):
        if self.in_battle and self._down("control"):
            self.battle_scene.selected = {u.id for u in self.battle.side_units(self.battle_side)}
        elif not self.in_battle and not self._down("control"):
            pass   # "a" also pans the map: handled by the movement keys

    def toggle_run(self):
        chosen = self._chosen()
        on = not all(u.run for u in chosen)
        for u in chosen:
            u.run = on

    def toggle_hold(self):
        chosen = self._chosen()
        stance = "free" if all(u.stance == "hold" for u in chosen) else "hold"
        for u in chosen:
            self.battle.set_stance(u, stance)
            if stance == "hold":
                self.battle.halt(u)

    def toggle_skirmish(self):
        chosen = [u for u in self._chosen() if u.ranged()]
        stance = "free" if all(u.stance == "skirmish" for u in chosen) else "skirmish"
        for u in chosen:
            self.battle.set_stance(u, stance)

    def cycle_formation(self):
        for u in self._chosen():
            options = u.formations()
            nxt = options[(options.index(u.formation) + 1) % len(options)] if u.formation in options else "line"
            self.battle.set_formation(u, nxt)

    def set_formation_selected(self, formation):
        for u in self._chosen():
            self.battle.set_formation(u, formation)

    def halt_selected(self):
        for u in self._chosen():
            self.battle.halt(u)

    # --- the left button: choose -----------------------------------------------------------------------

    def battle_left_down(self):
        self.box_from = self._mouse()

    def battle_left_up(self):
        start, end = self.box_from, self._mouse()
        self.box_from = None
        if self.box is not None:
            self.box.destroy()
            self.box = None
        if start is None or end is None:
            return
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= CLICK:
            return self.battle_pick()
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))
        inside = set()
        for u in self.battle.side_units(self.battle_side):
            s = self._screen(u)
            if s is not None and x0 <= s[0] <= x1 and y0 <= s[1] <= y1:
                inside.add(u.id)
        if self._down("shift"):
            self.battle_scene.selected |= inside
        else:
            self.battle_scene.selected = inside

    def update_box(self):
        """Draw the box being dragged."""
        if self.box_from is None:
            return
        m = self._mouse()
        if m is None or math.hypot(m[0] - self.box_from[0], m[1] - self.box_from[1]) <= CLICK:
            return
        x0, x1 = sorted((self.box_from[0], m[0]))
        y0, y1 = sorted((self.box_from[1], m[1]))
        if self.box is None:
            self.box = DirectFrame(parent=self.render2d, frameColor=(1.0, 0.85, 0.35, 0.18))
        self.box["frameSize"] = (x0, x1, y0, y1)

    def battle_pick(self):
        p = self._ground_m()
        if p is None:
            return
        scene, b = self.battle_scene, self.battle
        u = scene.unit_at(p[0] * UNIT, p[1] * UNIT)
        if u is not None and u.side == self.battle_side:
            if self._down("shift"):
                scene.selected ^= {u.id}
            else:
                scene.selected = {u.id}
            return
        if not b.started and scene.selected:
            self.march_as_body(self._chosen(), p, deploy=True)
            return
        scene.selected = set()

    # --- the right button: order -------------------------------------------------------------------------

    def battle_right_down(self):
        self.line_from = self._ground_m() if self.battle_scene.selected else None

    def battle_right_up(self, start_screen):
        end = self._mouse()
        if start_screen is None or end is None or self.over_gui():
            return
        dragged = math.hypot(end[0] - start_screen[0], end[1] - start_screen[1]) > CLICK
        chosen = self._chosen()
        if not chosen:
            return
        p = self._ground_m()
        if p is None:
            return
        if dragged and self.line_from is not None:
            self.form_line(chosen, self.line_from, p)
        elif not dragged:
            self.battle_order(chosen, p)
        self.line_from = None

    def battle_order(self, chosen, p):
        b = self.battle
        target = self.battle_scene.unit_at(p[0] * UNIT, p[1] * UNIT)
        if target is not None and target.side != self.battle_side:
            for u in chosen:
                b.attack(u, target)
            return
        if b.started:
            self.march_as_body(chosen, p)
        else:
            self.march_as_body(chosen, p, deploy=True)

    def march_as_body(self, chosen, p, deploy=False):
        """Keep the regiments' places about each other, the body facing the way it marches."""
        if not chosen:
            return
        cx = sum(u.x for u in chosen) / len(chosen)
        cy = sum(u.y for u in chosen) / len(chosen)
        facing = math.atan2(p[0] - cx, p[1] - cy) if math.hypot(p[0] - cx, p[1] - cy) > 30 else None
        for u in chosen:
            x, y = p[0] + (u.x - cx), p[1] + (u.y - cy)
            if deploy:
                self.battle.place_unit(u, x, y)
            else:
                self.battle.move(u, x, y, facing=facing)

    def form_line(self, chosen, a, b):
        """Spread the regiments along the line dragged from a to b, facing away from where they stand."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        cx = sum(u.x for u in chosen) / len(chosen)
        cy = sum(u.y for u in chosen) / len(chosen)
        nx, ny = -uy, ux
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if (mx - cx) * nx + (my - cy) * ny < 0:     # face away from where the regiments come from
            nx, ny = -nx, -ny
        facing = math.atan2(nx, ny)
        # keep their order along the line, so that no two cross on the way
        chosen = sorted(chosen, key=lambda u: (u.x - a[0]) * ux + (u.y - a[1]) * uy)
        need = sum(u.frontage for u in chosen) + GAP * (len(chosen) - 1)
        width = max(length, need)
        pos = -width / 2
        for u in chosen:
            share = u.frontage / need * width
            centre = pos + share / 2
            x, y = mx + ux * centre, my + uy * centre
            if self.battle.started:
                self.battle.move(u, x, y, facing=facing)
            else:
                self.battle.place_unit(u, x, y)
                u.facing = facing
            pos += share
