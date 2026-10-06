"""Real-time battles: the same armies and the same modifiers as the auto-resolve, fought on a field.

Pure logic, no pygame: the UI (ui/battle_screen.py) draws a Battlefield and gives orders to the
player's regiments; the computer commands the rest. step(dt) advances the fight; once it is over,
finish() writes the losses into the real regiments and returns an ordinary BattleResult.

How a fight works:
- Regiments march at their unit's speed (slower in forests and marshes) and stop when they reach
  an enemy. In contact they deal the auto-resolve's damage, spread over time
  (one auto-resolve round = SECONDS_PER_ROUND seconds).
- A blow from the side strikes harder (FLANK), one from behind harder still (REAR), and both shake
  the victim. Charge-type abilities strike harder in the first seconds of contact.
- Ranged regiments shoot at enemies within RANGE when not locked in melee (weaker against
  targets in a forest; walls do not stop Flying Fire).
- Hills help their holders defend; walls (assaults) protect the defenders standing behind them,
  and only their gates let the attackers through.
- Weather and night: rain wets bowstrings and powder, snow slows every step, fog and darkness
  shorten the archers' reach; the Revenants fight best at night.
- Every regiment has one order it can give once in a while (use_ability): a charge, a volley, a war
  cry, a dance... The computer uses them too.
- Before the fight the player may place their regiments inside their deployment zone (place).
- Armies standing next to the battle march in to help after REINFORCE_TIME seconds (Side.late).
- In an assault the gates are shut: a ram (after two seasons of siege) batters a gate open, ladders
  (after one) let the attackers climb the walls slowly, and flying wyrms fly over them.
- A regiment flees once its losses, its army's losses and recent flanking add up to more than its
  morale can bear. Fleeing regiments run for their own edge of the field; the side with no
  regiment left standing loses. If time runs out, the defenders hold.
"""

import math
from dataclasses import dataclass, field

from . import battle
from .battle import BattleResult, SideReport
from .generals import veteran_mult

FIELD_W, FIELD_H = 1280, 600
SECONDS_PER_ROUND = 3.0
TIME_LIMIT = 300.0
RADIUS = 18
CONTACT = 2 * RADIUS + 4
RANGE = 260
SPEED_SCALE = 9.0  # pixels per second per point of the unit's speed
FLANK, REAR = 1.3, 1.6
FLANK_PANIC, PANIC_TIME = 0.15, 3.0
CHARGE_TIME = 2.5
CHARGES = {"charge": 1.5, "frenzy": 1.5, "mace_throw": 1.3}
RANGED_SHARE = 0.8
FOREST_COVER = 0.7
HILL_DEFENSE = 1.2
SLOW = {"forest": 0.7, "marsh": 0.6, "river": 0.45}
RIVER_DEFENSE = 0.85  # caught wading: easier to hit
AURA = 160
HEAL_RATE = 0.004  # share of full strength per second per healer nearby (Midsummer Maidens)
ROUT_SPEED = 1.3
PURSUIT = 1.5  # blows on fleeing regiments
DEFENDER_HOLD = 15.0  # the computer's defenders wait this long unless the enemy comes close
WALL_X, GATE_HALF = 880, 45
GATES = (FIELD_H * 0.3, FIELD_H * 0.7)
GATE_HP, RAM_HP = 100.0, 60.0
RAM_SPEED, RAM_BLOWS, RAM_DAMAGE = 22.0, 6.0, 3.0  # px/s; damage to a gate / taken from each archer, per second
CLIMB = 0.25  # pace on ladders
REINFORCE_TIME = 30.0
DEPLOY_DEPTH = 380  # how far into the field each side may place its regiments

WEATHER = {
    "clear": {"name": "Clear skies"},
    "rain": {"name": "Rain", "ranged": 0.6, "gun": 0.35, "speed": 0.9},
    "snow": {"name": "Snow", "ranged": 0.8, "speed": 0.8},
    "fog": {"name": "Fog", "range": 0.6},
}
NIGHT_RANGE = 0.7
NIGHT_STRIGOI = 1.15  # the Revenants' blows at night
NIGHT_RESOLVE = 0.05  # the living hold a little less firmly in the dark

# The order each regiment can give: by the unit's ability (None: any other regiment).
# effects: attack / defense / speed / volley multipliers on the regiment itself for `time` seconds;
# rally (allies near), scare (enemies near) and heal (allies near) act around it.
ACTIVE = {
    "charge": {"name": "Charge!", "time": 6, "cooldown": 40, "attack": 1.3, "speed": 1.6},
    "frenzy": {"name": "Frenzy!", "time": 6, "cooldown": 40, "attack": 1.4, "speed": 1.4},
    "mace_throw": {"name": "Hurl the maces", "time": 5, "cooldown": 40, "attack": 1.5},
    "ranged": {"name": "Volley!", "time": 6, "cooldown": 40, "volley": 1.8},
    "flying_fire": {"name": "Dragon fire", "time": 6, "cooldown": 45, "attack": 1.7},
    "life_drain": {"name": "Blood feast", "time": 8, "cooldown": 45, "attack": 1.4},
    "hero": {"name": "War cry", "time": 20, "cooldown": 60, "rally": 0.15},
    "enchanting_dance": {"name": "Bewitching round", "time": 6, "cooldown": 45, "scare": True},
    "dread": {"name": "Dread wail", "time": 6, "cooldown": 45, "scare": True},
    "heal": {"name": "Midsummer blessing", "time": 0, "cooldown": 60, "heal": 0.12},
    None: {"name": "Brace!", "time": 10, "cooldown": 40, "defense": 1.35, "speed": 0.5},
}
ABILITY_REACH = 200


@dataclass
class Zone:
    kind: str  # "forest", "hill" or "marsh"
    x: float
    y: float
    r: float

    def contains(self, x, y):
        return (x - self.x) ** 2 + (y - self.y) ** 2 <= self.r ** 2


@dataclass
class Block:
    """Impassable ground: rocks, or a stretch of town wall."""
    kind: str  # "rocks", "wall" or "gate"
    x: float
    y: float
    w: float
    h: float
    hp: float = 0.0  # a gate's strength against the ram

    def contains(self, x, y, pad=0.0):
        return self.x - pad <= x <= self.x + self.w + pad and self.y - pad <= y <= self.y + self.h + pad


@dataclass
class Ram:
    """A battering ram, pushed by the attackers towards the nearest gate."""
    x: float
    y: float
    hp: float = RAM_HP
    gate: float | None = None  # the y of the gate it goes for

    @property
    def alive(self):
        return self.hp > 0


@dataclass
class Unit:
    id: int
    side: int  # 0 attacker, 1 defender
    regiment: object
    x: float
    y: float
    facing: float
    start_hp: float
    order: tuple | None = None  # ("move", x, y) or ("attack", unit id)
    state: str = "ready"  # "ready", "routing", "fled" or "dead"
    contact: dict = field(default_factory=dict)  # enemy id -> time contact began
    shaken_until: float = -1.0
    fighting: int | None = None  # whom it struck last
    shooting: int | None = None
    buffs: dict = field(default_factory=dict)  # effect -> (multiplier, until)
    ready_at: float = 0.0  # when its special order can be given again
    arrive_at: float = 0.0  # reinforcements: when they march onto the field

    @property
    def ready(self):
        return self.state == "ready"


class Battlefield:
    def __init__(self, attacker, defender, units, terrain, kind, rng, province="", player_side=None,
                 weather="clear", night=False):
        self.sides = (attacker, defender)
        self.data = units
        self.terrain = terrain
        self.kind = kind
        self.rng = rng
        self.province = province
        self.player_side = player_side  # 0, 1 or None (the computer commands both)
        self.weather = weather if weather in WEATHER else "clear"
        self.night = night
        self.time = 0.0
        self.withdrawn = None
        self.notes = []
        equipment = attacker.equipment or {}
        self.ladders = kind == "assault" and bool(equipment.get("ladders"))
        self.ram = Ram(150, FIELD_H / 2) if kind == "assault" and equipment.get("ram") else None
        self.zones, self.blocks = self._ground()
        self.units = []
        self._deploy()
        self.start_hp = [sum(r.hp for r in s.regiments) for s in self.sides]
        self.start_n = [len(s.regiments) for s in self.sides]
        self.result = None

    # --- setting up ------------------------------------------------------------------------

    def _ground(self):
        rng = self.rng
        zones, blocks = [], []

        def scatter(kind, count, rmin, rmax, x0=260, x1=FIELD_W - 260):
            for _ in range(count):
                zones.append(Zone(kind, rng.uniform(x0, x1), rng.uniform(60, FIELD_H - 60), rng.uniform(rmin, rmax)))

        if self.terrain == "forest":
            scatter("forest", 7, 50, 95, 120, FIELD_W - 120)
        elif self.terrain == "hills":
            scatter("hill", 2, 90, 130)
            zones.append(Zone("hill", FIELD_W - 230, FIELD_H / 2, 140))  # the defenders' ridge
        elif self.terrain == "marsh":
            scatter("marsh", 6, 45, 85)
        elif self.terrain == "mountains":
            for _ in range(4):
                w, h = rng.uniform(40, 90), rng.uniform(40, 120)
                blocks.append(Block("rocks", rng.uniform(380, FIELD_W - 420), rng.uniform(40, FIELD_H - 160), w, h))
            zones.append(Zone("hill", FIELD_W - 230, FIELD_H / 2, 150))
        else:
            scatter("forest", 2, 40, 70)
            scatter("hill", 1, 80, 110)
        if self.kind == "field" and getattr(self.sides[0], "river", None):
            # the attackers come over a river: a band of water across the field, waded at half pace
            water = [Zone("river", FIELD_W * 0.42 + math.sin(y / 90) * 40, y, 34) for y in range(-20, FIELD_H + 40, 26)]
            zones = water + [z for z in zones if all(math.hypot(z.x - w.x, z.y - w.y) > z.r + w.r for w in water)]
        if self.kind == "assault":
            gates = (FIELD_H * 0.3, FIELD_H * 0.7)
            edges = [0, gates[0] - GATE_HALF, gates[0] + GATE_HALF, gates[1] - GATE_HALF, gates[1] + GATE_HALF, FIELD_H]
            for top, bottom in zip(edges[::2], edges[1::2]):
                blocks.append(Block("wall", WALL_X - 10, top, 20, bottom - top))
            for g in gates:
                blocks.append(Block("gate", WALL_X - 10, g - GATE_HALF, 20, 2 * GATE_HALF, GATE_HP))
            zones = [z for z in zones if abs(z.x - WALL_X) > z.r + 20]
        return zones, blocks

    def _deploy(self):
        uid = 0
        for side, s in enumerate(self.sides):
            late = {id(r) for r in s.late}
            here = [r for r in s.regiments if id(r) not in late]
            front = [r for r in here if self.data[r.unit]["ability"] != "ranged"]
            back = [r for r in here if self.data[r.unit]["ability"] == "ranged"]
            sign = 1 if side == 0 else -1
            base = 150 if side == 0 else FIELD_W - 150
            for line, group in ((0, front), (1, back)):
                for col in range(0, len(group), 8):
                    chunk = group[col:col + 8]
                    x = base - sign * (line * 70 + (col // 8) * 60)
                    for i, r in enumerate(chunk):
                        y = FIELD_H / 2 + (i - (len(chunk) - 1) / 2) * 62
                        facing = 0.0 if side == 0 else math.pi
                        self.units.append(Unit(uid, side, r, x, y, facing, r.hp))
                        uid += 1
            coming = [r for r in s.regiments if id(r) in late]
            for i, r in enumerate(coming):  # they march in from their own edge, later
                x = -RADIUS if side == 0 else FIELD_W + RADIUS
                y = FIELD_H * (i + 1) / (len(coming) + 1)
                u = Unit(uid, side, r, x, y, 0.0 if side == 0 else math.pi, r.hp, state="waiting",
                         arrive_at=REINFORCE_TIME)
                self.units.append(u)
                uid += 1

    # --- before the battle -------------------------------------------------------------------

    def deploy_zone(self, side):
        """Where `side` may place its regiments before the fight."""
        if side == 1 and self.kind == "assault":
            return (WALL_X + 30, RADIUS, FIELD_W - RADIUS - WALL_X - 30, FIELD_H - 2 * RADIUS)
        if side == 0:
            return (RADIUS, RADIUS, DEPLOY_DEPTH, FIELD_H - 2 * RADIUS)
        return (FIELD_W - DEPLOY_DEPTH - RADIUS, RADIUS, DEPLOY_DEPTH, FIELD_H - 2 * RADIUS)

    def place(self, ids, x, y):
        """Before the fight: set a group down around (x, y), inside its side's deployment zone."""
        group = [self.units[i] for i in ids if self.units[i].ready]
        if not group:
            return
        zx, zy, zw, zh = self.deploy_zone(group[0].side)
        cx = sum(u.x for u in group) / len(group)
        cy = sum(u.y for u in group) / len(group)
        for u in group:
            nx = _clamp(x + u.x - cx, zx, zx + zw)
            ny = _clamp(y + u.y - cy, zy, zy + zh)
            if self._free(nx, ny):
                u.x, u.y = nx, ny
        self._separate()

    # --- weather -------------------------------------------------------------------------------

    @property
    def range(self):
        r = RANGE * WEATHER[self.weather].get("range", 1.0)
        return r * NIGHT_RANGE if self.night else r

    def _ranged_mult(self, u):
        w = WEATHER[self.weather]
        gun = self.data[u.regiment.unit]["icon"] in ("gun", "rifle")
        return w.get("gun", w.get("ranged", 1.0)) if gun else w.get("ranged", 1.0)

    # --- special orders ------------------------------------------------------------------------

    def ability(self, u):
        a = self.data[u.regiment.unit]["ability"]
        return ACTIVE.get(a, ACTIVE[None])

    def can_use(self, u):
        return u.ready and self.time >= u.ready_at

    def use_ability(self, ids):
        """Give the regiments' special order (those that are ready to)."""
        used = []
        for i in ids:
            u = self.units[i]
            if not self.can_use(u):
                continue
            a = self.ability(u)
            until = self.time + a["time"]
            for effect in ("attack", "defense", "speed", "volley"):
                if effect in a:
                    u.buffs[effect] = (a[effect], until)
            for o in self.units:
                if not o.ready or _dist(o, u) > ABILITY_REACH:
                    continue
                if o.side == u.side and "rally" in a:
                    o.buffs["rally"] = (a["rally"], until)
                    o.shaken_until = -1.0
                if o.side == u.side and "heal" in a:
                    full = self.data[o.regiment.unit]["hp"]
                    o.regiment.hp = min(full, o.regiment.hp + full * a["heal"])
                if o.side != u.side and a.get("scare"):
                    o.shaken_until = max(o.shaken_until, self.time + a["time"])
            u.ready_at = self.time + a["cooldown"]
            used.append(u.id)
        return used

    def _buff(self, u, effect, default=1.0):
        mult, until = u.buffs.get(effect, (default, -1.0))
        return mult if self.time < until else default

    # --- queries ---------------------------------------------------------------------------

    def unit(self, uid):
        return self.units[uid]

    def standing(self, side):
        return [u for u in self.units if u.side == side and u.ready]

    def coming(self, side):
        """Reinforcements of `side` still on the road."""
        return any(u.side == side and u.state == "waiting" for u in self.units)

    def gate(self, y):
        return next((b for b in self.blocks if b.kind == "gate" and b.y <= y <= b.y + b.h), None)

    def strength(self, side):
        return sum(u.regiment.hp for u in self.units if u.side == side and u.state in ("ready", "routing", "waiting"))

    @property
    def over(self):
        return self.result is not None

    def zone_at(self, x, y):
        for z in self.zones:
            if z.contains(x, y):
                return z.kind
        return None

    def behind_walls(self, u):
        return self.kind == "assault" and u.side == 1 and u.x > WALL_X

    # --- orders ----------------------------------------------------------------------------

    def order_move(self, ids, x, y):
        """Move a group, keeping its shape around the point clicked."""
        group = [self.units[i] for i in ids if self.units[i].ready]
        if not group:
            return
        cx = sum(u.x for u in group) / len(group)
        cy = sum(u.y for u in group) / len(group)
        for u in group:
            u.order = ("move", _clamp(x + (u.x - cx), RADIUS, FIELD_W - RADIUS),
                       _clamp(y + (u.y - cy), RADIUS, FIELD_H - RADIUS))

    def order_attack(self, ids, target_id):
        for i in ids:
            if self.units[i].ready:
                self.units[i].order = ("attack", target_id)

    def order_halt(self, ids):
        for i in ids:
            self.units[i].order = None

    def withdraw(self, side):
        """Sound the retreat: the side gives up the field."""
        self.withdrawn = side
        for u in self.units:
            if u.side == side and u.ready:
                u.state = "routing"

    # --- the fight -------------------------------------------------------------------------

    def step(self, dt):
        if self.over:
            return
        self.time += dt
        for u in self.units:
            if u.state == "waiting" and self.time >= u.arrive_at:
                u.state = "ready"  # the reinforcements arrive
                u.x = RADIUS * 2 if u.side == 0 else FIELD_W - RADIUS * 2
                self.notes.append(f"Reinforcements reach the field ({self.sides[u.side].faction}).")
        self._command()
        self._move(dt)
        self._siege(dt)
        self._fight(dt)
        self._morale()
        alive = [bool(self.standing(0)) or self.coming(0), bool(self.standing(1)) or self.coming(1)]
        if not alive[0] or not alive[1] or self.time >= TIME_LIMIT:
            self._end(winner=1 if not alive[0] or self.time >= TIME_LIMIT else 0)

    def _command(self):
        """The computer's orders, for every side it commands."""
        for side in (0, 1):
            if side == self.player_side:
                continue
            enemies = self.standing(1 - side)
            if not enemies:
                continue
            for u in self.standing(side):
                if (u.fighting is not None or u.shooting is not None) and self.can_use(u) \
                        and self.rng.random() < 0.02:
                    self.use_ability([u.id])
                target = min(enemies, key=lambda e: _dist(u, e))
                ranged = self.data[u.regiment.unit]["ability"] == "ranged"
                if side == 1 and self.kind == "assault":
                    inside = [e for e in enemies if e.x > WALL_X]
                    if ranged and _dist(u, target) <= self.range:
                        u.order = None
                    elif inside:
                        u.order = ("attack", min(inside, key=lambda e: _dist(u, e)).id)
                    else:
                        u.order = None  # stay behind the walls
                elif side == 1 and self.time < DEFENDER_HOLD and _dist(u, target) > self.range + 40:
                    u.order = None  # hold the line for now
                elif ranged and _dist(u, target) <= self.range * 0.9:
                    u.order = None  # stand and shoot
                else:
                    u.order = ("attack", target.id)

    def _move(self, dt):
        for u in self.units:
            if u.state == "routing":
                edge = -RADIUS * 3 if u.side == 0 else FIELD_W + RADIUS * 3
                self._step_towards(u, edge, u.y, dt, ROUT_SPEED)
                if (u.side == 0 and u.x <= 0) or (u.side == 1 and u.x >= FIELD_W):
                    u.state = "fled"
                continue
            if not u.ready or u.contact:
                continue  # locked in melee
            goal = None
            if u.order and u.order[0] == "move":
                goal = u.order[1:]
            elif u.order and u.order[0] == "attack":
                target = self.units[u.order[1]]
                if target.state in ("ready", "routing"):
                    ranged = self.data[u.regiment.unit]["ability"] == "ranged"
                    if ranged and _dist(u, target) <= self.range * 0.9:
                        goal = None
                    else:
                        goal = (target.x, target.y)
                else:
                    u.order = None
            if goal:
                gx, gy = self._route(u, goal)
                self._step_towards(u, gx, gy, dt, 1.0)
                if u.order and u.order[0] == "move" and math.hypot(u.x - goal[0], u.y - goal[1]) < 4:
                    u.order = None
        self._separate()

    def _climbs(self, u):
        """Can this regiment get over the walls without a gate? (wyrms fly; ladders, after a siege)"""
        return self.data[u.regiment.unit]["ability"] == "flying_fire" or (u.side == 0 and self.ladders)

    def _route(self, u, goal):
        """Where to head for now: straight at the goal, or first to the nearest gate in the walls."""
        if self.kind != "assault" or (u.x < WALL_X) == (goal[0] < WALL_X) or self._climbs(u):
            return goal
        gates = GATES
        gate = min(gates, key=lambda g: abs(g - u.y) + abs(g - goal[1]))
        if abs(u.y - gate) > GATE_HALF - RADIUS:
            side_x = WALL_X - 40 if u.x < WALL_X else WALL_X + 40
            return side_x, gate  # line up with the gate first
        return (WALL_X + 60 if u.x < WALL_X else WALL_X - 60), gate  # then through it

    def _step_towards(self, u, gx, gy, dt, mult):
        dx, dy = gx - u.x, gy - u.y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return
        speed = self.data[u.regiment.unit]["speed"] * SPEED_SCALE * mult * SLOW.get(self.zone_at(u.x, u.y), 1.0)
        speed *= WEATHER[self.weather].get("speed", 1.0) * self._buff(u, "speed")
        if self._on_wall(u.x, u.y) and self.data[u.regiment.unit]["ability"] != "flying_fire":
            speed *= CLIMB
        step = min(dist, speed * dt)
        nx, ny = u.x + dx / dist * step, u.y + dy / dist * step
        u.facing = math.atan2(dy, dx)
        if self._free(nx, ny, u):
            u.x, u.y = nx, ny
        elif self._free(nx, u.y, u):
            u.x = nx
        elif self._free(u.x, ny, u):
            u.y = ny
        else:
            # walk along the obstacle towards the nearest way round (a gate, or the end of the rocks)
            u.y = _clamp(u.y + math.copysign(step, self._way_round(u) - u.y), RADIUS, FIELD_H - RADIUS)

    def _free(self, x, y, u=None):
        climbs = u is not None and self._climbs(u)
        return all(not b.contains(x, y, RADIUS * 0.6) for b in self.blocks
                   if not (climbs and b.kind in ("wall", "gate")))

    def _on_wall(self, x, y):
        return any(b.kind in ("wall", "gate") and b.contains(x, y, RADIUS * 0.6) for b in self.blocks)

    def _siege(self, dt):
        """The ram rolls to a gate and batters it; archers on the walls try to burn it."""
        ram = self.ram
        if ram is None or not ram.alive:
            return
        shut = [g for g in GATES if self.gate(g)]
        if not shut:
            return
        if ram.gate not in shut:
            ram.gate = min(shut, key=lambda g: abs(g - ram.y))
        tx, ty = WALL_X - 34, ram.gate
        d = math.hypot(tx - ram.x, ty - ram.y)
        if d > 2:
            step = min(d, RAM_SPEED * dt)
            ram.x += (tx - ram.x) / d * step
            ram.y += (ty - ram.y) / d * step
        else:
            gate = self.gate(ram.gate)
            gate.hp -= RAM_BLOWS * dt
            if gate.hp <= 0:
                self.blocks.remove(gate)
                self.notes.append("The ram breaks a gate open!")
        archers = sum(1 for u in self.standing(1) if self.data[u.regiment.unit]["ability"] == "ranged"
                      and math.hypot(u.x - ram.x, u.y - ram.y) <= self.range)
        ram.hp -= RAM_DAMAGE * archers * dt
        if not ram.alive:
            self.notes.append("The defenders burn the ram.")

    def _way_round(self, u):
        blocking = [b for b in self.blocks if b.contains(u.x + math.cos(u.facing) * RADIUS * 1.5, u.y, RADIUS)]
        if not blocking:
            return u.y
        b = blocking[0]
        options = [b.y - RADIUS * 1.5, b.y + b.h + RADIUS * 1.5]
        return min(options, key=lambda y: abs(y - u.y))

    def _separate(self):
        active = [u for u in self.units if u.state in ("ready", "routing")]
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                d = _dist(a, b)
                limit = 2 * RADIUS if a.side == b.side else CONTACT - 2
                if 1e-6 < d < limit:
                    push = (limit - d) / 2
                    ux, uy = (a.x - b.x) / d, (a.y - b.y) / d
                    for u, s in ((a, push), (b, -push)):
                        nx, ny = u.x + ux * s, u.y + uy * s
                        if self._free(nx, ny, u):
                            u.x = _clamp(nx, RADIUS, FIELD_W - RADIUS)
                            u.y = _clamp(ny, RADIUS, FIELD_H - RADIUS)

    def _fight(self, dt):
        units = self.data
        damage, heal = {}, {}
        for u in self.units:
            u.fighting = u.shooting = None
            if not u.ready:
                u.contact.clear()
                continue
            enemies = [e for e in self.units if e.side != u.side and e.state in ("ready", "routing")]
            touching = {e.id for e in enemies if _dist(u, e) <= CONTACT}
            for eid in list(u.contact):
                if eid not in touching:
                    del u.contact[eid]
            for eid in touching:
                u.contact.setdefault(eid, self.time)
            target = None
            if u.contact:
                ordered = u.order[1] if u.order and u.order[0] == "attack" else None
                target = self.units[ordered] if ordered in u.contact else \
                    min((self.units[e] for e in u.contact), key=lambda e: _dist(u, e))
                u.fighting = target.id
                u.facing = math.atan2(target.y - u.y, target.x - u.x)
                share = 1.0
            elif units[u.regiment.unit]["ability"] == "ranged":
                in_range = [e for e in enemies if e.ready and _dist(u, e) <= self.range]
                if in_range:
                    ordered = u.order[1] if u.order and u.order[0] == "attack" else None
                    target = self.units[ordered] if ordered in {e.id for e in in_range} else \
                        min(in_range, key=lambda e: _dist(u, e))
                    u.shooting = target.id
                    share = RANGED_SHARE * (FOREST_COVER if self.zone_at(target.x, target.y) == "forest" else 1.0)
                    share *= self._ranged_mult(u) * self._buff(u, "volley") * self.sides[1 - u.side].storm
            if target is None:
                continue
            dmg = self._blow(u, target, dt) * share
            damage[target.id] = damage.get(target.id, 0.0) + dmg
            if units[u.regiment.unit]["ability"] == "life_drain":
                heal[u.id] = heal.get(u.id, 0.0) + dmg * battle.LIFE_DRAIN
        for uid, d in damage.items():
            self.units[uid].regiment.hp -= d
        for uid, h in heal.items():
            r = self.units[uid].regiment
            r.hp = min(units[r.unit]["hp"], r.hp + h)
        self._healers(dt)
        for u in self.units:
            if u.state in ("ready", "routing") and u.regiment.hp < battle.MIN_HP:
                u.state = "dead"
                u.regiment.hp = 0

    def _blow(self, u, target, dt):
        units = self.data
        me, them = self.sides[u.side], self.sides[target.side]
        unit, foe = units[u.regiment.unit], units[target.regiment.unit]
        attack = unit["attack"] * me.attack_mult * self._attack_aura(u) * veteran_mult(u.regiment)
        attack *= self._buff(u, "attack")
        if self.night and me.faction == "strigoi":
            attack *= NIGHT_STRIGOI
        if them.creature:
            attack *= me.creature_bane
        if u.fighting is not None and unit["ability"] in CHARGES and \
                self.time - u.contact.get(target.id, self.time) < CHARGE_TIME:
            attack *= CHARGES[unit["ability"]]
        if unit["ability"] == "forest_ambush" and u.side == 1 and self.terrain == "forest" and self.time < 10:
            attack *= battle.FOREST_AMBUSH
        if unit["ability"] == "bane_of_creatures" and them.creature:
            attack *= battle.BANE_OF_CREATURES
        if target.state == "routing":
            attack *= PURSUIT
        angle = abs(_angle_diff(math.atan2(u.y - target.y, u.x - target.x), target.facing))
        if u.fighting is not None and angle > math.radians(120):
            attack *= REAR
            target.shaken_until = self.time + PANIC_TIME
        elif u.fighting is not None and angle > math.radians(60):
            attack *= FLANK
            target.shaken_until = self.time + PANIC_TIME
        defense_mult = them.defense_mult
        if them.walls and not (self.behind_walls(target) and unit["ability"] != "flying_fire"):
            defense_mult /= battle.WALLS_DEFENSE
        ground = self.zone_at(target.x, target.y)
        if ground == "hill":
            defense_mult *= HILL_DEFENSE
        elif ground == "river":
            defense_mult *= RIVER_DEFENSE
        defense = foe["defense"] * defense_mult * veteran_mult(target.regiment) * self._buff(target, "defense")
        vigour = 0.5 + 0.5 * u.regiment.hp / unit["hp"]
        roll = 0.8 + 0.4 * self.rng.random()
        per_round = battle.DAMAGE_PER_ATTACK * attack * battle.ARMOUR / (battle.ARMOUR + defense) * vigour * roll
        return per_round * dt / SECONDS_PER_ROUND

    def _nearby(self, u, side, ability):
        return sum(1 for o in self.units if o.side == side and o.ready and
                   self.data[o.regiment.unit]["ability"] == ability and _dist(u, o) <= AURA)

    def _attack_aura(self, u):
        dancers = min(battle.MAX_DANCE, self._nearby(u, 1 - u.side, "enchanting_dance"))
        hero = any(o.side == u.side and o.ready and self.data[o.regiment.unit]["ability"] == "hero"
                   for o in self.units)
        return (1 - battle.DANCE * dancers) * (battle.HERO_ATTACK if hero else 1.0)

    def _healers(self, dt):
        for u in self.units:
            if not u.ready:
                continue
            healers = min(2, self._nearby(u, u.side, "heal"))
            if healers:
                full = self.data[u.regiment.unit]["hp"]
                u.regiment.hp = min(full, u.regiment.hp + full * HEAL_RATE * healers * dt)

    def _morale(self):
        lost_side = [1 - self.strength(s) / self.start_hp[s] if self.start_hp[s] else 1 for s in (0, 1)]
        for u in self.units:
            if not u.ready:
                continue
            side = self.sides[u.side]
            hero = any(o.side == u.side and o.ready and self.data[o.regiment.unit]["ability"] == "hero"
                       for o in self.units)
            dread = min(battle.MAX_DREAD, self._nearby(u, 1 - u.side, "dread"))
            bonus = side.resolve_bonus + (battle.HERO_RESOLVE if hero else 0.0) - battle.DREAD * dread
            bonus += self._buff(u, "rally", 0.0)
            if self.night and side.faction != "strigoi":
                bonus -= NIGHT_RESOLVE
            limit = battle.break_point([u.regiment], self.data, bonus)
            own_lost = 1 - u.regiment.hp / u.start_hp if u.start_hp else 1
            panic = FLANK_PANIC if self.time < u.shaken_until else 0.0
            if own_lost + 0.5 * lost_side[u.side] + panic >= limit:
                u.state = "routing"
                u.order = None

    def _end(self, winner):
        loser = 1 - winner
        for u in self.units:
            if u.side == loser and u.state in ("ready", "routing"):
                u.regiment.hp *= 1 - battle.PURSUIT_LOSS / 2  # the rest of the pursuit
        for s in self.sides:
            s.regiments[:] = [r for r in s.regiments if r.hp >= battle.MIN_HP]
        reports = [SideReport(s.faction, s.leader, self.start_n[i], len(s.regiments), self.start_hp[i],
                              sum(r.hp for r in s.regiments)) for i, s in enumerate(self.sides)]
        self.result = BattleResult(self.province, self.kind, reports[0], reports[1],
                                   "attacker" if winner == 0 else "defender",
                                   max(1, round(self.time / SECONDS_PER_ROUND)), notes=list(dict.fromkeys(self.notes)))

    def finish(self, step=1 / 30, max_steps=None):
        """Let the computer fight it out to the end (both sides), and return the result."""
        self.player_side = None
        steps = 0
        while not self.over:
            self.step(step)
            steps += 1
            if max_steps and steps >= max_steps:
                break
        return self.result


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _angle_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi
