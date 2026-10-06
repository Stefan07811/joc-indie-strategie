"""Auto-resolved battles.

Both sides fight in short rounds. Each round every regiment strikes a random enemy regiment;
damage grows with the striker's attack and shrinks with the target's defence, on how battered the striker already is, and on
modifiers (terrain, walls, generals, home ground, first-round charges and volleys).
A side breaks once it has lost more of its strength than its morale can bear.
The same code predicts outcomes for the AI and for the player's battle forecast.
"""

import dataclasses
import random
from dataclasses import dataclass, field

DAMAGE_PER_ATTACK = 5  # a blow lands for about attack × this, reduced by the target's defence
ARMOUR = 10  # defence D lets through ARMOUR / (ARMOUR + D) of a blow
MAX_ROUNDS = 12
PURSUIT_LOSS = 0.2  # share of remaining strength a broken side loses while fleeing
MIN_HP = 8  # regiments weaker than this are disbanded
GENERAL_BONUS = 1.1
HOME_TERRAIN_BONUS = 1.15
WALLS_DEFENSE = 1.5
WALLS_RESOLVE = 0.2  # garrisons behind walls hold out longer before breaking
FIRST_ROUND = {"ranged": 1.5, "charge": 1.5}
BANE_OF_CREATURES = 1.3


@dataclass
class Regiment:
    unit: str
    hp: float

    def copy(self):
        return Regiment(self.unit, self.hp)


@dataclass
class Side:
    """One side of a battle. `regiments` are the real objects and are damaged in place."""
    faction: str
    regiments: list[Regiment]
    leader: str | None = None  # general's name; None for a garrison
    defense_mult: float = 1.0
    attack_mult: float = 1.0
    resolve_bonus: float = 0.0
    creature: bool = False  # Monster Hunters strike creatures harder


@dataclass
class SideReport:
    faction: str
    leader: str | None
    start_regiments: int
    end_regiments: int
    start_hp: float
    end_hp: float

    @property
    def losses(self):
        return self.start_hp - self.end_hp


@dataclass
class BattleResult:
    province: str
    kind: str  # "field" or "assault"
    attacker: SideReport
    defender: SideReport
    winner: str  # "attacker" or "defender"
    rounds: int
    notes: list[str] = field(default_factory=list)

    @property
    def attacker_won(self):
        return self.winner == "attacker"

    @property
    def winning_faction(self):
        return self.attacker.faction if self.attacker_won else self.defender.faction

    @property
    def losing_faction(self):
        return self.defender.faction if self.attacker_won else self.attacker.faction


def strength(regiments, units):
    """A rough single number for how dangerous a group of regiments is."""
    total = 0.0
    for r in regiments:
        u = units[r.unit]
        total += r.hp * (u["attack"] + u["defense"]) / 10
    return total


def break_point(regiments, units, bonus=0.0):
    """Share of starting strength a side can lose before it breaks (0.3 .. 0.95)."""
    hp = sum(r.hp for r in regiments) or 1
    morale = sum(units[r.unit]["morale"] * r.hp for r in regiments) / hp
    return max(0.3, min(0.95, 0.25 + morale / 100 * 0.5 + bonus))


def resolve(attacker, defender, units, rng=None, province="", kind="field"):
    """Fight it out. Damages the sides' regiments in place and removes the dead ones."""
    rng = rng or random.Random()
    sides = (attacker, defender)
    start_hp = [sum(r.hp for r in s.regiments) for s in sides]
    start_n = [len(s.regiments) for s in sides]
    limits = [break_point(attacker.regiments, units), break_point(defender.regiments, units, defender.resolve_bonus)]
    broken = None
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        damage = [_strikes(sides[i], sides[1 - i], units, rng, rounds) for i in (0, 1)]
        for i in (0, 1):
            _apply(sides[1 - i], damage[i])
        lost = [1 - sum(r.hp for r in s.regiments) / start_hp[i] if start_hp[i] else 1 for i, s in enumerate(sides)]
        over = [lost[i] >= limits[i] or not sides[i].regiments for i in (0, 1)]
        if over[0] or over[1]:
            # if both crack in the same round, the one further past its limit breaks
            if not attacker.regiments or not defender.regiments:
                broken = 0 if not attacker.regiments else 1
            else:
                broken = 0 if over[0] and (not over[1] or lost[0] - limits[0] >= lost[1] - limits[1]) else 1
            break
    if broken is None:
        broken = 0  # the attack stalled: the defenders hold the field
    loser = sides[broken]
    for r in loser.regiments:
        r.hp *= 1 - PURSUIT_LOSS
    _bury(loser)

    reports = [
        SideReport(s.faction, s.leader, start_n[i], len(s.regiments), start_hp[i], sum(r.hp for r in s.regiments))
        for i, s in enumerate(sides)
    ]
    return BattleResult(province, kind, reports[0], reports[1], "defender" if broken == 0 else "attacker", rounds)


def predict(attacker, defender, units, kind="field"):
    """Expected outcome without touching the real regiments: (attacker wins?, attacker hp left share)."""
    a = dataclasses.replace(attacker, regiments=[r.copy() for r in attacker.regiments])
    d = dataclasses.replace(defender, regiments=[r.copy() for r in defender.regiments])
    start = sum(r.hp for r in a.regiments) or 1
    result = resolve(a, d, units, _Average(), kind=kind)
    return result.attacker_won, sum(r.hp for r in a.regiments) / start


class _Average:
    """Stand-in for random.Random that always rolls the average, for predictions."""

    def random(self):
        return 0.5

    def choice(self, seq):
        return max(seq, key=lambda r: r.hp)


def _strikes(side, enemy, units, rng, round_no):
    hits = {}
    if not enemy.regiments:
        return hits
    for r in side.regiments:
        u = units[r.unit]
        target = rng.choice(enemy.regiments)
        t = units[target.unit]
        attack = u["attack"] * side.attack_mult
        if round_no == 1:
            attack *= FIRST_ROUND.get(u["ability"], 1.0)
        if u["ability"] == "bane_of_creatures" and enemy.creature:
            attack *= BANE_OF_CREATURES
        defense = t["defense"] * enemy.defense_mult
        vigour = 0.5 + 0.5 * r.hp / u["hp"]
        roll = 0.8 + 0.4 * rng.random()
        dmg = DAMAGE_PER_ATTACK * attack * ARMOUR / (ARMOUR + defense) * vigour * roll
        hits[id(target)] = hits.get(id(target), 0) + dmg
    return hits


def _apply(side, hits):
    for r in side.regiments:
        r.hp -= hits.get(id(r), 0)
    _bury(side)


def _bury(side):
    side.regiments[:] = [r for r in side.regiments if r.hp >= MIN_HP]
