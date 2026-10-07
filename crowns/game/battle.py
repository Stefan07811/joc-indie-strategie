"""Tactical battles: the armies' regiments on a field, fought out second by second.

The field is a few kilometres of the land where the armies met: plains, hills, woods or marsh, maybe a
stream. Each regiment is a block of men with a frontage and a depth. It marches where it is ordered,
or towards the enemy it is told to attack; missile troops shoot at what comes in range; blocks in
contact fight, harder in front than on the flanks, horse charging home harder after a run; the losses,
being taken in the flank and seeing friends run all wear down morale, and a broken regiment flees for
its edge of the field. The battle is over when one side has no regiment left standing.

No graphics here: the battle can be played, tested, or fought by two AIs.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

FIELD_W, FIELD_H = 2400.0, 1600.0            # metres
DEPLOY_DEPTH = 350.0                          # each side deploys this deep from its edge
WALK = {"foot": 1.3, "missile": 1.3, "horse": 2.8}       # m/s, in good order
RUN = {"foot": 2.6, "missile": 2.6, "horse": 6.5}
RANGE = {"missile": 190.0}
HORSE_ARCHERS = {"horse_archers", "akinjis", "sipahis", "mamluks", "calarasi", "mirza_horse", "kurdish_horse",
                 "stratiotai"}
HORSE_RANGE = 140.0
VOLLEY = 4.0                                  # seconds between volleys
AMMO = 30
MELEE_RATE = 0.025                            # blows a second from each man in the front ranks
MISSILE_RATE = 0.03                           # arrows that tell, a volley, from each archer
PRESSURE = 0.12                               # nerve lost a second in melee, by how the fight is going
BREAK = 15.0                                  # morale under which a regiment flees
TIME_LIMIT = 1800.0                           # seconds: then the defender holds the field


@dataclass
class Unit:
    id: int
    side: int                                 # 0 = attacker, 1 = defender
    unit: str                                 # a key of rules.UNITS
    men: int
    start_men: int
    x: float
    y: float
    facing: float                             # radians, 0 = towards +y
    melee: float
    missile: float
    defence: float
    morale_base: float
    kind: str                                 # foot, missile, horse
    experience: float = 0.0
    morale: float = 60.0
    ammo: int = AMMO
    order: Optional[tuple] = None             # ("move", x, y) / ("attack", unit id) / None (hold)
    state: str = "formed"                     # formed, fighting, routing, gone
    reload: float = 0.0
    charge: float = 0.0                       # metres run straight towards the enemy
    charging: float = 0.0                     # seconds of charge bonus left
    general: bool = False
    still: float = 0.0                        # seconds since it last moved
    regiment: int = 0                         # index of the regiment in its army
    shocked: set = field(default_factory=set)

    @property
    def alive(self):
        return self.state not in ("gone",) and self.men > 0

    @property
    def standing(self):
        return self.alive and self.state != "routing"

    @property
    def frontage(self):
        return float(np.clip(math.sqrt(self.men) * (3.2 if self.kind == "horse" else 2.6), 24, 130))

    @property
    def depth(self):
        return max(12.0, self.frontage * (0.45 if self.kind == "horse" else 0.32))

    @property
    def radius(self):
        return math.hypot(self.frontage, self.depth) / 2

    def speed(self, running):
        table = RUN if running else WALK
        return table[self.kind]

    def ranged(self):
        if self.kind == "missile":
            return RANGE["missile"]
        if self.unit in HORSE_ARCHERS and self.missile >= 4:
            return HORSE_RANGE
        return 0.0


class Field:
    """The ground: heights (metres) and woods on a grid, with a stream perhaps."""

    CELL = 20.0

    def __init__(self, terrain="plains", seed=0, river=False):
        rng = np.random.default_rng(seed)
        nx, ny = int(FIELD_W / self.CELL) + 1, int(FIELD_H / self.CELL) + 1
        y, x = np.mgrid[0:ny, 0:nx] / max(nx, ny)
        relief = {"plains": 18, "steppe": 8, "hills": 70, "mountains": 140, "forest": 30, "marsh": 4,
                  "desert": 20}.get(terrain, 20)
        h = np.zeros((ny, nx))
        for scale, amp in ((2, 1.0), (5, 0.45), (11, 0.2)):
            g = rng.normal(0, 1, (scale + 2, scale + 2))
            gy = np.linspace(0, scale, ny)
            gx = np.linspace(0, scale, nx)
            y0, x0 = gy.astype(int), gx.astype(int)
            fy, fx = (gy - y0)[:, None], (gx - x0)[None, :]
            fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
            a, b = g[y0][:, x0], g[y0][:, x0 + 1]
            c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
            h += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        self.height = (h - h.min()) * relief / max(1e-6, np.ptp(h))
        woods_share = {"forest": 0.35, "hills": 0.15, "mountains": 0.2, "plains": 0.06, "marsh": 0.05}.get(terrain, 0.03)
        noise = rng.random((ny // 6 + 2, nx // 6 + 2))
        woods = np.kron(noise, np.ones((6, 6)))[:ny, :nx]
        # keep the middle of the field mostly open
        woods = woods * (0.6 + 0.8 * np.abs(y - 0.5 * ny / max(nx, ny)))
        self.woods = woods > (1 - woods_share)
        self.marsh = terrain == "marsh"
        self.river = None
        if river:
            xs = np.linspace(0, FIELD_W, 40)
            ys = FIELD_H / 2 + 120 * np.sin(xs / 400 + rng.uniform(0, 6)) + rng.uniform(-80, 80)
            self.river = list(zip(xs, ys))
            for i, (rx, ry) in enumerate(self.river):
                cx = int(rx / self.CELL)
                for j in range(-2, 3):
                    cy = int(ry / self.CELL) + j
                    if 0 <= cy < ny and 0 <= cx < nx:
                        self.height[cy, cx] = max(0, self.height[cy, cx] - 4)
        self.terrain = terrain

    def _cell(self, x, y):
        return (int(np.clip(y / self.CELL, 0, self.height.shape[0] - 1)),
                int(np.clip(x / self.CELL, 0, self.height.shape[1] - 1)))

    def h(self, x, y):
        return float(self.height[self._cell(x, y)])

    def wooded(self, x, y):
        return bool(self.woods[self._cell(x, y)])

    def near_river(self, x, y):
        if not self.river:
            return False
        return min(math.hypot(x - rx, y - ry) for rx, ry in self.river[::2]) < 25

    def going(self, x, y, kind):
        """How quickly men move here (1 = open ground)."""
        f = 1.0
        if self.wooded(x, y):
            f *= 0.55 if kind != "horse" else 0.4
        if self.marsh:
            f *= 0.7
        if self.near_river(x, y):
            f *= 0.35
        return f


def _angle_to(a, x, y):
    return math.atan2(x - a.x, y - a.y)


def _hit(attack, defence, base=0.3):
    """The share of blows (or arrows) that tell: skill against armour and shield."""
    return min(0.95, max(0.04, base + 0.045 * (attack - defence)))


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Battle:
    """A battle between two armies of the campaign: the attacker (side 0) comes from the south edge."""

    def __init__(self, attacker, defender, unit_types, terrain="plains", seed=0, river=False,
                 attacker_leadership=1.0, defender_leadership=1.0, place="the field"):
        self.field = Field(terrain, seed, river)
        self.rng = np.random.default_rng(seed + 7919)
        self.place = place
        self.terrain = terrain
        self.armies = (attacker, defender)
        self.leadership = (attacker_leadership, defender_leadership)
        self.units = []
        self.time = 0.0
        self.started = False
        self.winner = None
        self.log = []
        self.events = []                  # (kind, ...) for the eyes: volleys and charges
        for side, army in enumerate(self.armies):
            self._deploy(side, army, unit_types)

    def _deploy(self, side, army, unit_types):
        """Line the regiments up: foot in the centre, missile troops in front, horse on the wings."""
        regs = list(enumerate(army.regiments))
        foot = [(i, r) for i, r in regs if unit_types[r.unit].kind == "foot"]
        missile = [(i, r) for i, r in regs if unit_types[r.unit].kind == "missile"]
        horse = [(i, r) for i, r in regs if unit_types[r.unit].kind == "horse"]
        y_line = 220.0 if side == 0 else FIELD_H - 220.0
        forward = 1 if side == 0 else -1
        facing = 0.0 if side == 0 else math.pi
        wings = len(horse) > 1
        rows = [(missile, y_line + forward * 70), (foot, y_line), (horse, y_line - forward * (30 if wings else 90))]
        line = foot or missile
        half = min(150.0, (FIELD_W - 500) / max(1, len(line))) * (len(line) - 1) / 2 + 60 if line else 0.0
        general_done = False
        for group, y in rows:
            if not group:
                continue
            spacing = min(150.0, (FIELD_W - 500) / max(1, len(group)))
            x0 = FIELD_W / 2 - spacing * (len(group) - 1) / 2
            for k, (i, r) in enumerate(group):
                t = unit_types[r.unit]
                x = x0 + k * spacing
                if group is horse and wings:            # horse on the wings of the line
                    left = k % 2 == 0
                    x = FIELD_W / 2 + (-1 if left else 1) * (half + 110 + 120 * (k // 2))
                u = Unit(len(self.units), side, r.unit, r.men, r.men, x, y, facing, t.melee, t.missile, t.defence,
                         t.morale, t.kind, r.experience, regiment=i)
                u.morale = 45 + 3.5 * t.morale + 15 * r.experience
                if not general_done and t.kind == "horse":
                    u.general, general_done = True, True
                self.units.append(u)
        if not general_done:
            mine = [u for u in self.units if u.side == side]
            if mine:
                mine[0].general = True

    # --- orders ----------------------------------------------------------------------------------

    def unit(self, uid):
        return self.units[uid]

    def side_units(self, side, standing=True):
        return [u for u in self.units if u.side == side and (u.standing if standing else u.alive)]

    def can_deploy(self, u, x, y):
        if self.started:
            return False
        lo, hi = (0, DEPLOY_DEPTH) if u.side == 0 else (FIELD_H - DEPLOY_DEPTH, FIELD_H)
        return 40 <= x <= FIELD_W - 40 and lo <= y <= hi

    def place_unit(self, u, x, y):
        if self.can_deploy(u, x, y):
            u.x, u.y = x, y
            return True
        return False

    def move(self, u, x, y):
        if u.standing:
            u.order = ("move", float(np.clip(x, 20, FIELD_W - 20)), float(np.clip(y, 20, FIELD_H - 20)))
            u.charge = 0.0

    def attack(self, u, target):
        if u.standing and target.alive and target.side != u.side:
            u.order = ("attack", target.id)
            u.charge = 0.0

    def halt(self, u):
        u.order = None

    def begin(self):
        self.started = True
        self.log.append("The battle begins.")

    # --- the fighting -----------------------------------------------------------------------------

    def step(self, dt):
        """Advance the battle by dt seconds of battle time."""
        if not self.started or self.winner is not None:
            return
        self.time += dt
        order = self.rng.permutation(len(self.units))   # nobody always moves first
        for i in order:
            u = self.units[i]
            if u.alive:
                self._act(u, dt)
        self._melee(dt)
        self._missiles(dt)
        self._morale(dt)
        self._check_end()

    def _enemies(self, u):
        return [e for e in self.units if e.side != u.side and e.alive]

    def _nearest(self, u, standing=True):
        foes = [e for e in self._enemies(u) if (e.standing or not standing)]
        return min(foes, key=lambda e: math.hypot(e.x - u.x, e.y - u.y), default=None)

    def _act(self, u, dt):
        u.still += dt
        if u.charging > 0:
            u.charging = max(0.0, u.charging - dt)
        if u.state == "routing":
            # run for our own edge of the field and leave it
            edge = -100 if u.side == 0 else FIELD_H + 100
            u.facing = 0.0 if edge > u.y else math.pi
            u.y += math.copysign(u.speed(True) * dt * self.field.going(u.x, u.y, u.kind), edge - u.y)
            if (u.side == 0 and u.y < -40) or (u.side == 1 and u.y > FIELD_H + 40):
                u.state = "gone"
            return
        if u.state == "fighting":
            return   # locked in melee
        target = None
        goal = None
        if u.order and u.order[0] == "attack":
            target = self.units[u.order[1]]
            if not target.alive:
                u.order = None
                target = None
        elif u.order and u.order[0] == "move":
            goal = (u.order[1], u.order[2])
        if target is not None:
            reach = u.ranged()
            dist = math.hypot(target.x - u.x, target.y - u.y)
            if reach and u.ammo > 0 and dist <= reach * 0.9:
                u.facing = _angle_to(u, target.x, target.y)
                return   # shoot from where we stand
            goal = (target.x, target.y)
        if goal is None:
            return
        gx, gy = goal
        dist = math.hypot(gx - u.x, gy - u.y)
        if dist < 3:
            u.order = None if u.order and u.order[0] == "move" else u.order
            return
        want = math.atan2(gx - u.x, gy - u.y)
        turn = _wrap(want - u.facing)
        u.facing += max(-1.5 * dt, min(1.5 * dt, turn))
        running = target is not None and dist < 160
        step = min(dist, u.speed(running) * dt * self.field.going(u.x, u.y, u.kind))
        if abs(turn) < 0.6:
            u.x += math.sin(u.facing) * step
            u.y += math.cos(u.facing) * step
            u.still = 0.0
            if target is not None and u.kind == "horse":
                u.charge += step
            else:
                u.charge = 0.0
        # blocks do not walk through each other
        for o in self.units:
            if o is u or not o.alive or o.state == "routing":
                continue
            d = math.hypot(o.x - u.x, o.y - u.y)
            need = (u.depth + o.depth) / 2 + 2
            if d < need:
                if o.side != u.side:
                    self._engage(u, o)
                elif d > 1e-3:
                    push = (need - d) / d * 0.5
                    u.x -= (o.x - u.x) * push
                    u.y -= (o.y - u.y) * push

    def _engage(self, a, b):
        for u, o in ((a, b), (b, a)):
            if u.state != "routing":
                u.state = "fighting"
                u.order = ("attack", o.id)
        if a.kind == "horse" and a.charge > 80:
            a.charging = 8.0
            self.log.append(f"{self.name(a)} charges home.")
            self.events.append(("charge", a.id, b.id))
        a.charge = 0.0

    def name(self, u):
        from .rules import UNITS
        side = ("Our", "Their")[u.side]
        return f"{side} {UNITS[u.unit].name}"

    def _strength(self, u, foe):
        """A regiment's fighting strength against `foe`, with the ground and the angle of attack."""
        s = u.melee * (1.0 + 0.5 * u.experience) * self.leadership[u.side]
        front = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing)) < 1.0
        if u.charging > 0:
            bonus = 1.8 if u.melee >= 12 else 1.4
            if front and foe.kind != "horse" and foe.still > 4:
                bonus = 1.0 + (bonus - 1.0) * 0.4      # foot standing firm, spears levelled, blunts the charge
            s *= bonus
        if u.still > 20 and u.kind != "horse":
            s *= 1.1                                   # men who waited in their ranks for the blow
        if u.kind == "horse" and self.field.wooded(u.x, u.y):
            s *= 0.6
        if self.field.h(u.x, u.y) > self.field.h(foe.x, foe.y) + 4:
            s *= 1.15     # fighting down a slope
        # where the blow lands on the foe: front, flank or rear
        angle = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing))
        if angle > 2.2:
            s *= 1.8
        elif angle > 1.0:
            s *= 1.35
        return s

    def _melee(self, dt):
        pairs = []
        for u in self.units:
            if u.state != "fighting" or not u.alive:
                continue
            foes = [e for e in self._enemies(u) if e.state != "gone" and
                    math.hypot(e.x - u.x, e.y - u.y) < (u.depth + e.depth) / 2 + 12]
            if not foes:
                u.state = "formed"
                continue
            foe = min(foes, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
            pairs.append((u, foe))
        hits, dealt = {}, {}
        for u, foe in pairs:
            engaged = min(u.men, u.frontage * 2.2)
            dmg = engaged * MELEE_RATE * _hit(self._strength(u, foe), foe.defence) * dt * self.rng.uniform(0.6, 1.4)
            if foe.state == "routing":
                dmg *= 2.5    # cut down as they run
            hits[foe.id] = hits.get(foe.id, 0.0) + dmg
            dealt[u.id] = dealt.get(u.id, 0.0) + dmg / max(1, foe.start_men)
            angle = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing))
            if angle > 1.0 and u.id not in foe.shocked:
                foe.shocked.add(u.id)
                foe.morale -= 12 if angle > 2.2 else 7
        for u, foe in pairs:
            # a regiment losing the fight loses heart faster than one winning it
            taken = hits.get(u.id, 0.0) / max(1, u.start_men)
            ratio = (taken + 1e-4) / (dealt.get(u.id, 0.0) + 1e-4)
            u.morale -= PRESSURE * dt * min(4.0, max(0.25, ratio))
        for uid, dmg in hits.items():
            self._lose(self.units[uid], dmg)

    def _missiles(self, dt):
        hits = []
        for u in self.units:
            reach = u.ranged()
            if not reach or u.ammo <= 0 or not u.standing or u.state == "fighting":
                continue
            u.reload -= dt
            if u.reload > 0:
                continue
            foes = [e for e in self._enemies(u) if e.state != "gone" and
                    math.hypot(e.x - u.x, e.y - u.y) <= reach]
            if not foes:
                continue
            target = None
            if u.order and u.order[0] == "attack" and self.units[u.order[1]] in foes:
                target = self.units[u.order[1]]
            target = target or min(foes, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
            u.reload = VOLLEY
            u.ammo -= 1
            dist = math.hypot(target.x - u.x, target.y - u.y)
            accuracy = 1.2 - 0.6 * dist / reach
            cover = 0.5 if self.field.wooded(target.x, target.y) else 1.0
            skill = u.missile * (1 + 0.3 * u.experience)
            dmg = u.men * MISSILE_RATE * _hit(skill, target.defence, 0.25) * accuracy * cover * \
                self.rng.uniform(0.5, 1.5)
            hits.append((target, dmg))
            self.events.append(("volley", u.id, target.id))
        for target, dmg in hits:   # the volleys of a moment land together
            self._lose(target, dmg)
            target.morale -= 0.6 * dmg / max(1, target.men) * 100 * 0.3

    def _lose(self, u, dmg):
        dead = min(u.men, int(dmg) + (1 if self._chance(dmg - int(dmg)) else 0))
        if dead <= 0:
            return
        before = u.men
        u.men -= dead
        u.morale -= 120.0 * dead / max(1, u.start_men)
        if u.men <= 0:
            u.men = 0
            u.state = "gone"
            self.log.append(f"{self.name(u)} is destroyed.")
            self._shock(u)
        elif before > 0 and u.general and u.men < u.start_men * 0.35 and "general" not in u.shocked:
            u.shocked.add("general")
            self.log.append(f"{('Our', 'Their')[u.side]} general's guard is cut to pieces.")
            for o in self.side_units(u.side):
                o.morale -= 12

    def _chance(self, p):
        return self.rng.random() < p

    def _shock(self, u):
        for o in self.side_units(u.side):
            if math.hypot(o.x - u.x, o.y - u.y) < 300:
                o.morale -= 6

    def _morale(self, dt):
        for u in self.units:
            if not u.alive:
                continue
            if u.state == "routing":
                continue
            # rest restores a little nerve
            if u.state == "formed":
                u.morale = min(45 + 3.5 * u.morale_base + 15 * u.experience, u.morale + 0.4 * dt)
            if u.morale < BREAK + self.rng.uniform(-4, 4):
                u.state = "routing"
                u.order = None
                self.log.append(f"{self.name(u)} breaks and flees!")
                self._shock(u)

    def _check_end(self):
        standing = [self.side_units(s) for s in (0, 1)]
        if not standing[0] or not standing[1]:
            self.winner = 1 if not standing[0] else 0
        elif self.time >= TIME_LIMIT:
            self.winner = 1
            self.log.append("Night falls: the attackers withdraw.")
        if self.winner is not None:
            # the beaten who are still on the field are caught as they flee
            for u in self.units:
                if u.side != self.winner and u.alive:
                    u.men = int(u.men * 0.8)
            self.log.append(("The attackers" if self.winner == 0 else "The defenders") + " carry the field.")

    # --- the AI ---------------------------------------------------------------------------------

    def ai(self, side):
        """The captains' plan. The line goes forward together; the archers shoot at what comes near and give
        ground before a charge; the horse keeps level on the wings and, once the lines are locked, falls on
        flanks and archers; horse archers ride off from what would catch them. The defender lets the attack
        come on, unless it is the one being out-shot."""
        mine = self.side_units(side)
        foes = [e for e in self.units if e.side != side and e.standing]
        if not mine or not foes:
            return
        forward = 1 if side == 0 else -1

        def dist(a, b):
            return math.hypot(a.x - b.x, a.y - b.y)

        line = [u for u in mine if u.kind != "horse"] or mine
        line_y = sum(u.y for u in line) / len(line)
        closest = min(dist(u, e) for u in line for e in foes)
        engaged = any(u.state == "fighting" for u in self.units)
        shooting = sum(u.men * u.missile for u in mine if u.ranged())
        against = sum(e.men * e.missile for e in foes if e.ranged())
        hold = side == 1 and self.time < 300 and closest > 300 and shooting >= 0.7 * against
        for u in mine:
            if u.state == "fighting":
                continue
            nearest = min(foes, key=lambda e: dist(u, e))
            d = dist(u, nearest)
            melee_near = [e for e in foes if not e.ranged() and e.state != "fighting" and dist(u, e) < 110]
            reach = u.ranged()
            if reach and u.ammo > 0:
                if melee_near and u.kind == "horse":          # ride off and shoot again
                    e = melee_near[0]
                    away = math.atan2(u.x - e.x, u.y - e.y)
                    self.move(u, u.x + math.sin(away) * 160, u.y + math.cos(away) * 160)
                elif melee_near and (u.y - line_y) * forward > -30:   # give ground behind the line
                    self.move(u, u.x, u.y - forward * 90)
                elif u.order and u.order[0] == "move" and melee_near:
                    continue
                elif d <= reach or not hold:
                    self.attack(u, nearest)
                continue
            if u.order and u.order[0] == "attack" and self.units[u.order[1]].standing:
                continue
            if u.kind == "horse":
                if engaged or d < 160:
                    locked = [e for e in foes if e.state == "fighting"]
                    shooters = [e for e in foes if e.kind == "missile"]
                    self.attack(u, min(shooters + locked or foes, key=lambda e: dist(u, e)))
                elif not hold and abs(u.y - line_y) > 25:      # keep level with the line
                    self.move(u, u.x, line_y - forward * 10)
                continue
            if hold:
                continue
            if d < 260 or engaged:
                self.attack(u, nearest)
            elif (u.y - line_y) * forward > 40:                # wait for the rest of the line
                self.halt(u)
            else:
                self.move(u, u.x, u.y + forward * min(150.0, d - 220))

    def run(self, dt=1.0, ai_sides=(0, 1), limit=None):
        """Fight it out with the AI for the given sides (for auto-resolving and tests)."""
        if not self.started:
            self.begin()
        while self.winner is None and (limit is None or self.time < limit):
            for side in ai_sides:
                if int(self.time) % 5 == 0:
                    self.ai(side)
            self.step(dt)
        return self.winner

    # --- the outcome --------------------------------------------------------------------------------

    def survivors(self, side):
        """{regiment index: men left} for an army (the dead and the fled who never came back)."""
        return {u.regiment: max(0, u.men) for u in self.units if u.side == side}


def tactical(campaign, attacker, defender, seed=None):
    """A Battle between two armies of the campaign, on the ground where they meet."""
    from .rules import UNITS
    prov, terrain, place = campaign.battle_site(attacker, defender)
    seed = campaign.rng.randrange(1 << 30) if seed is None else seed
    river = terrain in ("plains", "steppe", "marsh") and (seed % 3 == 0)
    return Battle(attacker, defender, UNITS, terrain, seed, river, campaign.leadership(attacker),
                  campaign.leadership(defender), place)


def conclude(campaign, battle, attacker, defender):
    """Carry a fought battle's outcome back into the campaign."""
    winner = attacker if battle.winner == 0 else defender
    after = {}
    for side, army in ((0, attacker), (1, defender)):
        left = battle.survivors(side)
        after[army.id] = [left.get(i, r.men) for i, r in enumerate(army.regiments)]
    return campaign.conclude_battle(attacker, defender, winner, after)
