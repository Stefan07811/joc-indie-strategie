"""Campaign state: provinces, armies, movement and the turn cycle. No pygame here."""

import heapq
from dataclasses import dataclass, field

SEASONS = ("Spring", "Summer", "Autumn", "Winter")


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


@dataclass
class Army:
    id: int
    faction: str
    province: str
    general: str
    regiments: list[str]
    moves_left: int


@dataclass
class Reach:
    cost: int
    path: list[str]  # provinces entered, in order, ending with the destination


@dataclass
class Game:
    data: object
    player: str
    provinces: dict[str, Province] = field(default_factory=dict)
    armies: dict[int, Army] = field(default_factory=dict)
    round: int = 0
    log: list[str] = field(default_factory=list)
    ai: dict = field(default_factory=dict)
    _next_army_id: int = 1

    @classmethod
    def new(cls, data, player, ai_factory=None):
        if not data.factions[player]["playable"]:
            raise ValueError(f"{player} is not a playable faction")
        game = cls(data=data, player=player)
        for p in data.provinces:
            game.provinces[p["id"]] = Province(
                id=p["id"], name=p["name"], terrain=p["terrain"], x=p["x"], y=p["y"],
                owner=p["owner"], neighbors=list(p.get("neighbors", ())), special=p.get("special"),
            )
        for a in data.map["start_armies"]:
            game.add_army(a["faction"], a["province"], a["general"], a["regiments"])
        if ai_factory is None:
            from .ai import SimpleAI as ai_factory
        for fid in game.turn_order:
            if fid != player:
                game.ai[fid] = ai_factory(fid)
        game.log.append(f"{game.date}: {game.faction_name(player)} begin their campaign.")
        return game

    # --- queries ---------------------------------------------------------------------------

    @property
    def turn_order(self):
        """Playable factions in data order, the player first."""
        others = [f for f, d in self.data.factions.items() if d["playable"] and f != self.player]
        return [self.player, *others]

    @property
    def season(self):
        return SEASONS[self.round % 4]

    @property
    def year(self):
        return self.data.map["start_year"] + self.round // 4

    @property
    def date(self):
        return f"{self.season} {self.year}"

    def faction_name(self, fid):
        return self.data.factions[fid]["name"] if fid else "No one"

    def capital_of(self, fid):
        return self.data.factions[fid]["capital"]

    def armies_in(self, pid):
        return [a for a in self.armies.values() if a.province == pid]

    def armies_of(self, fid):
        return [a for a in self.armies.values() if a.faction == fid]

    def provinces_of(self, fid):
        return [p for p in self.provinces.values() if p.owner == fid]

    def enter_cost(self, fid, pid):
        """Movement points faction `fid` spends to enter province `pid`."""
        terrain = self.provinces[pid].terrain
        if terrain in self.data.factions[fid]["terrain_mastery"]:
            return 1
        return self.data.terrain[terrain]["move_cost"]

    def blocked_for(self, fid, pid):
        """Provinces holding a foreign army can't be entered or crossed (battles arrive in M2)."""
        return any(a.faction != fid for a in self.armies_in(pid))

    def reachable(self, army):
        """Every province `army` can reach this turn, as {province id: Reach}."""
        best = {army.province: Reach(0, [])}
        queue = [(0, army.province)]
        while queue:
            cost, pid = heapq.heappop(queue)
            if cost > best[pid].cost:
                continue
            for nid in self.provinces[pid].neighbors:
                if self.blocked_for(army.faction, nid):
                    continue
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

    # --- actions ---------------------------------------------------------------------------

    def add_army(self, fid, pid, general, regiments):
        army = Army(self._next_army_id, fid, pid, general, list(regiments), self.data.map["army_moves"])
        self.armies[army.id] = army
        self._next_army_id += 1
        return army

    def move_army(self, army_id, target):
        army = self.armies[army_id]
        reach = self.reachable(army).get(target)
        if reach is None:
            raise MoveError(f"{army.general} cannot reach {target} this turn")
        army.moves_left -= reach.cost
        army.province = target
        return reach

    def end_turn(self):
        """The player ends their turn: every AI faction acts, then a new season begins."""
        for fid in self.turn_order[1:]:
            self.ai[fid].take_turn(self)
        self.round += 1
        for army in self.armies.values():
            army.moves_left = self.data.map["army_moves"]
        self.log.append(f"{self.date} begins.")
