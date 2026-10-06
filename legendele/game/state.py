"""Campaign state: provinces, armies, movement, war and the turn cycle. No pygame here."""

import heapq
import random
from dataclasses import dataclass, field

from . import battle, diplomacy, economy, legends
from .battle import BattleResult, Regiment, Side
from .economy import Treasury

SEASONS = ("Spring", "Summer", "Autumn", "Winter")
HEAL_RATE = 0.1  # share of full strength regiments recover each season on friendly ground
SIEGE_ATTRITION = 0.15  # share of full strength a besieged garrison loses each season
REBELS = legends.REBELS


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
    buildings: list[str] = field(default_factory=list)
    construction: dict | None = None  # {"building": id, "turns_left": n}
    recruits: list[str] = field(default_factory=list)  # unit ids arriving next season
    captured_round: int | None = None  # when it last changed hands (fresh conquests are restless)


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
    treasury: dict[str, Treasury] = field(default_factory=dict)
    spectate: bool = False  # AI-only games (simulations): the war goes on after the player falls
    _next_army_id: int = 1
    _generals_named: dict[str, int] = field(default_factory=dict)
    abduct_ready: dict[str, int] = field(default_factory=dict)  # round from which a faction may abduct again
    rebels: object = field(default_factory=legends.RebelAI)
    # diplomacy (see diplomacy.py)
    relations: dict = field(default_factory=dict)  # frozenset({a, b}) -> "war" / "peace" / "alliance"
    war_since: dict = field(default_factory=dict)
    truce_until: dict = field(default_factory=dict)
    treachery: dict[str, int] = field(default_factory=dict)  # broken treaties per faction
    grudges: set = field(default_factory=set)  # (victim, traitor)
    last_proposal: dict = field(default_factory=dict)
    proposals: list = field(default_factory=list)  # offers waiting for the human player's answer

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
        for p in game.provinces.values():
            if p.owner:
                game._muster(p)
        if ai_factory is None:
            from .ai import SimpleAI as ai_factory
        diplomacy.setup(game)
        for fid in game.turn_order:
            game.heart_turns[fid] = 0
            game.treasury[fid] = Treasury(game.rules["start_gold"], game.rules["start_food"])
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
        return self.winner is not None or (self.player in self.eliminated and not self.spectate)

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

    @property
    def rules(self):
        """Economy constants from map.json."""
        return self.data.map["economy"]

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
        if self.at_home(fid, pid):
            return 1
        return self.data.terrain[terrain]["move_cost"]

    def at_home(self, fid, pid):
        """Does `fid` master the terrain of `pid`? The Heart of the Mountains belongs to no legend."""
        p = self.provinces[pid]
        return p.special != "heart" and p.terrain in self.data.factions[fid]["terrain_mastery"]

    def at_war(self, a, b):
        return diplomacy.relation(self, a, b) == diplomacy.WAR

    def friendly_land(self, fid, pid):
        """Our own province or an ally's."""
        owner = self.provinces[pid].owner
        return owner is not None and diplomacy.relation(self, fid, owner) in ("self", diplomacy.ALLIANCE)

    def has_enemy_army(self, fid, pid):
        return any(a.faction != fid and self.at_war(fid, a.faction) for a in self.armies_in(pid))

    def blocked(self, fid, pid):
        """Land and armies of factions at peace with us are off limits."""
        p = self.provinces[pid]
        if p.owner is not None and diplomacy.relation(self, fid, p.owner) == diplomacy.PEACE:
            return True
        return any(diplomacy.relation(self, fid, a.faction) == diplomacy.PEACE for a in self.armies_in(pid))

    def defended(self, fid, pid):
        """Would an army of `fid` entering `pid` have to fight or besiege?"""
        p = self.provinces[pid]
        return self.has_enemy_army(fid, pid) or (not self.friendly_land(fid, pid) and bool(p.garrison))

    def armies_seen(self, viewer, pid):
        """The armies in `pid` that faction `viewer` can see (the Fae hide in forests)."""
        return [a for a in self.armies_in(pid) if legends.visible_to(self, viewer, a)]

    def looks_defended(self, fid, pid):
        """Like defended(), but only counting what `fid` can see."""
        p = self.provinces[pid]
        return (any(a.faction != fid and self.at_war(fid, a.faction) for a in self.armies_seen(fid, pid))
                or (not self.friendly_land(fid, pid) and bool(p.garrison)))

    def passable(self, fid, pid):
        """Armies may march on through their own provinces as long as no enemy stands there.
        Entering any other province ends the march (to capture, fight or besiege)."""
        return self.friendly_land(fid, pid) and not self.has_enemy_army(fid, pid)

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
                if ncost > army.moves_left or self.blocked(army.faction, nid):
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
        mult = battle.HOME_TERRAIN_BONUS if self.at_home(fid, pid) else 1.0
        defense = mult * (self.data.terrain[p.terrain]["defense"] if defending else 1.0)
        if walls:
            defense *= battle.WALLS_DEFENSE
        return Side(
            faction=fid, regiments=regiments, leader=leader, defense_mult=defense,
            attack_mult=mult * (battle.GENERAL_BONUS if leader else 1.0) * legends.attack_modifier(self, fid, pid),
            resolve_bonus=battle.WALLS_RESOLVE if walls else 0.0,
            creature=self.data.factions[fid]["creature"],
            walls=walls, ambush_ground=defending and p.terrain == "forest",
        )

    def _attackers(self, armies, pid):
        regiments = [r for a in armies for r in a.regiments]
        return self._side(armies[0].faction, regiments, armies[0].general, pid, defending=False)

    def _field_defenders(self, fid, pid, seen_by=None):
        enemies = [a for a in self.armies_in(pid) if a.faction != fid and self.at_war(fid, a.faction)
                   and (seen_by is None or legends.visible_to(self, seen_by, a))]
        if not enemies:
            return None, []
        regiments = [r for a in enemies for r in a.regiments]
        return self._side(enemies[0].faction, regiments, enemies[0].general, pid, defending=True), enemies

    def _garrison_side(self, pid):
        p = self.provinces[pid]
        return self._side(p.owner or REBELS, p.garrison, None, pid, defending=True, walls=p.walls)

    def forecast(self, army, pid, seen_only=False):
        """Predicted result of `army` marching into / assaulting `pid`: (wins?, share of army left),
        or None if no fight would happen. With `seen_only`, hidden enemies are left out of the sums."""
        attackers = self._attackers([army], pid)
        if pid != army.province:
            defenders, _ = self._field_defenders(army.faction, pid, army.faction if seen_only else None)
            if defenders:
                return battle.predict(attackers, defenders, self.data.units)
            if self.friendly_land(army.faction, pid):
                return None
        p = self.provinces[pid]
        if self.friendly_land(army.faction, pid) or not p.garrison:
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
            legends.raise_dead(self, result, army=army)
            self._capture(p, army.faction)  # a broken garrison has nowhere to run: it surrenders
        else:
            legends.raise_dead(self, result, garrison_of=p.id)
            p.besieged_by = None
            if army.id in self.armies:
                self._retreat(army, None)
        self._check_end()
        return self.events[start:]

    def abduct(self, army_id):
        """Dragonkin only: carry off a rival heir from a capital next to (or at) this army."""
        if self.over:
            raise MoveError("the war is over")
        start = len(self.events)
        try:
            legends.abduct(self, self.armies[army_id])
        except ValueError as e:
            raise MoveError(str(e)) from None
        self._check_end()
        return self.events[start:]

    def declare_war(self, fid, other):
        start = len(self.events)
        try:
            diplomacy.declare_war(self, fid, other)
        except diplomacy.DiplomacyError as e:
            raise MoveError(str(e)) from None
        return self.events[start:]

    def propose(self, kind, fid, other, gold=0):
        """Offer peace or an alliance; returns True/False from an AI, None if a human must answer."""
        try:
            return diplomacy.propose(self, diplomacy.Proposal(kind, fid, other, gold))
        except diplomacy.DiplomacyError as e:
            raise MoveError(str(e)) from None

    def break_alliance(self, fid, other):
        try:
            diplomacy.break_alliance(self, fid, other)
        except diplomacy.DiplomacyError as e:
            raise MoveError(str(e)) from None

    def build(self, fid, pid, bid):
        reason = economy.building_blocker(self, fid, pid, bid)
        if reason:
            raise MoveError(reason)
        b = self.data.buildings[bid]
        self.treasury[fid].gold -= b["cost"]
        self.provinces[pid].construction = {"building": bid, "turns_left": b["turns"]}

    def recruit(self, fid, pid, uid):
        reason = economy.unit_blocker(self, fid, pid, uid)
        if reason:
            raise MoveError(reason)
        self.treasury[fid].gold -= self.data.units[uid]["cost"]
        self.provinces[pid].recruits.append(uid)

    def cancel_recruit(self, pid, index):
        """Take back a regiment still waiting to be trained, with a full refund."""
        p = self.provinces[pid]
        uid = p.recruits.pop(index)
        self.treasury[p.owner].gold += self.data.units[uid]["cost"]

    def merge(self, army_id):
        """Fold the other armies of the same faction standing here into this one (as far as room allows)."""
        army = self.armies[army_id]
        cap = self.rules["max_regiments"]
        for other in self.armies_in(army.province):
            if other.faction != army.faction or other.id == army.id:
                continue
            room = cap - len(army.regiments)
            if room <= 0:
                break
            moved, other.regiments = other.regiments[:room], other.regiments[room:]
            army.regiments += moved
            army.moves_left = min(army.moves_left, other.moves_left)
            if not other.regiments:
                self._leave(other)
                del self.armies[other.id]

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
                survivors = [a for a in enemy_armies if a.id in self.armies]
                if survivors:
                    legends.raise_dead(self, result, army=survivors[0])
                if army.id in self.armies:
                    self._retreat(army, origin)
                return
            legends.raise_dead(self, result, army=army)
            for a in enemy_armies:
                if a.id in self.armies:
                    self._retreat(a, None)
            if p.besieged_by is not None and p.besieged_by not in self.armies:
                p.besieged_by = None
        if self.friendly_land(army.faction, p.id):
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
        self._bury(army, "is destroyed")

    def _retreat(self, army, prefer):
        """Fall back to a friendly neighbouring province, or be destroyed if there is none."""
        options = [prefer] if prefer and self._safe_for(army.faction, prefer) else []
        here = self.provinces[army.province]
        options += sorted(n for n in here.neighbors if self.friendly_land(army.faction, n)
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
        p.construction = None  # half-built work and recruits in training are lost; finished buildings stay
        p.recruits = []
        p.captured_round = self.round
        if fid == REBELS:
            # the Outlaws hold the province as free land: their army becomes its garrison
            p.owner = None
            for rebels in [a for a in self.armies_in(p.id) if a.faction == REBELS]:
                p.garrison += rebels.regiments
                del self.armies[rebels.id]
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
        for fid in self.turn_order:
            if fid == self.player:
                continue
            self.ai_turn(fid)
            if self.over:
                return
        self.rebels.take_turn(self)
        if self.over:
            return
        self._new_round()

    def ai_turn(self, fid):
        if fid in self.ai and fid not in self.eliminated and not self.over:
            self.ai[fid].take_turn(self)

    def _new_round(self):
        self.round += 1
        self.log.append(f"{self.date} begins.")
        for fid in self.turn_order:
            self._collect(fid)
        for p in self.provinces.values():
            self._advance_construction(p)
            self._train_recruits(p)
            self._siege_or_rest(p)
        for army in list(self.armies.values()):
            army.moves_left = self.data.map["army_moves"]
            if self.provinces[army.province].owner == army.faction:
                self._heal(army.regiments)
            elif self.season == "Winter" and not self.data.factions[army.faction]["winter_hardy"]:
                for r in army.regiments:
                    r.hp -= self.data.units[r.unit]["hp"] * self.rules["winter_attrition"]
                self._bury(army, "freezes to death in the snow")
        legends.hora(self)
        legends.healers(self)
        legends.rebellions(self)
        self._check_end()
        if not self.winner:
            self._count_heart()

    def _collect(self, fid):
        """Taxes in, wages out, food in the granary; hunger and desertion when they run dry."""
        t = self.treasury[fid]
        bal = economy.balance(self, fid)
        t.gold += bal.gold
        t.food += bal.food
        if t.food < 0:
            t.food = 0
            for army in self.armies_of(fid):
                for r in army.regiments:
                    r.hp -= self.data.units[r.unit]["hp"] * self.rules["hunger_loss"]
                self._bury(army, "starves")
            if fid == self.player:
                self.log.append("The granaries are empty: our armies go hungry!")
        if t.gold < 0:
            regiments = [(self.data.units[r.unit]["upkeep"], a.id, i) for a in self.armies_of(fid)
                         for i, r in enumerate(a.regiments)]
            if regiments:
                _, army_id, i = max(regiments)
                army = self.armies[army_id]
                deserter = army.regiments.pop(i)
                self.log.append(f"Unpaid, the {self.data.units[deserter.unit]['name']} of {army.general} desert.")
                self._bury(army, "melts away")

    def _advance_construction(self, p):
        if not p.construction:
            return
        p.construction["turns_left"] -= 1
        if p.construction["turns_left"] > 0:
            return
        bid = p.construction["building"]
        p.buildings.append(bid)
        p.construction = None
        if self.data.buildings[bid].get("walls"):
            p.walls = True
        if p.owner == self.player:
            self.log.append(f"{self.data.buildings[bid]['name']} completed in {p.name}.")

    def _train_recruits(self, p):
        if not p.recruits or p.owner is None:
            return
        cap = self.rules["max_regiments"]
        if self.has_enemy_army(p.owner, p.id):
            # the enemy arrived while they trained: they man the walls instead of marching out
            p.garrison += self._regiments(p.recruits)
            p.recruits = []
            return
        for uid in p.recruits:
            army = next((a for a in self.armies_in(p.id) if a.faction == p.owner and len(a.regiments) < cap), None)
            if army is None:
                army = self.add_army(p.owner, p.id, self._new_general(p.owner), [])
                if p.owner == self.player:
                    self.log.append(f"{army.general} takes command of a new army in {p.name}.")
            army.regiments += self._regiments([uid])
        p.recruits = []

    def _siege_or_rest(self, p):
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
            self._muster(p)

    def _muster(self, p):
        """Walled towns keep a proper garrison; every other province raises a militia."""
        size = self.rules["garrison_size"] if p.walls else self.rules["militia_size"]
        if len(p.garrison) < size:
            p.garrison += self._regiments([self._cheapest_unit(p.owner)])

    def _cheapest_unit(self, fid):
        units = [u for u in economy.recruitable_units(self, fid) if self.data.units[u]["tier"] == 1]
        return min(units, key=lambda u: (self.data.units[u]["cost"], -self.data.units[u]["defense"], u))

    def _new_general(self, fid):
        names = self.data.factions[fid]["general_names"]
        n = self._generals_named.get(fid, 0)
        self._generals_named[fid] = n + 1
        return names[n] if n < len(names) else f"{names[n % len(names)]} {n // len(names) + 1}"

    def _bury(self, army, how):
        army.regiments[:] = [r for r in army.regiments if r.hp >= battle.MIN_HP]
        if not army.regiments and army.id in self.armies:
            self._leave(army)
            del self.armies[army.id]
            self.log.append(f"{army.general}'s army {how}.")

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
