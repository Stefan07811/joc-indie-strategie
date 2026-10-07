"""Storming a town: the wall across the field with its gate and towers, the ladders, the ram at the gate,
the breaches that the months of siege have opened, and the town's square that the attackers must take
and hold. Mixed into Battle."""

import math
from dataclasses import dataclass, field

import numpy as np

CLIMB = 25.0            # seconds for a regiment to get up its ladders
SCALED = 25.0           # seconds a regiment fights badly after coming over the wall
GATE_HALF = 22.0        # half the width of the gateway (metres)
BREACH_HALF = 28.0
TOWER_RANGE = 170.0
TOWER_VOLLEY = 5.0
PLAZA_HOLD = 60.0       # seconds the attackers must hold the square alone to take the town
WALL_BAND = 22.0        # men this near the wall's line stand on it


@dataclass
class Walls:
    y: float                       # the wall's line across the field
    gate_x: float
    gate_hp: float
    fort: int
    breaches: list = field(default_factory=list)
    towers: list = field(default_factory=list)
    plaza: tuple = (0.0, 0.0)
    town: str = "the town"
    held: float = 0.0              # seconds the attackers have held the square
    reload: dict = field(default_factory=dict)

    @property
    def gate_open(self):
        return self.gate_hp <= 0

    def passable(self, x, side):
        """Can a regiment of `side` cross the wall line at x without ladders?"""
        at_gate = abs(x - self.gate_x) < GATE_HALF
        if at_gate and (self.gate_open or side == 1):
            return True
        return any(abs(x - b) < BREACH_HALF for b in self.breaches)


def make_walls(siege, field_w, field_h, rng):
    """siege: {"fort": walls level 0-4, "progress": 0-1 of the siege so far, "town": name}."""
    fort = int(siege.get("fort", 1))
    progress = float(siege.get("progress", 0.0))
    walls = Walls(y=field_h - 480.0, gate_x=field_w / 2, gate_hp=250.0 * (1 + fort) * (1 - 0.6 * progress),
                  fort=fort, plaza=(field_w / 2, field_h - 220.0), town=siege.get("town", "the town"))
    for k in range(int(progress / 0.45)):       # the siege engines' work: breaches in the curtain
        walls.breaches.append(float(rng.uniform(300, field_w - 300)))
    n = 2 + 2 * fort
    walls.towers = [float(x) for x in np.linspace(180, field_w - 180, n)]
    return walls


class SiegeRules:
    """Battle methods for a storm. self.siege is a Walls, or None in a battle in the open."""

    def _siege_deploy(self, side, army, unit_types):
        """The garrison: archers on the wall, foot behind the gate, horse by the square."""
        from .battle import Unit
        w = self.siege
        regs = list(enumerate(army.regiments))
        missile = [(i, r) for i, r in regs if unit_types[r.unit].kind == "missile"]
        foot = [(i, r) for i, r in regs if unit_types[r.unit].kind == "foot"]
        horse = [(i, r) for i, r in regs if unit_types[r.unit].kind == "horse"]
        places = []
        for k, item in enumerate(missile):
            x = w.gate_x + (k - (len(missile) - 1) / 2) * 170
            places.append((item, x, w.y + 10))
        for k, item in enumerate(foot):
            x = w.gate_x + (k - (len(foot) - 1) / 2) * 130
            places.append((item, x, w.y + 110))
        for k, item in enumerate(horse):
            places.append((item, w.plaza[0] + (k - (len(horse) - 1) / 2) * 120, w.plaza[1]))
        first = True
        for (i, r), x, y in places:
            t = unit_types[r.unit]
            u = Unit(len(self.units), side, r.unit, r.men, r.men, float(x), float(y), math.pi, t.melee, t.missile,
                     t.defence, t.morale, t.kind, r.experience, regiment=i)
            u.morale = 45 + 3.5 * t.morale + 15 * r.experience + 10      # men fighting for their homes
            u.stance = "hold"
            u.general, first = first, False
            self.units.append(u)

    # --- moving against the wall ---------------------------------------------------------------------

    def _climbing(self, u, dt):
        """A regiment on its ladders: when it is up, it is over the wall, shaken and in some disorder."""
        u.climb -= dt
        if u.climb <= 0:
            u.state = "formed"
            u.y = self.siege.y + 14
            u.scaled = SCALED
            self.log.append(f"{self.name(u)} are over the wall!")

    def _wall_check(self, u, x0, y0):
        """Stop a regiment at the wall unless it can pass; foot set up ladders."""
        w = self.siege
        if (y0 - w.y) * (u.y - w.y) > 0 or w.passable(u.x, u.side):
            return
        if u.side == 0 and u.kind != "horse" and u.state == "formed":
            u.x, u.y = u.x, w.y - 8
            u.state = "climbing"
            u.climb = CLIMB * (1 + 0.15 * w.fort)
            self.events.append(("ladders", u.id))
        else:
            u.x, u.y = x0, y0

    def _siege_step(self, dt):
        w = self.siege
        # the ram: foot pressed against the shut gate batter it down
        if not w.gate_open:
            for u in self.units:
                if u.side == 0 and u.standing and u.kind == "foot" and abs(u.x - w.gate_x) < 45 and \
                        w.y - 40 < u.y < w.y:
                    w.gate_hp -= min(u.men, 400) * 0.02 * dt
            if w.gate_open:
                self.log.append("The gate gives way!")
                self.events.append(("gate",))
        # the towers shoot at whatever comes near the wall
        attackers = [u for u in self.units if u.side == 0 and u.standing]
        for k, tx in enumerate(w.towers):
            w.reload[k] = w.reload.get(k, TOWER_VOLLEY * (k % 3) / 3) - dt
            if w.reload[k] > 0 or not attackers:
                continue
            target = min(attackers, key=lambda e: math.hypot(e.x - tx, e.y - w.y))
            d = math.hypot(target.x - tx, target.y - w.y)
            if d > TOWER_RANGE:
                continue
            w.reload[k] = TOWER_VOLLEY
            from .battle import _hit
            dmg = (12 + 8 * w.fort) * _hit(8, target.armour, 0.3) * (1.2 - 0.6 * d / TOWER_RANGE) * \
                self.rng.uniform(0.5, 1.5)
            self._lose(target, dmg)
            target.morale -= dmg / max(1, target.men) * 25
            self.events.append(("tower", tx, w.y, target.id))
        for u in self.units:
            if getattr(u, "scaled", 0) > 0:
                u.scaled = max(0.0, u.scaled - dt)
        # the square: held by the attackers alone, the town is theirs
        px, py = w.plaza
        ours = any(u.side == 0 and u.standing and math.hypot(u.x - px, u.y - py) < 90 for u in self.units)
        theirs = any(u.side == 1 and u.standing and math.hypot(u.x - px, u.y - py) < 130 for u in self.units)
        if ours and not theirs:
            w.held += dt
            if w.held >= PLAZA_HOLD and self.winner is None:
                self.log.append(f"The square of {w.town} is taken: the town is ours!")
                self.winner = 0
        else:
            w.held = max(0.0, w.held - dt * 0.5)

    def _siege_strength(self, u, foe, s):
        w = self.siege
        if u.state == "climbing" or getattr(u, "scaled", 0) > 0:
            s *= 0.6                               # off the ladders, in no order yet
        on_wall = abs(u.y - w.y) < WALL_BAND
        if u.side == 1 and on_wall and foe.side == 0 and foe.y < w.y + 4:
            s *= 1.35                              # striking down from the wall-walk
        return s

    def on_wall(self, u):
        return self.siege is not None and u.side == 1 and abs(u.y - self.siege.y) < WALL_BAND

    # --- the captains in a storm ------------------------------------------------------------------------

    def _siege_ai(self, side):
        w = self.siege
        mine = self.side_units(side)
        foes = [e for e in self.units if e.side != side and e.standing]
        if not mine or not foes:
            return
        if side == 1:     # the garrison holds the wall; it falls on whoever gets inside
            inside = [e for e in foes if e.y > w.y + 6]
            for u in mine:
                if u.state == "fighting" or u.ranged():
                    continue
                if inside:
                    near = min(inside, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
                    if math.hypot(near.x - u.x, near.y - u.y) < 400 or u.kind == "horse":
                        self.attack(u, near)
            return
        ways = ([w.gate_x] if w.gate_open else []) + list(w.breaches)
        rams = 0
        for u in sorted(mine, key=lambda u: abs(u.x - w.gate_x)):
            if u.state in ("fighting", "climbing"):
                continue
            inside = u.y > w.y + 6
            if inside:
                defenders = [e for e in foes if math.hypot(e.x - u.x, e.y - u.y) < 200]
                if defenders:
                    self.attack(u, min(defenders, key=lambda e: math.hypot(e.x - u.x, e.y - u.y)))
                else:
                    self.move(u, *w.plaza)
                continue
            if u.ranged() and u.ammo > 0:                  # archers shoot at the wall's defenders
                on = [e for e in foes if self.on_wall(e)] or foes
                self.attack(u, min(on, key=lambda e: math.hypot(e.x - u.x, e.y - u.y)))
                continue
            if ways:                                       # through the gate or a breach, to the square
                way = min(ways, key=lambda x: abs(x - u.x))
                if abs(u.y - w.y) > 40 or abs(u.x - way) > BREACH_HALF:
                    self.move(u, way, w.y - 20 if u.y < w.y - 25 else w.y + 40)
                else:
                    self.move(u, way, w.y + 60)
                continue
            if u.kind == "horse":                          # horse waits for a way in
                self.move(u, u.x, min(u.y, w.y - 260))
                continue
            if rams < 2 and not w.gate_open:               # the first two bodies of foot take the ram
                rams += 1
                self.move(u, w.gate_x + (rams - 1.5) * 30, w.y - 12)
                continue
            # the rest put up their ladders where the wall is held thinnest
            spot = u.x if abs(u.x - w.gate_x) > 60 else u.x + 200
            self.move(u, float(np.clip(spot, 100, 2300)), w.y + 30)
