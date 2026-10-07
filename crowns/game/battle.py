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
AMMO = 24
MELEE_RATE = 0.025                            # blows a second from each man in the front ranks
MISSILE_RATE = 0.04                           # arrows that tell, a volley, from each archer
PRESSURE = 0.12                               # nerve lost a second in melee, by how the fight is going
HIT_SLOPE = 0.02                             # how much skill over armour counts for a blow to tell
HORSE_VOLLEY = 0.5                            # horse archers' time between volleys, against foot archers'
HORSE_MELEE = 1.8                             # riders against men on foot
# formations: (frontage, depth) against the plain line, and who may take them
FORMATIONS = {"line": (1.0, 1.0, ("foot", "missile", "horse")), "deep": (0.6, 1.7, ("foot",)),
              "wedge": (0.55, 1.6, ("horse",)), "square": (0.7, 1.4, ("foot",)),
              "loose": (1.5, 1.3, ("missile", "horse"))}
STANCES = ("free", "hold", "skirmish")
RUN_COST = 1.0                                # how fast running tires
TIRING = 0.15                                 # strength lost by a spent regiment
SHY = 60.0                                   # how near a charge comes before archers give ground
BREAK = 15.0                                  # morale under which a regiment flees
TIME_LIMIT = 1800.0                           # seconds: then the defender holds the field


from .siege import SiegeRules, make_walls  # noqa: E402


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
    formation: str = "line"                   # see FORMATIONS
    run: bool = False                         # march at the run (tiring)
    stance: str = "free"                      # free: engage what comes near; hold: stand; skirmish: keep away
    stamina: float = 100.0                    # wind and legs: running and fighting tire, rest restores
    face_to: Optional[float] = None           # the facing to take once the march is done
    army: int = 0                             # 0: the side's main army; 1, 2...: allies coming to its aid
    arrive: float = 0.0                       # battle time at which it comes onto the field
    climb: float = 0.0                        # seconds left on the ladders, storming a wall
    scaled: float = 0.0                       # seconds of disorder left after coming over a wall

    @property
    def alive(self):
        return self.state not in ("gone",) and self.men > 0

    @property
    def standing(self):
        return self.alive and self.state not in ("routing", "waiting")

    @property
    def frontage(self):
        line = float(np.clip(math.sqrt(self.men) * (3.2 if self.kind == "horse" else 2.6), 24, 130))
        return line * FORMATIONS[self.formation][0]

    @property
    def depth(self):
        f, d, _ = FORMATIONS[self.formation]
        line = float(np.clip(math.sqrt(self.men) * (3.2 if self.kind == "horse" else 2.6), 24, 130))
        return max(12.0, line * (0.45 if self.kind == "horse" else 0.32) * d)

    @property
    def armour(self):
        """Defence in the formation it holds: a wedge opens its flanks, a square closes up."""
        return self.defence + {"wedge": -2.0, "square": 1.0}.get(self.formation, 0.0)

    @property
    def tired(self):
        """1.0 fresh .. 0.85 spent."""
        return 1.0 - TIRING + TIRING * self.stamina / 100.0

    def formations(self):
        return [name for name, (_, _, kinds) in FORMATIONS.items() if self.kind in kinds]

    @property
    def radius(self):
        return math.hypot(self.frontage, self.depth) / 2

    def speed(self, running):
        table = RUN if running and self.stamina > 15 else WALK
        slow = 0.55 if self.formation == "square" else (0.85 if self.formation == "deep" else 1.0)
        return table[self.kind] * slow

    def ranged(self):
        if self.kind == "missile" or (self.kind == "foot" and self.missile >= 6):   # janissaries carry bows
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
        self.fords = []
        if river:
            xs = np.linspace(0, FIELD_W, 40)
            ys = FIELD_H / 2 + 120 * np.sin(xs / 400 + rng.uniform(0, 6)) + rng.uniform(-80, 80)
            self.river = list(zip(xs, ys))
            # two or three fords where the stream runs shallow
            self.fords = [self.river[k] for k in sorted(rng.choice(np.arange(5, 35), size=3, replace=False))]
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
        """In the stream (and not at a ford)."""
        if not self.river:
            return False
        if any(math.hypot(x - fx, y - fy) < 40 for fx, fy in self.fords):
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
    return min(0.95, max(0.04, base + HIT_SLOPE * (attack - defence)))


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Battle(SiegeRules):
    """A battle between two armies of the campaign: the attacker (side 0) comes from the south edge."""

    def __init__(self, attacker, defender, unit_types, terrain="plains", seed=0, river=False,
                 attacker_leadership=1.0, defender_leadership=1.0, place="the field", allies=None, siege=None):
        """allies: {side: [(army, seconds before it arrives), ...]}: armies near enough to join in.
        siege: {"fort", "progress", "town"} when the attacker storms a town held by the defender."""
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
        self.formed_up = set()            # the sides whose captains have chosen their formations
        self.allies = {0: [], 1: []}
        self.general_fate = {}            # side -> "killed" / "captured", for the general of the main army
        self.siege = make_walls(siege, FIELD_W, FIELD_H, self.rng) if siege else None
        for side, army in enumerate(self.armies):
            if self.siege is not None and side == 1:
                self._siege_deploy(side, army, unit_types)
            else:
                self._deploy(side, army, unit_types)
        for side, coming in (allies or {}).items():
            for k, (army, delay) in enumerate(coming, start=1):
                self.allies[side].append(army)
                first = len(self.units)
                self._deploy(side, army, unit_types)
                for u in self.units[first:]:
                    u.army, u.arrive, u.state, u.general = k, float(delay), "waiting", False
                    u.x = float(np.clip(u.x + (500 if k % 2 else -500), 60, FIELD_W - 60))
                    u.y = 20.0 if side == 0 else FIELD_H - 20.0

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

    def move(self, u, x, y, facing=None):
        if u.standing:
            u.order = ("move", float(np.clip(x, 20, FIELD_W - 20)), float(np.clip(y, 20, FIELD_H - 20)))
            u.charge = 0.0
            u.face_to = facing

    def attack(self, u, target):
        if u.standing and target.alive and target.side != u.side:
            u.order = ("attack", target.id)
            u.charge = 0.0

    def halt(self, u):
        u.order = None
        u.face_to = None

    def set_formation(self, u, formation):
        if formation in u.formations() and u.standing:
            u.formation = formation
            return True
        return False

    def set_stance(self, u, stance):
        if stance in STANCES:
            u.stance = stance

    def face(self, u, angle):
        """Turn to face `angle` (radians, 0 towards +y) where it stands, or once its march is done."""
        u.face_to = angle

    def begin(self):
        self.started = True
        self.log.append("The battle begins.")

    # --- the fighting -----------------------------------------------------------------------------

    def step(self, dt):
        """Advance the battle by dt seconds of battle time."""
        if not self.started or self.winner is not None:
            return
        self.time += dt
        for u in self.units:
            if u.state == "waiting" and self.time >= u.arrive:
                u.state = "formed"
                u.still = 0.0
                self.events.append(("arrive", u.id))
                if u.army and not any(o.army == u.army and o.state != "waiting" and o.id != u.id
                                      for o in self.units if o.side == u.side):
                    self.log.append(("Our" if u.side == 0 else "Their") + " allies come onto the field!")
        order = self.rng.permutation(len(self.units))   # nobody always moves first
        for i in order:
            u = self.units[i]
            if u.alive and u.state != "waiting":
                self._act(u, dt)
        if self.siege is not None:
            self._siege_step(dt)
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
        moving = u.order is not None and u.state == "formed"
        if u.state == "fighting":
            u.stamina = max(0.0, u.stamina - 0.35 * dt)
        elif not moving:
            u.stamina = min(100.0, u.stamina + 0.6 * dt)
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
        if u.state == "climbing":
            return self._climbing(u, dt)
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
            if u.face_to is not None:            # turn the front where we were told
                turn = _wrap(u.face_to - u.facing)
                u.facing += max(-1.0 * dt, min(1.0 * dt, turn))
                if abs(turn) < 0.02:
                    u.face_to = None
            return
        gx, gy = goal
        dist = math.hypot(gx - u.x, gy - u.y)
        if dist < 3:
            u.order = None if u.order and u.order[0] == "move" else u.order
            return
        want = math.atan2(gx - u.x, gy - u.y)
        turn = _wrap(want - u.facing)
        u.facing += max(-1.5 * dt, min(1.5 * dt, turn))
        running = u.run or (target is not None and dist < 160)
        if running and u.stamina > 15:
            u.stamina = max(0.0, u.stamina - (0.9 if u.kind == "horse" else 1.2) * RUN_COST * dt)
        step = min(dist, u.speed(running) * dt * self.field.going(u.x, u.y, u.kind))
        if abs(turn) < 0.6:
            x0, y0 = u.x, u.y
            u.x += math.sin(u.facing) * step
            u.y += math.cos(u.facing) * step
            if self.siege is not None:
                self._wall_check(u, x0, y0)
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

    def visible(self, u, side):
        """Can `side` see regiment u? Men standing still in a wood are hidden until an enemy comes close."""
        if u.side == side or u.state != "formed" or not self.field.wooded(u.x, u.y) or u.still < 8:
            return True
        return any(math.hypot(o.x - u.x, o.y - u.y) < 110 for o in self.units if o.side == side and o.standing)

    def _engage(self, a, b):
        if a.state == "formed" and a.still < 30 and self.field.wooded(a.x, a.y) and b.state == "formed" and \
                not self.field.wooded(b.x, b.y) and b.morale > BREAK and a.id not in b.shocked:
            b.shocked.add(a.id)                   # out of the trees, onto men who never saw them
            b.morale -= 15
            self.log.append(f"Ambush! {self.name(a)} fall on {self.name(b).lower()} from the woods.")
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
        s = u.melee * (1.0 + 0.5 * u.experience) * self.leadership[u.side] * u.tired
        s *= {"square": 0.9, "loose": 0.8}.get(u.formation, 1.0)
        if u.kind == "horse" and foe.kind != "horse":
            s *= HORSE_MELEE          # a rider strikes down from above
        front = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing)) < 1.0
        if u.charging > 0:
            bonus = (1.8 if u.melee >= 12 else 1.4) + (0.5 if u.formation == "wedge" else 0.0)
            if (front or foe.formation == "square") and foe.kind != "horse" and foe.still > 4:
                bonus = 1.0 + (bonus - 1.0) * 0.4      # foot standing firm, spears levelled, blunts the charge
            s *= bonus
        if u.still > 20 and u.kind != "horse":
            s *= 1.1                                   # men who waited in their ranks for the blow
        if u.kind == "horse" and self.field.wooded(u.x, u.y):
            s *= 0.6
        if self.field.h(u.x, u.y) > self.field.h(foe.x, foe.y) + 4:
            s *= 1.15     # fighting down a slope
        if self.field.near_river(u.x, u.y):
            s *= 0.75     # floundering in the stream
        if self.siege is not None:
            s = self._siege_strength(u, foe, s)
        # where the blow lands on the foe: front, flank or rear
        angle = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing))
        if foe.formation == "square":
            pass                                       # a square has no flank and no rear
        elif angle > 2.2:
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
            dmg = engaged * MELEE_RATE * _hit(self._strength(u, foe), foe.armour) * dt * self.rng.uniform(0.6, 1.4)
            if foe.state == "routing":
                dmg *= 2.5    # cut down as they run
            hits[foe.id] = hits.get(foe.id, 0.0) + dmg
            dealt[u.id] = dealt.get(u.id, 0.0) + dmg / max(1, foe.start_men)
            angle = abs(_wrap(_angle_to(foe, u.x, u.y) - foe.facing))
            if angle > 1.0 and u.id not in foe.shocked and foe.formation != "square":
                foe.shocked.add(u.id)
                foe.morale -= 12 if angle > 2.2 else 7
        for u, foe in pairs:
            # a regiment losing the fight loses heart faster than one winning it
            taken = hits.get(u.id, 0.0) / max(1, u.start_men)
            ratio = (taken + 1e-4) / (dealt.get(u.id, 0.0) + 1e-4)
            u.morale -= PRESSURE * dt * min(4.0, max(0.25, ratio)) * (0.7 if u.formation == "deep" else 1.0)
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
            u.reload = VOLLEY * (HORSE_VOLLEY if u.kind == "horse" else 1.0)   # riders loose on the move
            u.ammo -= 1
            dist = math.hypot(target.x - u.x, target.y - u.y)
            accuracy = 1.2 - 0.6 * dist / reach
            cover = 0.5 if self.field.wooded(target.x, target.y) else 1.0
            cover *= {"loose": 0.6, "deep": 1.15, "square": 1.15}.get(target.formation, 1.0)
            if self.on_wall(target):
                cover *= 0.5                        # behind the battlements
            skill = u.missile * (1 + 0.3 * u.experience)
            dmg = u.men * MISSILE_RATE * _hit(skill, target.armour, 0.25) * accuracy * cover * \
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
        u.morale -= 120.0 * dead / max(1, u.start_men) * (0.85 if u.formation == "deep" else 1.0)
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
        # a side is beaten when nothing of it stands on the field and no help is still on the road
        standing = [self.side_units(s) or [u for u in self.units if u.side == s and u.state == "waiting"]
                    for s in (0, 1)]
        if not standing[0] or not standing[1]:
            self.winner = 1 if not standing[0] else 0
        elif self.time >= TIME_LIMIT:
            self.winner = 1
            self.log.append("Night falls: the attackers withdraw.")
        if self.winner is not None:
            # the beaten who are still on the field are caught as they flee
            for u in self.units:
                if u.side != self.winner and u.alive and u.state != "waiting":
                    u.men = int(u.men * 0.8)
            # the beaten general: dead on the field, taken as he fled, or got away
            for u in self.units:
                if u.general and u.side != self.winner and u.army == 0:
                    roll = self.rng.random()
                    if u.men <= 0 or roll < 0.15:
                        self.general_fate[u.side] = "killed"
                    elif roll < 0.4:
                        self.general_fate[u.side] = "captured"
                elif u.general and u.side == self.winner and u.army == 0 and u.men <= 0:
                    self.general_fate[u.side] = "killed"
            self.log.append(("The attackers" if self.winner == 0 else "The defenders") + " carry the field.")

    # --- the AI ---------------------------------------------------------------------------------

    def ai(self, side):
        """The captains' plan. The line goes forward together; the archers shoot at what comes near and give
        ground before a charge; the horse keeps level on the wings and, once the lines are locked, falls on
        flanks and archers; horse archers ride off from what would catch them. The defender lets the attack
        come on, unless it is the one being out-shot."""
        if self.siege is not None:
            return self._siege_ai(side)
        mine = self.side_units(side)
        foes = [e for e in self.units if e.side != side and e.standing and self.visible(e, side)]
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
            melee_near = [e for e in foes if not e.ranged() and e.state != "fighting" and dist(u, e) < SHY]
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

    def captains(self, side):
        """What the player's regiments do of their own accord, by their stance: a free regiment closes with
        an enemy that comes near, a skirmishing one keeps its distance while it has arrows, one told to hold
        stands where it is."""
        foes = [e for e in self.units if e.side != side and e.standing]
        for u in self.side_units(side):
            if u.state == "fighting" or not foes:
                continue
            nearest = min(foes, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
            d = math.hypot(nearest.x - u.x, nearest.y - u.y)
            if u.stance == "skirmish" and u.ranged() and u.ammo > 0:
                if not nearest.ranged() and d < SHY * 1.4:
                    away = math.atan2(u.x - nearest.x, u.y - nearest.y)
                    back = 160.0 if u.kind == "horse" else 70.0
                    self.move(u, u.x + math.sin(away) * back, u.y + math.cos(away) * back)
            elif u.stance == "free" and u.order is None and d < 90 and not (u.ranged() and u.ammo > 0):
                self.attack(u, nearest)

    def form_up(self, side):
        """The captains keep the plain line: it is what their men know. (The player may choose otherwise.)"""

    def run(self, dt=1.0, ai_sides=(0, 1), limit=None):
        """Fight it out with the AI for the given sides (for auto-resolving and tests)."""
        if not self.started:
            self.begin()
        for side in ai_sides:
            if side not in self.formed_up:
                self.form_up(side)
                self.formed_up.add(side)
        while self.winner is None and (limit is None or self.time < limit):
            for side in ai_sides:
                if int(self.time) % 5 == 0:
                    self.ai(side)
            self.step(dt)
        return self.winner

    # --- the outcome --------------------------------------------------------------------------------

    def survivors(self, side, army=0):
        """{regiment index: men left} for an army (the dead and the fled who never came back)."""
        return {u.regiment: max(0, u.men) for u in self.units if u.side == side and u.army == army}


AID_KM = 30.0          # armies this near a battle march to it


def helpers(campaign, army, enemy, exclude):
    """Armies near enough to come to `army`'s aid against `enemy`: its own or its allies', with how many
    seconds of battle pass before each arrives."""
    friends = {army.owner, *campaign.allies_of(army.owner)}
    out = []
    for other in campaign.armies:
        if any(other is e for e in exclude) or other.owner not in friends or not other.regiments:
            continue
        if other.owner != army.owner and not campaign.hostile(other.owner, enemy.owner):
            continue
        km = math.hypot(other.x - army.x, other.y - army.y) * 1.5
        if km <= AID_KM:
            out.append((km, other))
    out.sort(key=lambda p: p[0])
    return [(other, 150.0 + 25.0 * km) for km, other in out[:2]]


def tactical(campaign, attacker, defender, seed=None):
    """A Battle between two armies of the campaign, on the ground where they meet, with any friends near
    enough to march to the sound of it."""
    from .rules import UNITS
    prov, terrain, place = campaign.battle_site(attacker, defender)
    seed = campaign.rng.randrange(1 << 30) if seed is None else seed
    river = terrain in ("plains", "steppe", "marsh") and (seed % 3 == 0)
    busy = [attacker, defender]
    allies = {0: helpers(campaign, attacker, defender, busy)}
    busy += [a for a, _ in allies[0]]
    allies[1] = helpers(campaign, defender, attacker, busy)
    return Battle(attacker, defender, UNITS, terrain, seed, river, campaign.leadership(attacker),
                  campaign.leadership(defender), place, allies=allies)


def conclude(campaign, battle, attacker, defender):
    """Carry a fought battle's outcome back into the campaign."""
    winner = attacker if battle.winner == 0 else defender
    after = {}
    for side, army in ((0, attacker), (1, defender)):
        left = battle.survivors(side)
        after[army.id] = [left.get(i, r.men) for i, r in enumerate(army.regiments)]
        # the allies who came: their losses, and a little of the victors' experience
        for k, ally in enumerate(battle.allies[side], start=1):
            left = battle.survivors(side, k)
            for i, r in enumerate(ally.regiments):
                r.men = max(0, min(r.men, int(left.get(i, r.men))))
                r.experience = min(1.0, r.experience + (0.1 if side == battle.winner else 0.03))
            ally.regiments = [r for r in ally.regiments if r.men >= 50]
            if not ally.regiments and ally in campaign.armies:
                campaign.armies.remove(ally)
    fates = {(attacker, defender)[side].id: fate for side, fate in battle.general_fate.items()}
    return campaign.conclude_battle(attacker, defender, winner, after, fates=fates)


def tactical_storm(campaign, army, pid, seed=None):
    """The assault on a besieged town, fought on the field: the army against the garrison behind its wall."""
    from .rules import UNITS
    p = campaign.provinces[pid]
    garrison = campaign.garrison_army(pid)
    seed = campaign.rng.randrange(1 << 30) if seed is None else seed
    terrain = campaign.static(pid).terrain
    siege = {"fort": campaign.fort(pid), "progress": p.siege["progress"] if p.siege else 0.0,
             "town": campaign.static(pid).name}
    return Battle(army, garrison, UNITS, terrain if terrain != "marsh" else "plains", seed, False,
                  campaign.leadership(army), 1.0 + 0.05 * campaign.fort(pid), campaign.static(pid).name,
                  siege=siege), garrison


def conclude_storm(campaign, battle, army, pid):
    """Carry a fought assault back into the campaign."""
    left = battle.survivors(0)
    lost = sum(r.men - max(0, min(r.men, left.get(i, r.men))) for i, r in enumerate(army.regiments))
    return campaign.conclude_storm(army, pid, battle.winner == 0, lost)
