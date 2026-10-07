"""War: declaring it, fighting it out on the map, and making peace.

Wars are fought for a goal: a province to conquer, a neighbour to make tributary, or freedom from an
overlord. Armies that meet fight a battle (resolved here; the tactical battles come later); an army
camped at an enemy town besieges it until the walls or the garrison give way. Every battle won and
every province held adds to the war score, and the score decides what peace the loser will accept.
"""

import math
from dataclasses import dataclass, field

from .calendar import Date

ENGAGE_KM = 18.0          # armies closer than this at the end of a march fight
SIEGE_KM = 15.0           # an army this close to an enemy town besieges it
TRUCE_MONTHS = 60
GARRISON_PER_FORT = 300
MILITIA_BASE = 150        # men who man an unwalled town's palisade and its church tower
MILITIA_PER_THOUSAND = 5  # and more for every thousand people of the province
ATTRITION = {"summer": 0.01, "spring": 0.015, "autumn": 0.015, "winter": 0.04}   # a month, in enemy land
HOME_WINTER_ATTRITION = 0.005
LOOTING = 0.05            # prosperity an enemy army strips from a province each month
REPLENISH = 0.08          # of the missing men a regiment gets back each month at home and at peace
GOALS = {
    "conquest": "Conquer {province}",
    "tribute": "Make {defender} pay tribute",
    "independence": "Throw off the yoke of {defender}",
}


@dataclass
class War:
    id: str
    attackers: list
    defenders: list
    goal: dict                       # {"kind": ..., "province": pid or None}
    start: Date
    battle_score: float = 0.0        # for the attackers, from battles
    ticking: float = 0.0             # for the attackers, from holding the war goal
    losses: dict = field(default_factory=dict)       # realm -> men lost
    log: list = field(default_factory=list)

    @property
    def leader(self):
        return self.attackers[0]

    @property
    def target(self):
        return self.defenders[0]

    def side(self, tag):
        if tag in self.attackers:
            return "attackers"
        if tag in self.defenders:
            return "defenders"
        return None

    def enemies(self, tag):
        side = self.side(tag)
        if side == "attackers":
            return self.defenders
        if side == "defenders":
            return self.attackers
        return []


class Warfare:
    """The wars of a campaign (it is part of Campaign: see campaign.py)."""

    # --- who is at war with whom ---------------------------------------------------------------------

    def at_war(self, a, b):
        return any(b in w.enemies(a) for w in self.wars)

    def enemies_of(self, tag):
        out = set()
        for w in self.wars:
            out.update(w.enemies(tag))
        return out

    def wars_of(self, tag):
        return [w for w in self.wars if w.side(tag)]

    def truce_with(self, a, b):
        until = self.truces.get(_pair(a, b))
        return until is not None and self.date < Date(*until)

    def war_name(self, war):
        a, d = self.info[war.leader]["adjective"], self.info[war.target]["adjective"]
        return f"The {a}-{d} War of {war.start.year}"

    # --- declaring ------------------------------------------------------------------------------

    def can_declare(self, attacker, defender, goal):
        """(True, None) or (False, the reason)."""
        if attacker == defender or not self.realms[defender].alive:
            return False, "No."
        if self.at_war(attacker, defender):
            return False, "Already at war."
        if self.truce_with(attacker, defender):
            return False, "A truce holds between us."
        lord = self.overlord.get(attacker)
        kind = goal["kind"]
        if kind == "independence":
            if not lord or lord[0] != defender:
                return False, f"We owe {self.name(defender)} nothing."
        elif lord and lord[0] == defender:
            return False, "We cannot make war on our overlord, except to be free of them."
        if kind == "conquest":
            pid = goal.get("province")
            if pid not in self.provinces or self.provinces[pid].owner != defender:
                return False, "That province is not theirs."
        if kind == "tribute" and self.overlord.get(defender):
            return False, f"{self.name(defender)} already answers to {self.name(self.overlord[defender][0])}."
        return True, None

    def declare_war(self, attacker, defender, goal):
        ok, why = self.can_declare(attacker, defender, goal)
        if not ok:
            raise ValueError(why)
        attackers, defenders = [attacker], [defender]
        # the overlord, the union partner and the sworn allies come to the defence
        for tag in self.defenders_called(defender, exclude=attacker):
            if tag not in attackers and tag not in defenders:
                defenders.append(tag)
        for tag in self.attackers_called(attacker, exclude=defenders):
            if tag not in attackers:
                attackers.append(tag)
        war = War(f"w{self._next_war}", attackers, defenders, dict(goal), self.date)
        self._next_war += 1
        self.wars.append(war)
        text = f"{self.war_name(war)}: {self.goal_text(war)}."
        war.log.append(f"{self.date}: {self.name(attacker)} declares war on {self.name(defender)}.")
        for tag in set(attackers) | set(defenders):
            self.tell(tag, text)
        return war

    def goal_text(self, war):
        return self.describe_goal(war.goal, war.target)

    def describe_goal(self, goal, target):
        province = self.static(goal["province"]).name if goal.get("province") else ""
        return GOALS[goal["kind"]].format(province=province, defender=self.name(target))

    def defenders_called(self, defender, exclude):
        """Who comes to the aid of a realm attacked: its overlord (unless that is the attacker), its
        union partner, its vassals, and its allies."""
        out = []
        lord = self.overlord.get(defender)
        if lord and lord[0] != exclude and lord[1] in ("vassal", "tributary", "protectorate", "union"):
            out.append(lord[0])
        for tag, held in self.overlord.items():
            if held and held[0] == defender and held[1] in ("vassal", "union") and tag != exclude:
                out.append(tag)
        out += [t for t in self.allies_of(defender) if t != exclude and not self.at_war(t, defender)]
        return [t for t in dict.fromkeys(out) if self.realms[t].alive]

    def attackers_called(self, attacker, exclude):
        out = [tag for tag, held in self.overlord.items()
               if held and held[0] == attacker and held[1] == "vassal" and tag not in exclude]
        return [t for t in out if self.realms[t].alive]

    def allies_of(self, tag):
        return [t for pair in self.alliances for t in pair if tag in pair and t != tag]

    # --- the war score -----------------------------------------------------------------------------

    def value(self, pid):
        return sum(self.income(pid)) + 5.0

    def occupation_score(self, war):
        """From the attackers' side: the share of each side's land the other holds."""
        def held_share(victims, takers):
            total = held = 0.0
            for p in self.provinces.values():
                if p.owner in victims:
                    v = self.value(p.id)
                    total += v
                    if p.controller in takers:
                        held += v
            return held / total if total else 0.0
        return 75.0 * (held_share(war.defenders, war.attackers) - held_share(war.attackers, war.defenders))

    def score(self, war):
        """-100 (the defenders have won everything) .. 100 (the attackers have)."""
        return max(-100.0, min(100.0, war.battle_score + war.ticking + self.occupation_score(war)))

    def exhaustion(self, war, tag):
        """How tired of the war a realm is: its months of war and the men it lost."""
        months = self.date.months_since(war.start)
        pool = max(1000.0, self.levy_pool(tag))
        return min(50.0, months * 0.5 + 60.0 * war.losses.get(tag, 0) / pool)

    # --- peace ------------------------------------------------------------------------------------

    def peace_cost(self, war, terms, loser):
        """The war score a peace costs the side that gives in."""
        cost = 0.0
        total = sum(self.value(p.id) for p in self.provinces_of(loser)) or 1.0
        for pid in terms.get("provinces", []):
            cost += 8.0 + 120.0 * self.value(pid) / total
        if terms.get("tribute"):
            cost += 40.0
        if terms.get("independence"):
            cost += 40.0
        gold = terms.get("gold", 0)
        if gold:
            cost += 20.0 * gold / max(200.0, 12 * self.budget(loser).income)
        return cost

    def would_accept(self, war, terms, by):
        """Would the realm `by` (leading its side) sign this peace?"""
        side = war.side(by)
        score = self.score(war) if side == "attackers" else -self.score(war)
        # score > 0 means `by` is winning; terms that take from `by` cost it
        taken = self.peace_cost(war, terms, by) if terms.get("loser") == by else 0.0
        given = self.peace_cost(war, terms, terms["loser"]) if terms.get("loser") not in (None, by) else 0.0
        tired = self.exhaustion(war, by)
        if taken:
            return -score + tired >= taken
        # a peace in our favour or a white peace: take it unless we are winning by more than it gives
        return score - given <= 10.0 + tired * 0.5

    def make_peace(self, war, terms):
        """End the war on these terms: {"loser": tag, "provinces": [...], "tribute": bool,
        "independence": bool, "gold": ducats}."""
        loser = terms.get("loser")
        winner = None
        if loser:
            winner = war.target if loser in war.attackers else war.leader
        for pid in terms.get("provinces", []):
            p = self.provinces[pid]
            if p.owner == loser:
                p.owner = p.controller = winner
                p.works, p.recruits = None, []
        if terms.get("tribute") and loser:
            self.overlord[loser] = (winner, "tributary")
        if terms.get("independence") and loser:
            self.overlord[winner] = None
        gold = min(terms.get("gold", 0), max(0.0, self.realms[loser].treasury)) if loser else 0
        if gold:
            self.realms[loser].treasury -= gold
            self.realms[winner].treasury += gold
        sides = set(war.attackers) | set(war.defenders)
        for p in self.provinces.values():   # the armies go home, the occupied land goes back
            if p.owner in sides and p.controller != p.owner and p.controller in sides:
                p.controller = p.owner
            p.siege = None if p.siege and p.siege.get("by") in sides else p.siege
        until = self.date
        for _ in range(TRUCE_MONTHS):
            until = until.next()
        for a in war.attackers:
            for d in war.defenders:
                self.truces[_pair(a, d)] = [until.year, until.month]
        self.wars.remove(war)
        self.borders_changed()
        for a in war.attackers:
            for d in war.defenders:
                self.nudge(a, d, -15 if loser else 0)
        text = f"Peace: {self.war_name(war)} is over. {self.peace_text(war, terms)}"
        for tag in sides:
            self.tell(tag, text)
        for tag in list(sides):
            self._check_alive(tag)
        return text

    def peace_text(self, war, terms):
        loser = terms.get("loser")
        if not loser:
            return "Neither side gains anything."
        winner = war.target if loser in war.attackers else war.leader
        parts = []
        if terms.get("provinces"):
            parts.append(f"{self.name(loser)} cedes " +
                         ", ".join(self.static(p).name for p in terms["provinces"]) + f" to {self.name(winner)}")
        if terms.get("tribute"):
            parts.append(f"{self.name(loser)} will pay tribute to {self.name(winner)}")
        if terms.get("independence"):
            parts.append(f"{self.name(winner)} is free of {self.name(loser)}")
        if terms.get("gold"):
            parts.append(f"{self.name(loser)} pays {terms['gold']:,} ducats")
        return "; ".join(parts) + "."

    def _check_alive(self, tag):
        realm = self.realms[tag]
        if realm.alive and not self.provinces_of(tag):
            realm.alive = False
            self.armies = [a for a in self.armies if a.owner != tag]
            for w in list(self.wars):
                for side in (w.attackers, w.defenders):
                    if tag in side:
                        side.remove(tag)
                if not w.attackers or not w.defenders:
                    self.wars.remove(w)
            for t, held in list(self.overlord.items()):
                if held and held[0] == tag:
                    self.overlord[t] = None
            self.tell(self.player, f"{self.info[tag]['name']} is no more.")

    # --- the fighting, at the end of every month -------------------------------------------------

    def war_month(self):
        self._battles()
        self._sieges()
        self._attrition_and_looting()
        for war in self.wars:
            pid = war.goal.get("province")
            if pid and self.provinces[pid].controller in war.attackers:
                war.ticking = min(25.0, war.ticking + 1.0)

    def hostile(self, a, b):
        return a != b and self.at_war(a, b)

    def hostile_near(self, army):
        """An enemy army close enough to fight this one, if any."""
        best, near = None, ENGAGE_KM
        for other in self.armies:
            if other is not army and self.hostile(army.owner, other.owner):
                d = math.hypot(army.x - other.x, army.y - other.y) * 1.5
                if d <= near:
                    best, near = other, d
        return best

    def _battles(self):
        fought = set()
        for a in list(self.armies):
            for b in list(self.armies):
                if a is b or id(a) in fought or id(b) in fought or not self.hostile(a.owner, b.owner):
                    continue
                if a not in self.armies or b not in self.armies:
                    continue
                if math.hypot(a.x - b.x, a.y - b.y) * 1.5 <= ENGAGE_KM:
                    if getattr(self, "interactive_battles", False) and self.player in (a.owner, b.owner):
                        self.pending_battles.append((a.id, b.id))   # the player will choose how to fight
                    else:
                        self.battle(a, b)
                    fought.update((id(a), id(b)))

    def strength(self, army, terrain, defending):
        total = 0.0
        for r in army.regiments:
            u = r.type
            power = u.melee + 0.8 * u.missile + 0.5 * u.defence
            if u.kind == "horse":
                power *= {"plains": 1.15, "steppe": 1.2, "forest": 0.8, "mountains": 0.7, "marsh": 0.75,
                          "hills": 0.9}.get(terrain, 1.0)
            elif defending and terrain in ("hills", "mountains", "forest"):
                power *= 1.2
            total += r.men / 100.0 * power * (0.5 + u.morale / 20.0) * (1 + 0.5 * r.experience)
        return total * self.leadership(army)

    def battle_site(self, attacker, defender):
        """(province or None, its terrain, its name) where two armies meet."""
        prov = self.provmap.at((attacker.x + defender.x) / 2, (attacker.y + defender.y) / 2) or \
            self.provmap.at(defender.x, defender.y)
        return prov, (prov.terrain if prov else "plains"), (prov.name if prov else "the field")

    def battle(self, attacker, defender):
        """Fight it out, resolved by the captains. Returns a report: {"winner", "loser", "place",
        "losses": {realm: men}}."""
        _, terrain, _ = self.battle_site(attacker, defender)
        sa = self.strength(attacker, terrain, False) * self.rng.uniform(0.8, 1.2)
        sd = self.strength(defender, terrain, True) * self.rng.uniform(0.8, 1.2)
        win = attacker if sa >= sd else defender
        ratio = max(sa, sd) / max(1e-6, min(sa, sd))
        lose_share = min(0.6, 0.2 + 0.12 * ratio) * self.rng.uniform(0.85, 1.15)
        win_share = max(0.04, 0.22 / ratio) * self.rng.uniform(0.8, 1.2)
        after = {}
        for army in (attacker, defender):
            share = win_share if army is win else lose_share
            after[army.id] = [r.men - int(r.men * share) for r in army.regiments]
        return self.conclude_battle(attacker, defender, win, after)

    def conclude_battle(self, attacker, defender, winner, after):
        """Apply a battle's outcome, however it was fought: `after` gives, for each army, the men left in
        each of its regiments."""
        _, terrain, place = self.battle_site(attacker, defender)
        win, lose = (winner, defender if winner is attacker else attacker)
        losses = {}
        for army in (win, lose):
            lost = 0
            for r, left in zip(army.regiments, after[army.id]):
                left = max(0, min(r.men, int(left)))
                lost += r.men - left
                r.men = left
                r.experience = min(1.0, r.experience + (0.15 if army is win else 0.05))
            army.regiments = [r for r in army.regiments if r.men >= 50]
            losses[army.id] = lost
        self.after_battle(win, lose)
        report = {"winner": win.owner, "loser": lose.owner, "place": place, "terrain": terrain,
                  "losses": {win.owner: losses[win.id], lose.owner: losses[lose.id]},
                  "armies": (win.name, lose.name)}
        for war in self.wars:
            if lose.owner in war.enemies(win.owner):
                points = max(2.0, min(20.0, 2.0 + losses[lose.id] / 400.0))
                war.battle_score += points if war.side(win.owner) == "attackers" else -points
                war.battle_score = max(-40.0, min(40.0, war.battle_score))
                for tag, men in report["losses"].items():
                    war.losses[tag] = war.losses.get(tag, 0) + men
                war.log.append(f"{self.date}: battle of {place}, won by {self.name(win.owner)}.")
        text = (f"Battle of {place}: the {win.name} defeats the {lose.name}. Losses: "
                f"{losses[win.id]:,} against {losses[lose.id]:,}.")
        self.tell(win.owner, text)
        self.tell(lose.owner, text)
        self.battles.append(report)
        if not lose.regiments:
            self.armies.remove(lose)
            self.tell(lose.owner, f"The {lose.name} is destroyed.")
        else:
            self._retreat(lose, win)
        if not win.regiments:
            self.armies.remove(win)
        return report

    def _retreat(self, army, enemy):
        """The beaten army falls back, away from the victor, towards its own land."""
        army.route = None
        dx, dy = army.x - enemy.x, army.y - enemy.y
        d = math.hypot(dx, dy) or 1.0
        for dist in (25, 18, 12, 8):
            x, y = army.x + dx / d * dist, army.y + dy / d * dist
            prov = self.provmap.at(x, y)
            if prov is not None:
                army.x, army.y = x, y
                break
        army.moves = 0.0

    def garrison(self, pid):
        """The men defending the town: the fortress's garrison, the castle's, and the townsfolk and
        villagers who take up arms when an enemy comes."""
        militia = MILITIA_BASE + MILITIA_PER_THOUSAND * self.provinces[pid].population
        return self.fort(pid) * GARRISON_PER_FORT + self.effect(pid, "garrison") + militia

    def _sieges(self):
        """Armies stopped at enemy towns besiege them, allies together; the town falls when the siege is
        done (an unwalled town in a month or two, a great fortress in a year or more)."""
        camps = {}
        for army in self.armies:
            prov = self.provmap.at(army.x, army.y)
            if prov is None or army.route is not None:
                continue   # only an army that has stopped at the town besieges it
            p = self.provinces[prov.id]
            if not self.hostile(army.owner, p.controller):
                continue
            tx, ty = prov.town
            if math.hypot(army.x - tx, army.y - ty) * 1.5 > SIEGE_KM:
                continue
            camps.setdefault(prov.id, []).append(army)
        for pid, armies in camps.items():
            p, info = self.provinces[pid], self.static(pid)
            # the side already besieging keeps the siege; others of that side join it
            lead = next((a for a in armies if p.siege and (a.owner == p.siege["by"] or
                                                           not self.hostile(a.owner, p.siege["by"]))), armies[0])
            side = [a for a in armies if a.owner == lead.owner or not self.hostile(a.owner, lead.owner)]
            men = sum(a.men for a in side)
            garrison = self.garrison(pid)
            if men < 2 * garrison:
                continue   # too few to close the town in
            fort = self.fort(pid)
            if not p.siege or p.siege["by"] != lead.owner and self.hostile(p.siege["by"], lead.owner):
                p.siege = {"by": lead.owner, "progress": 0.0, "months": 0}
                self.tell(p.controller, f"{info.name} is besieged by the {lead.name}.")
                self.tell(lead.owner, f"The {lead.name} lays siege to {info.name}.")
            winter = 0.5 if self.date.season == "winter" else 1.0
            might = min(2.0, men / (4.0 * garrison))
            p.siege["progress"] += (0.6 + 0.4 * might) * winter / (1.0 + 1.5 * fort) * self.rng.uniform(0.7, 1.3)
            p.siege["months"] += 1
            if p.siege["progress"] >= 1.0:
                self._occupy(p, lead.owner)
        for p in self.provinces.values():
            if p.siege and p.id not in camps:
                p.siege = None

    def _occupy(self, p, tag):
        info = self.static(p.id)
        before = p.controller
        p.controller = tag if p.owner != tag else p.owner
        p.siege = None
        p.recruits = []
        p.prosperity = max(0.3, p.prosperity - 0.1)
        text = f"{info.name} falls to {self.name(tag)}." if p.owner != tag else \
            f"{info.name} is retaken by {self.name(tag)}."
        self.tell(tag, text)
        if before != tag:
            self.tell(before, text)
        for w in self.wars:
            if before in w.enemies(tag):
                w.log.append(f"{self.date}: {text}")

    def _attrition_and_looting(self):
        season = self.date.season
        for army in list(self.armies):
            prov = self.provmap.at(army.x, army.y)
            own = prov is not None and self.provinces[prov.id].controller == army.owner
            friendly = prov is not None and (own or self.provinces[prov.id].owner in self.allies_of(army.owner))
            if not friendly:
                rate = ATTRITION[season] + (0.01 if prov and prov.terrain in ("mountains", "marsh", "desert") else 0)
            else:
                rate = HOME_WINTER_ATTRITION if season == "winter" else 0.0
            if rate:
                for r in army.regiments:
                    r.men = int(r.men * (1 - rate))
                army.regiments = [r for r in army.regiments if r.men >= 50]
            elif own and not self.wars_of(army.owner):
                realm = self.realms[army.owner]
                for r in army.regiments:
                    missing = r.type.men - r.men
                    back = min(int(missing * REPLENISH + 0.999), int(realm.manpower))
                    if back > 0:
                        r.men += back
                        realm.manpower -= back
            if not army.regiments:
                self.armies.remove(army)
                continue
            if prov is not None and self.hostile(army.owner, self.provinces[prov.id].owner):
                p = self.provinces[prov.id]
                p.prosperity = max(0.2, p.prosperity - LOOTING)


def _pair(a, b):
    return "|".join(sorted((a, b)))


def war_from_dict(d):
    return War(d["id"], d["attackers"], d["defenders"], d["goal"], Date(*d["start"]), d["battle_score"],
               d["ticking"], d["losses"], d["log"])


def war_to_dict(w):
    return {"id": w.id, "attackers": w.attackers, "defenders": w.defenders, "goal": w.goal,
            "start": [w.start.year, w.start.month], "battle_score": w.battle_score, "ticking": w.ticking,
            "losses": w.losses, "log": w.log}

