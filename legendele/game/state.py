"""Campaign state: provinces, armies, movement, war and the turn cycle. No pygame here."""

import heapq
import random
from dataclasses import dataclass, field

from . import battle
from .battle import BattleResult, Regiment, Side

SEASONS = ("Spring", "Summer", "Autumn", "Winter")
HEAL_RATE = 0.1  # share of full strength regiments recover each season on friendly ground
SIEGE_ATTRITION = 0.15  # share of full strength a besieged garrison loses each season
REBELS = "haiduci"


class MoveError(ValueError):
    pass


@dataclass
class Province:
    id: str
    name: str
    terrain: str
    x: int
    y: int
    owner: str | None
    neighbors: list[str]
    special: str | None = None
    walls: bool = False
    garrison: list[Regiment] = field(default_factory=list)
    besieged_by: int | None = None  # id of the army besieging this province's garrison


@dataclass
class Army:
    id: int
    faction: str
    province: str
    general: str
    regiments: list[Regiment]
    moves_left: int


@dataclass
class Reach:
    cost: int
    path: list[str]  # provinces entered, in order, ending with the destination


# --- events: what happened, for the chronicle and the battle reports ---------------------

@dataclass
class Battle:
    result: BattleResult


@dataclass
class Captured:
    province: str
    faction: str
    previous: str | None


@dataclass
class SiegeStarted:
    province: str
    faction: str


@dataclass
class Retreated:
    faction: str
    general: str
    province: str | None  # None: the army had nowhere to go and was destroyed


@dataclass
class Eliminated:
    faction: str


@dataclass
class Victory:
    faction: str
    kind: str  # "conquest", "legend" or "last_standing"


@dataclass
class Game:
    data: object
    player: str
    provinces: dict[str, Province] = field(default_factory=dict)
    armies: dict[int, Army] = field(default_factory=dict)
    round: int = 0
    log: list[str] = field(default_factory=list)
    events: list = field(default_factory=list)
    ai: dict = field(default_factory=dict)
    rng: random.Random = field(default_factory=random.Random)
    eliminated: list[str] = field(default_factory=list)
    heart_turns: dict[str, int] = field(default_factory=dict)
    winner: Victory | None = None
    _next_army_id: int = 1

    @classmethod
    def new(cls, data, player, ai_factory=None, seed=None):
        if not data.factions[player]["playable"]:
            raise ValueError(f"{player} is not a playable faction")
        game = cls(data=data, player=player, rng=random.Random(seed))
        for p in data.provinces:
            game.provinces[p["id"]] = Province(
                id=p["id"], name=p["name"], terrain=p["terrain"], x=p["x"], y=p["y"],
                owner=p["owner"], neighbors=list(p.get("neighbors", ())), special=p.get("special"),
                walls=p.get("walls", False), garrison=game._regiments(p.get("garrison", ())),
            )
        for a in data.map["start_armies"]:
            game.add_army(a["faction"], a["province"], a["general"], a["regiments"])
        if ai_factory is None:
            from .ai import SimpleAI as ai_factory
        for fid in game.turn_order:
            game.heart_turns[fid] = 0
            if fid != player:
                game.ai[fid] = ai_factory(fid)
        game.log.append(f"{game.date}: {game.faction_name(player, True)} begin their campaign.")
        return game

    # --- queries ---------------------------------------------------------------------------

    @property
    def turn_order(self):
        """Playable factions still in the game, the player first."""
        others = [f for f, d in self.data.factions.items() if d["playable"] and f != self.player]
        return [f for f in (self.player, *others) if f not in self.eliminated]

    @property
    def over(self):
        return self.winner is not None or self.player in self.eliminated

    @property
    def season(self):
        return SEASONS[self.round % 4]

    @property
    def year(self):
        return self.data.map["start_year"] + self.round // 4

    @property
    def date(self):
        return f"{self.season} {self.year}"

    @property
    def victory_rules(self):
        return self.data.map["victory"]

    def faction_name(self, fid, mid_sentence=False):
        name = self.data.factions[fid]["name"] if fid else "No one"
        if mid_sentence and name.startswith("The "):
            name = "the " + name[4:]
        return name

    def capital_of(self, fid):
        return self.data.factions[fid]["capital"]

    def armies_in(self, pid):
        return [a for a in self.armies.values() if a.province == pid]

    def armies_of(self, fid):
        return [a for a in self.armies.values() if a.faction == fid]

    def provinces_of(self, fid):
        return [p for p in self.provinces.values() if p.owner == fid]

    def heart_holder(self):
        return next((p.owner for p in self.provinces.values() if p.special == "heart"), None)

    def enter_cost(self, fid, pid):
        """Movement points faction `fid` spends to enter province `pid`."""
        terrain = self.provinces[pid].terrain
        if terrain in self.data.factions[fid]["terrain_mastery"]:
            return 1
        return self.data.terrain[terrain]["move_cost"]

    def has_enemy_army(self, fid, pid):
        return any(a.faction != fid for a in self.armies_in(pid))

    def defended(self, fid, pid):
        """Would an army of `fid` entering `pid` have to fight or besiege?"""
        p = self.provinces[pid]
        return self.has_enemy_army(fid, pid) or (p.owner != fid and bool(p.garrison))

    def passable(self, fid, pid):
        """Armies may march on through their own provinces as long as no enemy stands there.
        Entering any other province ends the march (to capture, fight or besiege)."""
        return self.provinces[pid].owner == fid and not self.has_enemy_army(fid, pid)

    def reachable(self, army):
        """Every province `army` can reach this turn, as {province id: Reach}."""
        best = {army.province: Reach(0, [])}
        queue = [(0, army.province)]
        while queue:
            cost, pid = heapq.heappop(queue)
            if cost > best[pid].cost:
                continue
            if pid != army.province and not self.passable(army.faction, pid):
                continue  # a destination only, the march stops here
            for nid in self.provinces[pid].neighbors:
                ncost = cost + self.enter_cost(army.faction, nid)
                if ncost > army.moves_left:
                    continue
                if nid not in best or ncost < best[nid].cost:
                    best[nid] = Reach(ncost, best[pid].path + [nid])
                    heapq.heappush(queue, (ncost, nid))
        del best[army.province]
        return best

    def distances(self, fid, start):
        """Movement cost from `start` to every province for faction `fid`, ignoring armies."""
        dist = {start: 0}
        queue = [(0, start)]
        while queue:
            cost, pid = heapq.heappop(queue)
            if cost > dist[pid]:
                continue
            for nid in self.provinces[pid].neighbors:
                ncost = cost + self.enter_cost(fid, nid)
                if ncost < dist.get(nid, float("inf")):
                    dist[nid] = ncost
                    heapq.heappush(queue, (ncost, nid))
        return dist

    def strength(self, regiments):
        return battle.strength(regiments, self.data.units)

    def besieging(self, army):
        p = self.provinces[army.province]
        return p.besieged_by == army.id

    # --- battle setup ----------------------------------------------------------------------

    def _side(self, fid, regiments, leader, pid, defending, walls=False):
        p = self.provinces[pid]
        home = p.terrain in self.data.factions[fid]["terrain_mastery"]
        mult = battle.HOME_TERRAIN_BONUS if home else 1.0
        defense = mult * (self.data.terrain[p.terrain]["defense"] if defending else 1.0)
        if walls:
            defense *= battle.WALLS_DEFENSE
        return Side(
            faction=fid, regiments=regiments, leader=leader, defense_mult=defense,
            attack_mult=mult * (battle.GENERAL_BONUS if leader else 1.0),
            resolve_bonus=battle.WALLS_RESOLVE if walls else 0.0,
            creature=self.data.factions[fid]["creature"],
        )

    def _attackers(self, armies, pid):
        regiments = [r for a in armies for r in a.regiments]
        return self._side(armies[0].faction, regiments, armies[0].general, pid, defending=False)

    def _field_defenders(self, fid, pid):
        enemies = [a for a in self.armies_in(pid) if a.faction != fid]
        if not enemies:
            return None, []
        regiments = [r for a in enemies for r in a.regiments]
        return self._side(enemies[0].faction, regiments, enemies[0].general, pid, defending=True), enemies

    def _garrison_side(self, pid):
        p = self.provinces[pid]
        return self._side(p.owner or REBELS, p.garrison, None, pid, defending=True, walls=p.walls)

    def forecast(self, army, pid):
        """Predicted result of `army` marching into / assaulting `pid`: (wins?, share of army left),
        or None if no fight would happen."""
        attackers = self._attackers([army], pid)
        if pid != army.province:
            defenders, _ = self._field_defenders(army.faction, pid)
            if defenders:
                return battle.predict(attackers, defenders, self.data.units)
            if self.provinces[pid].owner == army.faction:
                return None
        p = self.provinces[pid]
        if p.owner == army.faction or not p.garrison:
            return None
        return battle.predict(attackers, self._garrison_side(pid), self.data.units, kind="assault")

    # --- actions ---------------------------------------------------------------------------

    def add_army(self, fid, pid, general, regiments):
        army = Army(self._next_army_id, fid, pid, general, self._regiments(regiments), self.data.map["army_moves"])
        self.armies[army.id] = army
        self._next_army_id += 1
        return army

    def _regiments(self, unit_ids):
        return [Regiment(uid, self.data.units[uid]["hp"]) for uid in unit_ids]

    def move_army(self, army_id, target):
        """March to `target`. Returns the events that happened (battles, captures, sieges)."""
        if self.over:
            raise MoveError("the war is over")
        army = self.armies[army_id]
        reach = self.reachable(army).get(target)
        if reach is None:
            raise MoveError(f"{army.general} cannot reach {target} this turn")
        start = len(self.events)
        origin = ([army.province] + reach.path)[-2]
        self._leave(army)
        army.moves_left -= reach.cost
        army.province = target
        if not self.passable(army.faction, target):
            army.moves_left = 0
        self._arrive(army, origin)
        self._check_end()
        return self.events[start:]

    def assault(self, army_id):
        """Storm the walls of the province `army` is besieging."""
        army = self.armies[army_id]
        p = self.provinces[army.province]
        if self.over or not self.besieging(army):
            raise MoveError(f"{army.general} is not besieging anything")
        if army.moves_left <= 0:
            raise MoveError(f"{army.general} needs a fresh turn to assault")
        start = len(self.events)
        army.moves_left = 0
        result = battle.resolve(self._attackers([army], p.id), self._garrison_side(p.id), self.data.units,
                                self.rng, province=p.id, kind="assault")
        self._record_battle(result)
        self._drop_if_destroyed(army)
        if result.attacker_won:
            self._capture(p, army.faction)  # a broken garrison has nowhere to run: it surrenders
        else:
            p.besieged_by = None
            if army.id in self.armies:
                self._retreat(army, None)
        self._check_end()
        return self.events[start:]

    def _leave(self, army):
        here = self.provinces[army.province]
        if here.besieged_by == army.id:
            others = [a for a in self.armies_in(here.id) if a.faction == army.faction and a.id != army.id]
            here.besieged_by = others[0].id if others else None

    def _arrive(self, army, origin):
        p = self.provinces[army.province]
        defenders, enemy_armies = self._field_defenders(army.faction, p.id)
        if defenders:
            result = battle.resolve(self._attackers([army], p.id), defenders, self.data.units, self.rng,
                                    province=p.id, kind="field")
            self._record_battle(result)
            for a in [army, *enemy_armies]:
                self._drop_if_destroyed(a)
            if not result.attacker_won:
                if army.id in self.armies:
                    self._retreat(army, origin)
                return
            for a in enemy_armies:
                if a.id in self.armies:
                    self._retreat(a, None)
            if p.besieged_by is not None and p.besieged_by not in self.armies:
                p.besieged_by = None
        if p.owner == army.faction:
            return
        if p.garrison:
            if p.besieged_by is None:
                p.besieged_by = army.id
                self._event(SiegeStarted(p.id, army.faction),
                            f"{self.faction_name(army.faction)} lay siege to {p.name}.")
        else:
            self._capture(p, army.faction)

    def _record_battle(self, result):
        a, d = result.attacker, result.defender
        place = self.provinces[result.province].name
        what = "storm" if result.kind == "assault" else "attack"
        verdict = "and win" if result.attacker_won else "but are thrown back"
        self._event(Battle(result), f"{self.faction_name(a.faction)} {what} {self.faction_name(d.faction, True)} "
                                    f"at {place} {verdict}.")

    def _drop_if_destroyed(self, army):
        if army.id in self.armies and not army.regiments:
            del self.armies[army.id]
            self.log.append(f"{army.general}'s army is destroyed.")

    def _retreat(self, army, prefer):
        """Fall back to a friendly neighbouring province, or be destroyed if there is none."""
        options = [prefer] if prefer and self._safe_for(army.faction, prefer) else []
        here = self.provinces[army.province]
        options += sorted(n for n in here.neighbors if self.provinces[n].owner == army.faction
                          and self._safe_for(army.faction, n))
        if options:
            self._leave(army)
            army.province = options[0]
            army.moves_left = 0
            self._event(Retreated(army.faction, army.general, options[0]),
                        f"{army.general} retreats to {self.provinces[options[0]].name}.")
        else:
            self._leave(army)
            del self.armies[army.id]
            self._event(Retreated(army.faction, army.general, None),
                        f"{army.general}'s army is cut off and destroyed.")

    def _safe_for(self, fid, pid):
        return not self.has_enemy_army(fid, pid)

    def _capture(self, p, fid):
        previous = p.owner
        p.owner = fid
        p.garrison = []
        p.besieged_by = None
        self._event(Captured(p.id, fid, previous),
                    f"{self.faction_name(fid)} take {p.name}" + (f" from {self.faction_name(previous, True)}." if previous else "."))

    def _event(self, event, message):
        self.events.append(event)
        self.log.append(message)

    def _check_end(self):
        for fid in list(self.turn_order):
            if not self.provinces_of(fid):
                self.eliminated.append(fid)
                for a in self.armies_of(fid):
                    self._leave(a)
                    del self.armies[a.id]
                self._event(Eliminated(fid), f"{self.faction_name(fid)} have been wiped from the land!")
        if self.winner:
            return
        for fid in self.turn_order:
            if len(self.provinces_of(fid)) >= self.victory_rules["conquest_provinces"]:
                self._win(fid, "conquest")
                return
        if len(self.turn_order) == 1:
            self._win(self.turn_order[0], "last_standing")

    def _win(self, fid, kind):
        self.winner = Victory(fid, kind)
        self._event(self.winner, f"{self.faction_name(fid)} are masters of the Carpathians!")

    # --- turns -----------------------------------------------------------------------------

    def end_turn(self):
        """The player ends their turn: every AI faction acts, then a new season begins."""
        if self.over:
            return
        for fid in self.turn_order[1:]:
            self.ai_turn(fid)
            if self.over:
                return
        self._new_round()

    def ai_turn(self, fid):
        if fid in self.ai and fid not in self.eliminated and not self.over:
            self.ai[fid].take_turn(self)

    def _new_round(self):
        self.round += 1
        self.log.append(f"{self.date} begins.")
        for p in self.provinces.values():
            if p.besieged_by is not None and (p.besieged_by not in self.armies
                                              or self.armies[p.besieged_by].province != p.id):
                p.besieged_by = None
            if p.besieged_by is not None:
                for r in p.garrison:
                    r.hp -= self.data.units[r.unit]["hp"] * SIEGE_ATTRITION
                p.garrison[:] = [r for r in p.garrison if r.hp >= battle.MIN_HP]
                if not p.garrison:
                    besieger = self.armies[p.besieged_by]
                    self.log.append(f"The starving defenders of {p.name} surrender.")
                    self._capture(p, besieger.faction)
            elif p.owner:
                self._heal(p.garrison)
        for army in self.armies.values():
            army.moves_left = self.data.map["army_moves"]
            if self.provinces[army.province].owner == army.faction:
                self._heal(army.regiments)
        self._check_end()
        if not self.winner:
            self._count_heart()

    def _heal(self, regiments):
        for r in regiments:
            full = self.data.units[r.unit]["hp"]
            r.hp = min(full, r.hp + full * HEAL_RATE)

    def _count_heart(self):
        holder = self.heart_holder()
        for fid in self.turn_order:
            holds = fid == holder and self.provinces[self.capital_of(fid)].owner == fid
            self.heart_turns[fid] = self.heart_turns.get(fid, 0) + 1 if holds else 0
            if self.heart_turns[fid] >= self.victory_rules["heart_turns"]:
                self.log.append(f"The Heart of the Mountains beats for {self.faction_name(fid, True)}.")
                self._win(fid, "legend")
                return
