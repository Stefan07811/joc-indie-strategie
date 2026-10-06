"""Computer-controlled factions.

Each turn the AI first spends its gold (one building, then as many regiments as it can afford
without running up a deficit), then moves its armies.

Armies: every army picks the most valuable province it can realistically take
(close, weakly held, ideally the Heart or an enemy capital), checks its odds with the same
battle maths the game uses, and marches there. Besiegers storm the walls once the odds are
good, otherwise they let hunger do the work. Smarter planning and personalities come in M5.
"""

from . import economy

MIN_SHARE_LEFT = 0.45  # only fight battles we expect to win with at least this much of the army left
GOLD_RESERVE = 40  # kept back for emergencies
BUILD_ORDER = ("market", "farm", "mine", "barracks", "walls")


class SimpleAI:
    def __init__(self, faction):
        self.faction = faction

    def take_turn(self, game):
        self._build(game)
        self._recruit(game)
        for army_id in sorted(a.id for a in game.armies_of(self.faction)):
            if game.over:
                return
            army = game.armies.get(army_id)
            if army is None:
                continue
            if game.besieging(army):
                self._siege(game, army)
            else:
                self._march(game, army)

    def _siege(self, game, army):
        forecast = game.forecast(army, army.province)
        if forecast and forecast[0] and forecast[1] >= MIN_SHARE_LEFT:
            game.assault(army.id)

    def _march(self, game, army):
        target = self._goal(game, army)
        if target is None or target == army.province:
            return
        reach = game.reachable(army)
        if target in reach:
            if game.has_enemy_army(self.faction, target):
                wins, share_left = game.forecast(army, target)
                if not wins or share_left < MIN_SHARE_LEFT:
                    return  # wait for a better moment
            game.move_army(army.id, target)
            return
        # Otherwise step toward it, through friendly land or provinces we can take without a fight.
        dist_to_goal = game.distances(self.faction, target)
        steps = [pid for pid in reach if game.passable(self.faction, pid) or not game.defended(self.faction, pid)]
        if not steps:
            return
        dest = min(steps, key=lambda pid: (dist_to_goal.get(pid, float("inf")), reach[pid].cost, pid))
        if dist_to_goal.get(dest, float("inf")) < dist_to_goal.get(army.province, float("inf")):
            game.move_army(army.id, dest)

    def _goal(self, game, army):
        dist = game.distances(self.faction, army.province)
        best, best_score = None, 0.0
        for p in game.provinces.values():
            if p.owner == self.faction and not game.has_enemy_army(self.faction, p.id):
                continue
            if any(a.faction == self.faction and a.id != army.id and game.besieging(a) for a in game.armies_in(p.id)):
                continue  # a comrade is already starving it out
            value = self._value(game, p)
            if not self._can_take(game, army, p):
                continue
            score = value / (1 + dist[p.id])
            if score > best_score or (score == best_score and best and p.id < best):
                best, best_score = p.id, score
        return best

    def _value(self, game, p):
        if p.owner == self.faction:
            return 8.0  # an enemy army on our own soil
        if p.special == "heart":
            # the longer a rival holds the Heart, the closer they are to a legendary victory
            return 6.0 + 2.0 * game.heart_turns.get(p.owner, 0)
        if p.owner and game.capital_of(p.owner) == p.id:
            # taking a Heart holder's capital also breaks their count
            return 5.0 + 1.5 * game.heart_turns.get(p.owner, 0)
        return 3.0 if p.owner is None else 3.5

    def _can_take(self, game, army, p):
        """Would `army` beat what holds province `p` (its armies, and later its garrison)?"""
        ours = game.strength(army.regiments)
        enemies = [a for a in game.armies_in(p.id) if a.faction != self.faction]
        theirs = sum(game.strength(a.regiments) for a in enemies)
        if p.owner != self.faction and p.garrison:
            theirs += game.strength(p.garrison) * (1.5 if p.walls else 1.0) * 0.7  # sieges wear them down
        return theirs == 0 or ours >= theirs * 1.1

    # --- economy ---------------------------------------------------------------------------

    def _build(self, game):
        fid = self.faction
        gold = game.treasury[fid].gold
        bal = economy.balance(game, fid)
        order = list(BUILD_ORDER)
        if bal.food < 2:
            order.remove("farm")
            order.insert(0, "farm")
        capital = game.capital_of(fid)
        # the capital first, then the richest provinces
        provinces = sorted(game.provinces_of(fid), key=lambda p: (p.id != capital, -economy.province_yield(game, p)[0], p.id))
        for bid in order:
            if bid == "barracks":
                candidates = [p for p in provinces if p.id == capital] or provinces[:1]
            elif bid == "walls":
                continue  # capitals are walled already; border forts come with M5's smarter AI
            else:
                candidates = provinces
            for p in candidates:
                cost = game.data.buildings[bid]["cost"]
                if gold - cost >= GOLD_RESERVE and economy.building_blocker(game, fid, p.id, bid) is None:
                    game.build(fid, p.id, bid)
                    return

    def _recruit(self, game):
        fid = self.faction
        units = game.data.units
        capital = game.capital_of(fid)
        places = [p for p in game.provinces_of(fid) if economy.can_manage(game, fid, p.id) is None]
        places.sort(key=lambda p: (p.id != capital, not game.armies_in(p.id), p.id))
        for p in places:
            while True:
                bal = economy.balance(game, fid)
                queued_upkeep = sum(units[u]["upkeep"] for q in game.provinces_of(fid) for u in q.recruits)
                spare = bal.gold - queued_upkeep
                options = [u for u in economy.recruitable_units(game, fid)
                           if economy.unit_blocker(game, fid, p.id, u) is None
                           and game.treasury[fid].gold - units[u]["cost"] >= GOLD_RESERVE
                           and units[u]["upkeep"] <= spare * 0.8]
                if not options or game.treasury[fid].food + bal.food * 2 < 0:
                    break
                options.sort(key=lambda u: (-units[u]["cost"], u))
                game.recruit(fid, p.id, game.rng.choice(options[:2]))

