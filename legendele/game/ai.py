"""Computer-controlled factions.

Every AI has a personality (factions.json, "ai"): how friendly and aggressive it is, how many wars
it will wage at once, how much stronger it must be before declaring one, how readily it sues for
peace, how loyal it is to treaties, how much gold sways it, and which targets it values.

Each turn an AI:
1. Talks: sues for peace in wars going badly, courts friends, drops allies it has come to hate,
   and may declare war on a weaker neighbour. Everyone turns on whoever comes close to winning
   (holding the Heart for a while, or nearing a conquest victory) and refuses them peace.
2. Spends: one building (calming restless provinces first, walls on dangerous borders when rich),
   then as many regiments as it can afford without running up a deficit.
3. Marches: every army picks the most valuable province it can realistically take, checks its odds
   with the same battle maths the game uses, and goes. Armies rush home to a threatened capital
   (and from there strike at the threat), stay where leaving would start a revolt, and besiegers storm the walls once the odds are good.
4. Gathers: armies that ended up together merge.
"""

from . import diplomacy, economy, legends
from .diplomacy import ALLIANCE, PEACE, WAR

MIN_SHARE_LEFT = 0.45  # only fight battles we expect to win with at least this much of the army left
GOLD_RESERVE = 40  # kept back for emergencies
BUILD_ORDER = ("market", "farm", "mine", "barracks", "walls")
WALLS_WHEN_RICHER_THAN = 400
HEART_ALARM = 3  # seasons of holding the Heart after which everyone turns on the holder
CONQUEST_ALARM = 0.3  # share of the land at which everyone turns on the largest realm

DEFAULT_PERSONALITY = {
    "personality": "Cautious", "summary": "", "friendliness": 0, "aggression": 0.4, "max_wars": 2,
    "war_ratio": 1.3, "peace_ratio": 0.8, "loyalty": 0.9, "greed": 1.0, "alliance_threshold": 30,
    "stay_near_home": False, "targets": {"neutral": 3.0, "enemy": 3.5, "heart": 6.0},
}


class SimpleAI:
    def __init__(self, faction, personality=None):
        self.faction = faction
        self._personality = personality

    def personality(self, game):
        if self._personality is None:
            self._personality = {**DEFAULT_PERSONALITY, **game.data.factions[self.faction].get("ai", {})}
        return self._personality

    def take_turn(self, game):
        self._diplomacy(game)
        self._build(game)
        self._recruit(game)
        for army_id in sorted(a.id for a in game.armies_of(self.faction)):
            if game.over:
                return
            army = game.armies.get(army_id)
            if army is None:
                continue
            if self._abduct(game, army):
                continue
            if game.besieging(army):
                self._siege(game, army)
            elif not self._on_guard(game, army):
                self._march(game, army)
        self._gather(game)

    # --- diplomacy -------------------------------------------------------------------------

    def consider(self, game, proposal):
        """Answer a proposal from another faction."""
        me, other = self.faction, proposal.faction
        pers = self.personality(game)
        if other in self._alarming(game):
            return False
        mood, _ = diplomacy.attitude(game, me, other)
        if proposal.kind == "alliance":
            return not diplomacy.never_allied(game, me, other) and mood >= pers["alliance_threshold"]
        ours, theirs = diplomacy.might(game, me), max(1.0, diplomacy.might(game, other))
        pressure = 0
        if ours < theirs * pers["peace_ratio"]:
            pressure += 30
        if self._weary(game, other):
            pressure += 15
        if ours > theirs * pers["war_ratio"]:
            pressure -= 20  # we are winning this war
        return mood + pressure + proposal.gold * pers["greed"] / 10 >= 0

    def _diplomacy(self, game):
        me = self.faction
        pers = self.personality(game)
        for other in list(game.turn_order):
            if other == me:
                continue
            rel = diplomacy.relation(game, me, other)
            mood, _ = diplomacy.attitude(game, me, other)
            if rel == WAR and self._wants_peace(game, other):
                self._offer(game, "peace", other)
            elif rel == PEACE and mood >= pers["alliance_threshold"] and game.rng.random() < 0.3:
                self._offer(game, "alliance", other)
            elif rel == ALLIANCE and mood < -20:
                game.break_alliance(me, other)
        self._maybe_declare_war(game)

    def _alarming(self, game):
        """Rivals on their way to winning: whoever has held the Heart for a while, and the largest realm
        once it is big enough to threaten a conquest victory."""
        sizes = {f: len(game.provinces_of(f)) for f in game.turn_order}
        largest = max(sizes.values())
        needed = round(CONQUEST_ALARM * len(game.provinces))
        return {f for f in game.turn_order if f != self.faction and
                (game.heart_turns.get(f, 0) >= HEART_ALARM or sizes[f] == largest >= needed)}

    def _offer(self, game, kind, other):
        if diplomacy.proposal_blocker(game, diplomacy.Proposal(kind, self.faction, other)) is None:
            game.propose(kind, self.faction, other)

    def _weary(self, game, other):
        since = game.war_since.get(diplomacy.key(self.faction, other), 0)
        return game.round - since >= diplomacy.rules(game)["weariness_turns"]

    def _wants_peace(self, game, other):
        pers = self.personality(game)
        ours, theirs = diplomacy.might(game, self.faction), max(1.0, diplomacy.might(game, other))
        if other in self._alarming(game):
            return False  # no peace with whoever is about to win
        return ours < theirs * pers["peace_ratio"] or (self._weary(game, other) and ours < theirs * 1.5)

    def _maybe_declare_war(self, game):
        me = self.faction
        pers = self.personality(game)
        alarm = self._alarming(game)
        wars = diplomacy.at_war_with(game, me)
        if not alarm and (len(wars) >= pers["max_wars"] or game.rng.random() >= pers["aggression"] * 0.25):
            return
        ours = diplomacy.might(game, me)
        options = []
        for other in game.turn_order:
            if other == me or diplomacy.relation(game, me, other) != PEACE:
                continue
            if other not in alarm and not diplomacy.shares_border(game, me, other):
                continue
            if diplomacy.in_truce(game, me, other) and game.rng.random() < pers["loyalty"]:
                continue  # we keep our word (usually)
            ratio = ours / max(1.0, diplomacy.might(game, other))
            mood, _ = diplomacy.attitude(game, me, other)
            if other in alarm:
                options.append((ratio + 2, other))
            elif ratio >= pers["war_ratio"] and mood < 25:
                options.append((ratio - mood / 100, other))
        if options:
            game.declare_war(me, max(options)[1])

    # --- armies ----------------------------------------------------------------------------

    def _abduct(self, game, army):
        pid, reason = legends.abduction_target(game, army)
        if reason:
            return False
        victim = game.provinces[pid].owner
        if legends.abduction_chance(game, army, pid) < 0.5 or game.treasury[victim].gold < 60:
            return False
        game.abduct(army.id)
        return True

    def _on_guard(self, game, army):
        """Stay to keep the peace where leaving would let the province rise up."""
        p = game.provinces[army.province]
        if p.owner != self.faction:
            return False
        order, _ = legends.public_order(game, p)
        others = len(p.garrison) + sum(len(a.regiments) for a in game.armies_in(p.id)
                                       if a.faction == self.faction and a.id != army.id)
        rules = game.data.map["order"]
        without_us = order - min(rules["max_troops"], (others + len(army.regiments)) * rules["per_regiment"]) \
            + min(rules["max_troops"], others * rules["per_regiment"])
        return without_us < 0

    def _capital_threatened(self, game, without=None):
        """Are the enemies around our capital stronger than its walls, garrison and the armies inside
        (not counting `without`)?"""
        capital = game.provinces[game.capital_of(self.faction)]
        if capital.owner != self.faction:
            return False
        threat = sum(game.strength(a.regiments) for pid in (capital.id, *capital.neighbors)
                     for a in game.armies_in(pid) if game.at_war(self.faction, a.faction))
        if not threat:
            return False
        defence = game.strength(capital.garrison) * (1.5 if capital.walls else 1.0)
        defence += sum(game.strength(a.regiments) for a in game.armies_in(capital.id)
                       if a.faction == self.faction and a is not without)
        return threat > defence

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
            value = self._value(game, p, army)
            if value is None:
                continue
            if any(a.faction == self.faction and a.id != army.id and game.besieging(a) for a in game.armies_in(p.id)):
                continue  # a comrade is already starving it out
            if not self._can_take(game, army, p):
                continue
            score = value / (1 + dist[p.id])
            if score > best_score or (score == best_score and best and p.id < best):
                best, best_score = p.id, score
        return best

    def _value(self, game, p, army):
        """How much this army wants province `p`, or None if it is not a target at all."""
        me = self.faction
        pers = self.personality(game)
        targets = pers["targets"]
        if p.owner == me:
            if game.has_enemy_army(me, p.id):
                return 8.0  # enemies on our own soil
            if p.id == game.capital_of(me) and self._capital_threatened(game) and army.province != p.id:
                return 9.0  # run home
            return None
        if game.blocked(me, p.id) or game.friendly_land(me, p.id):
            return None
        if p.owner is not None and not game.at_war(me, p.owner):
            return None
        if pers["stay_near_home"] and not any(game.provinces[n].owner == me for n in p.neighbors):
            return None
        if p.special == "heart":
            # the longer a rival holds the Heart, the closer they are to a legendary victory
            return targets["heart"] + 2.0 * game.heart_turns.get(p.owner, 0)
        if p.owner and game.capital_of(p.owner) == p.id:
            # taking a Heart holder's capital also breaks their count
            return targets["enemy"] + 1.5 + 1.5 * game.heart_turns.get(p.owner, 0)
        return targets["neutral"] if p.owner is None else targets["enemy"]

    def _can_take(self, game, army, p):
        """Would `army` beat what holds province `p` (its armies, and later its garrison)?"""
        ours = game.strength(army.regiments)
        enemies = [a for a in game.armies_in(p.id) if a.faction != self.faction and game.at_war(self.faction, a.faction)]
        theirs = sum(game.strength(a.regiments) for a in enemies)
        if not game.friendly_land(self.faction, p.id) and p.garrison:
            theirs += game.strength(p.garrison) * (1.5 if p.walls else 1.0) * 0.7  # sieges wear them down
        return theirs == 0 or ours >= theirs * 1.1

    def _gather(self, game):
        """Armies that ended the turn together become one."""
        for p in game.provinces.values():
            mine = [a for a in game.armies_in(p.id) if a.faction == self.faction]
            if len(mine) > 1 and not any(game.besieging(a) for a in mine[1:]):
                game.merge(mine[0].id)

    # --- economy ---------------------------------------------------------------------------

    def _build(self, game):
        fid = self.faction
        gold = game.treasury[fid].gold
        bal = economy.balance(game, fid)
        order = list(BUILD_ORDER)
        if bal.food < 2:
            order.remove("farm")
            order.insert(0, "farm")
        own = [bid for bid, b in game.data.buildings.items() if b.get("faction") == fid]
        restless = [p for p in game.provinces_of(fid) if legends.public_order(game, p)[0] < 2]
        for bid in own:  # calm restless provinces with the faction's own building first
            for p in restless:
                if gold - game.data.buildings[bid]["cost"] >= GOLD_RESERVE and \
                        economy.building_blocker(game, fid, p.id, bid) is None:
                    game.build(fid, p.id, bid)
                    return
        order[1:1] = own
        capital = game.capital_of(fid)
        # restless provinces first, then the capital, then the richest
        provinces = sorted(game.provinces_of(fid), key=lambda p: (legends.public_order(game, p)[0] >= 1,
                                                                   p.id != capital,
                                                                   -economy.province_yield(game, p)[0], p.id))
        enemies = set(diplomacy.at_war_with(game, fid))
        for bid in order:
            if bid == "barracks":
                candidates = [p for p in provinces if p.id == capital] or provinces[:1]
            elif bid == "walls":
                if gold < WALLS_WHEN_RICHER_THAN:
                    continue
                candidates = [p for p in provinces if any(game.provinces[n].owner in enemies for n in p.neighbors)]
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
