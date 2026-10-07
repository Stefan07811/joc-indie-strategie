"""The realms the player does not rule: what they build, raise, declare and march on each month.

Each AI realm keeps a reserve, spends on the building that pays best, keeps an army its income can
bear (more in war), looks for weak neighbours to fight, makes peace when the war score says it should,
and moves its armies to besiege enemy towns, to fight weaker enemy armies, or home again.
"""

import math

from .rules import BUILDINGS

# How eager a realm is to start wars (a month's chance is about 2% times this).
AGGRESSION = {"ott_rum": 2.0, "ott_isa": 2.0, "ott_meh": 2.0, "timurids": 1.5, "karaman": 1.8, "horde": 1.5,
              "hungary": 1.2, "venice": 0.8, "genoa": 0.4, "ragusa": 0.1, "papal": 0.3, "knights": 0.3,
              "aquileia": 0.2, "salzburg": 0.2, "byzantium": 0.4, "theodoro": 0.3}
WAR_CHANCE = 0.035
MIN_RATIO = 1.6           # how much stronger than the defence a realm wants to be before it attacks
ROUTES_PER_MONTH = 40     # the AI's marching orders are expensive to work out: this many a month at most


class AI:
    def __init__(self, campaign, nav):
        self.c = campaign
        self.land_nav = nav
        self.routes = 0

    def month(self):
        """Every AI realm takes its decisions for the month (before the month is closed)."""
        c = self.c
        self.routes = 0
        tags = [t for t in c.realms if c.realms[t].alive and t != c.player]
        self.budgets = {t: c.budget(t) for t in tags}
        c.rng.shuffle(tags)
        for tag in tags:
            self.make_peace(tag)
        for tag in tags:
            self.build(tag)
            for _ in range(3 if c.wars_of(tag) else 2):   # a rich realm raises more than a regiment a month
                self.recruit(tag)
            self.go_to_war(tag)
        for tag in tags:
            self.merge(tag)
            self.move_armies(tag)

    # --- money ------------------------------------------------------------------------------------

    def reserve(self, tag):
        return 3 * max(0.0, self.budgets[tag].expenses)

    def build(self, tag):
        """Spend what is above the reserve on the buildings that pay best, one work per province."""
        c = self.c
        realm = c.realms[tag]
        spare = realm.treasury - self.reserve(tag)
        if spare < 300:
            return
        options = []
        for p in c.provinces_of(tag):
            if p.works or p.controller != tag:
                continue
            for kind in BUILDINGS:
                check = c.can_build(p.id, kind)
                if check[0] and check[1] <= spare:
                    options.append((self._building_value(p.id, kind) / check[1], p.id, kind, check[1]))
        options.sort(reverse=True)
        busy = set()
        for value, pid, kind, cost in options:
            if value <= 0 or pid in busy or cost > realm.treasury - self.reserve(tag):
                continue
            if c.build(pid, kind):
                busy.add(pid)
            if len(busy) >= 6:
                break

    def _building_value(self, pid, kind):
        """Ducats a month the next level would bring (or what it is judged to be worth)."""
        c = self.c
        p = c.provinces[pid]
        level = p.buildings.get(kind, 0)
        before = sum(c.income(pid))
        p.buildings[kind] = level + 1
        after = sum(c.income(pid))
        if level == 0:
            del p.buildings[kind]
        else:
            p.buildings[kind] = level
        gain = after - before
        if kind == "walls":
            danger = sum(1 for n in c.static(pid).neighbors if c.provinces[n].owner in c.enemies_of(p.owner)
                         or c.opinion(p.owner, c.provinces[n].owner) < -20)
            gain += 15.0 * danger * (2 if pid == c.capital(p.owner) else 1)
        elif kind == "castle":
            gain += 25.0 if pid == c.capital(p.owner) else 4.0
        elif kind == "church":
            gain += 3.0 * p.unrest + 2.0
        elif kind == "stables":
            gain += 6.0 if pid == c.capital(p.owner) else 1.0
        return gain

    def recruit(self, tag):
        c = self.c
        realm = c.realms[tag]
        b = self.budgets[tag]
        at_war = bool(c.wars_of(tag))
        target = b.income * (0.85 if at_war else 0.5)
        if b.armies >= target or realm.treasury < self.reserve(tag) * (0.5 if at_war else 1.0):
            return
        places = [c.capital(tag)] + [p.id for p in c.provinces_of(tag) if p.buildings.get("castle")]
        options = c.units_for(tag)
        for pid in dict.fromkeys(p for p in places if p):
            affordable = [u for u in options if c.can_recruit(pid, u.id)[0]
                          and b.armies + u.upkeep <= target]
            if not affordable:
                continue
            # a mix: horse and foot, the best the realm can raise
            horse = sum(1 for a in c.armies_of(tag) for r in a.regiments if r.type.kind == "horse")
            foot = sum(1 for a in c.armies_of(tag) for r in a.regiments if r.type.kind != "horse")
            want = "horse" if horse < foot * 0.6 else None
            pool = [u for u in affordable if (want is None or u.kind == want)] or affordable
            unit = max(pool, key=lambda u: (u.melee + u.missile + u.defence) * u.men / max(1, u.upkeep) *
                       (1.0 + 0.3 * c.rng.random()))
            c.recruit(pid, unit.id)
            return

    # --- war and peace ---------------------------------------------------------------------------

    def go_to_war(self, tag):
        c = self.c
        from .campaign import DIFFICULTY
        war = DIFFICULTY[c.difficulty]["war"]
        if c.wars_of(tag) or c.rng.random() > WAR_CHANCE * AGGRESSION.get(tag, 1.0) * c.aggression(tag) * war:
            return
        if c.date.months_since(c.start_date) < 3:
            return   # the first months belong to the player
        me = c.military_power(tag)
        lord = c.overlord.get(tag)
        candidates = []
        if lord and lord[0] in c.realms and c.realms[lord[0]].alive:
            if c.wars_of(lord[0]) and me > MIN_RATIO * c.coalition_power(lord[0], tag) * 0.6:
                candidates.append((2.0, lord[0], {"kind": "independence"}))
        for other in c.neighbours.get(tag, ()):
            if not c.realms[other].alive or (lord and other == lord[0]):
                continue
            held = c.overlord.get(other)
            if held and held[0] == tag and c.opinion(tag, other) > -40:
                continue   # our own vassals pay us; we do not burn their villages
            if c.opinion(tag, other) > 10 or c.truce_with(tag, other) or sorted((tag, other)) in c.alliances:
                continue
            ratio = me / max(1.0, c.coalition_power(other, tag))
            # a realm we do not hate must be much weaker to tempt us
            if ratio < (MIN_RATIO if c.opinion(tag, other) < -10 else 2 * MIN_RATIO):
                continue
            target = self._border_province(tag, other)
            if target is None:
                continue
            goal = {"kind": "conquest", "province": target}
            if ratio > 4 and not c.overlord.get(other) and len(c.provinces_of(other)) <= 3:
                goal = {"kind": "tribute"}
            candidates.append((ratio - c.opinion(tag, other) / 50.0, other, goal))
        if not candidates:
            return
        _, other, goal = max(candidates, key=lambda x: x[0])
        if c.can_declare(tag, other, goal)[0]:
            c.declare_war(tag, other, goal)

    def _border_province(self, tag, other):
        """The richest province of `other` that touches our land."""
        c = self.c
        best, value = None, 0.0
        for p in c.provinces_of(other):
            if any(c.provinces[n].owner == tag for n in c.static(p.id).neighbors):
                v = c.value(p.id)
                if v > value:
                    best, value = p.id, v
        return best

    def make_peace(self, tag):
        c = self.c
        for war in list(c.wars):
            if tag not in (war.leader, war.target) or war not in c.wars:
                continue
            if c.date.months_since(war.start) < 4:
                continue
            other = war.target if tag == war.leader else war.leader
            score = c.score(war) if tag == war.leader else -c.score(war)
            if score >= 15:
                terms = self.demands(war, tag, other, score)
                if terms and not terms.get("provinces") and war.goal["kind"] == "conquest" and \
                        c.date.months_since(war.start) < 24 and c.exhaustion(war, tag) < 25:
                    continue      # we came for land, not for silver: keep at the sieges
            elif score <= -25 or c.exhaustion(war, tag) > 30:
                terms = self.concessions(war, tag, other, -score)
            else:
                continue
            if terms is None:
                continue
            if other == c.player:
                c.propose_peace(tag, war, terms)
            elif c.would_accept(war, terms, other):
                c.make_peace(war, terms)
                c.borders_changed()

    def demands(self, war, winner, loser, score):
        """The most a winning side can ask for its score."""
        c = self.c
        terms = {"loser": loser, "provinces": []}
        mine = set(war.attackers if war.side(winner) == "attackers" else war.defenders)
        goal = war.goal
        if goal["kind"] == "tribute" and war.side(winner) == "attackers":
            if c.peace_cost(war, {"loser": loser, "tribute": True}, loser) <= score:
                return {"loser": loser, "tribute": True}
        if goal["kind"] == "independence" and war.side(winner) == "attackers":
            if c.peace_cost(war, {"loser": loser, "independence": True}, loser) <= score:
                return {"loser": loser, "independence": True}
        held = sorted((p for p in c.provinces_of(loser) if p.controller in mine),
                      key=lambda p: (p.id != goal.get("province"), -c.value(p.id)))
        for p in held:
            trial = dict(terms, provinces=terms["provinces"] + [p.id])
            if c.peace_cost(war, trial, loser) <= score:
                terms = trial
        if not terms["provinces"]:
            gold = int(min(c.realms[loser].treasury, 6 * c.budget(loser).income) / 100) * 100
            if gold <= 0:
                return {"loser": None}
            terms = {"loser": loser, "gold": gold}
        return terms

    def concessions(self, war, loser, winner, deficit):
        """What a losing side offers to end it: the war goal, or a white peace if it is not losing badly."""
        c = self.c
        if deficit < 25:
            return {"loser": None}
        goal = war.goal
        if war.side(loser) == "defenders":
            if goal["kind"] == "conquest" and c.provinces[goal["province"]].owner == loser:
                return {"loser": loser, "provinces": [goal["province"]]}
            if goal["kind"] == "tribute":
                return {"loser": loser, "tribute": True}
            if goal["kind"] == "independence":
                return {"loser": loser, "independence": True}
        gold = int(min(c.realms[loser].treasury, 3 * c.budget(loser).income) / 100) * 100
        return {"loser": loser, "gold": gold} if gold > 0 else {"loser": None}

    # --- armies -----------------------------------------------------------------------------------

    def merge(self, tag):
        c = self.c
        armies = c.armies_of(tag)
        for i, a in enumerate(armies):
            for b in armies[i + 1:]:
                if a in c.armies and b in c.armies and a.route is None and b.route is None and \
                        math.hypot(a.x - b.x, a.y - b.y) < 6:
                    a.regiments += b.regiments
                    a.march = min(a.march, b.march)
                    c.armies.remove(b)

    def nav(self, army):
        return self.c.nav_for(army)

    def order(self, army, x, y):
        if self.routes >= ROUTES_PER_MONTH:
            return False
        self.routes += 1
        return army.order(self.nav(army), x, y, greed=1.4)

    def move_armies(self, tag):
        c = self.c
        enemies = c.enemies_of(tag)
        for army in c.armies_of(tag):
            if not enemies:
                self._go_home(army)
                continue
            if army.route is not None and self._still_worth_it(army, enemies):
                continue
            army.route = None
            mine = c.strength(army, "plains", False)
            # 1. a weaker enemy army within a month's march: go and fight it
            prey = [e for e in c.armies if e.owner in enemies and
                    math.hypot(e.x - army.x, e.y - army.y) * 1.5 < army.march * 0.9 and
                    c.strength(e, "plains", True) * 1.3 < mine]
            prey = [e for e in prey if self.nav(army).connected(army.x, army.y, e.x, e.y)]
            if prey:
                e = min(prey, key=lambda e: math.hypot(e.x - army.x, e.y - army.y))
                self.order(army, e.x, e.y)
                continue
            # 2. a stronger enemy army close by: fall back to the nearest of our fortified towns
            danger = [e for e in c.armies if e.owner in enemies and
                      math.hypot(e.x - army.x, e.y - army.y) * 1.5 < 120 and
                      c.strength(e, "plains", False) > mine * 1.2]
            if danger:
                home = self._nearest_town(army, lambda p: p.owner == tag and p.controller == tag and
                                          c.fort(p.id) > 0)
                if home and math.hypot(home.town[0] - army.x, home.town[1] - army.y) > 4:
                    self.order(army, *home.town)
                continue
            # 3. besiege: our land the enemy holds first, then the war goal, then the nearest enemy town
            target = self._siege_target(army, tag, enemies)
            if target is not None:
                tx, ty = c.static(target).town
                if math.hypot(tx - army.x, ty - army.y) > 3:
                    self.order(army, tx, ty)

    def _still_worth_it(self, army, enemies):
        """Keep marching unless the town we marched on is no longer the enemy's."""
        c = self.c
        prov = c.provmap.at(*army.route.end)
        if prov is None:
            return False
        holder = c.provinces[prov.id].controller
        return holder in enemies or any(e.owner in enemies and math.hypot(e.x - army.route.end[0],
                                                                          e.y - army.route.end[1]) < 10
                                        for e in c.armies)

    def _siege_target(self, army, tag, enemies):
        c = self.c
        goals = {w.goal.get("province") for w in c.wars_of(tag)}
        best, best_score = None, -math.inf
        for p in c.provinces.values():
            if p.controller not in enemies:
                continue
            info = c.static(p.id)
            d = math.hypot(info.town[0] - army.x, info.town[1] - army.y) * 1.5
            if d > army.march * 3:
                continue
            score = -d / army.march - 0.6 * c.fort(p.id)
            if p.owner == tag:
                score += 3.0
            if p.id in goals:
                score += 2.0
            if army.men < 2 * c.garrison(p.id) or not self.nav(army).connected(army.x, army.y, *info.town):
                continue
            # other armies of ours already besieging it
            if any(a is not army and a.owner == tag and math.hypot(a.x - info.town[0], a.y - info.town[1]) < 8
                   for a in c.armies):
                score -= 2.0
            if score > best_score:
                best, best_score = p.id, score
        return best

    def _nearest_town(self, army, keep):
        c = self.c
        best, dist = None, math.inf
        for p in c.provinces.values():
            if keep(p):
                info = c.static(p.id)
                d = math.hypot(info.town[0] - army.x, info.town[1] - army.y)
                if d < dist:
                    best, dist = info, d
        return best

    def _go_home(self, army):
        c = self.c
        if army.route is not None:
            return
        cap = c.capital(army.owner)
        if cap is None:
            return
        tx, ty = c.static(cap).town
        if math.hypot(tx - army.x, ty - army.y) > 8 and self.nav(army).connected(army.x, army.y, tx, ty):
            self.order(army, tx, ty)

