"""The campaign: the state of the world month by month, and the rules that move it on.

Everything here is plain data and arithmetic, with no graphics, so it can be tested, saved and run by
the AI. A turn is a month: taxes come in, troops are paid, works go on, people are born and die, the
armies march.
"""

import copy
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Optional

from . import rules
from .armies import Army, Regiment
from .calendar import START, Date
from .navigation import Route
from .rules import BUILDINGS, UNITS
from .diplomacy import Diplomacy
from .history import Chronicles
from .people import Court
from .war import Warfare, war_from_dict, war_to_dict

TRIBUTE = {"tributary": 0.10, "vassal": 0.15, "protectorate": 0.05, "union": 0.0}
# Some realms fight in another tradition than their culture's.
REALM_TRADITION = {"timurids": "steppe", "horde": "steppe", "mamluks": "levant", "akkoyunlu": "steppe"}
# The field armies of September 1402, by rank, as unit lists cycled through to the army's size.
ARMY_SIZE = {"empire": 20, "kingdom": 14, "duchy": 8, "county": 3}
TEMPLATES = {
    "latin": ["knights", "crossbowmen", "men_at_arms", "light_horse", "militia", "crossbowmen", "knights",
              "militia"],
    "vlach": ["boyars", "calarasi", "vlach_archers", "great_host", "calarasi", "great_host", "boyars"],
    "balkan": ["vlastela", "bowmen", "spearmen", "stradioti", "spearmen", "bowmen", "vlastela"],
    "greek": ["archontes", "greek_archers", "militia_greek", "stratiotai", "militia_greek", "greek_archers"],
    "ottoman": ["sipahis", "azaps", "akinjis", "sipahis", "janissaries", "azaps", "akinjis", "sipahis"],
    "steppe": ["horse_archers", "horse_archers", "mirza_horse", "horse_archers", "horse_archers", "mirza_horse"],
    "levant": ["mamluks", "kurdish_horse", "levant_foot", "mamluks", "kurdish_horse", "levant_foot"],
}
# Ducats a month from a realm's lands beyond the edge of the map: Egypt, Persia and Transoxiana, the
# Volga, Genoa itself, northern Poland and Lithuania, eastern Georgia.
BEYOND_THE_MAP = {"mamluks": 9000, "timurids": 8000, "horde": 2500, "genoa": 2200, "poland": 3500,
                  "lithuania": 3000, "georgia": 700, "akkoyunlu": 500,
                  "knights": 900}     # the Knights' priories all over Christendom send their dues
ARMY_SHARE = 0.45     # of its income a realm spends on the army it starts with
# Realms with fleets to carry their armies over the sea (any realm with a harbour gets them too).
NAVAL_REALMS = {"venice", "genoa", "knights", "cyprus", "naxos", "lesbos", "byzantium", "ott_rum", "ott_isa",
                "ott_meh", "mamluks", "naples", "sicily", "ragusa", "tocco", "trebizond", "aydin", "mentese"}
HOARD_MONTHS = 12     # a treasury above this many months of income is spent on the court's splendour
LARGESSE = 0.08       # of the hoard above that, each month
# Armies in the field in September 1402 that do not stand at their realm's capital.
FIELD_ARMIES = {
    # Timur's host wintered in western Anatolia after Ankara and the sack of Bursa
    "timurids": ("kutahya", 24, "The Host of Timur"),
}


@dataclass
class ProvinceState:
    id: str
    owner: str
    controller: str                      # who holds it now: an occupier, in war
    population: float                    # thousands
    prosperity: float = 1.0              # 0 .. 1: war, plague and famine lower it
    unrest: float = 0.0
    buildings: dict = field(default_factory=dict)       # building id -> level
    works: Optional[dict] = None         # {"kind": building id, "months": left}
    recruits: list = field(default_factory=list)        # unit ids, ready next month
    siege: Optional[dict] = None         # {"by": realm, "progress": 0 .. 1, "months": n}


@dataclass
class RealmState:
    tag: str
    treasury: float
    manpower: float                      # men who can still be called to arms
    prestige: float = 0.0
    alive: bool = True


@dataclass
class Budget:
    tax: float = 0.0
    production: float = 0.0
    commerce: float = 0.0
    tribute_in: float = 0.0
    beyond: float = 0.0                  # from lands beyond the edge of the map
    court: float = 0.0
    armies: float = 0.0
    forts: float = 0.0
    tribute_out: float = 0.0

    @property
    def income(self):
        return self.tax + self.production + self.commerce + self.tribute_in + self.beyond

    @property
    def expenses(self):
        return self.court + self.armies + self.forts + self.tribute_out

    @property
    def balance(self):
        return self.income - self.expenses


class Campaign(Warfare, Diplomacy, Court, Chronicles):
    def __init__(self, provmap, realms, relations=(), player="wallachia", date=START, seed=1402, armies=True):
        self.provmap = provmap
        self.info = copy.deepcopy(realms)  # the realms' history (crowns/data/realms.json), as it changes
        self.relations = list(relations)
        self.player = player
        self.date = date
        self.start_date = date
        self.ai = None
        self.proposals = []                # offers to the player waiting for an answer
        self.interactive_battles = False   # the player's battles wait for the player (in the game itself)
        self.pending_battles = []          # (army id, army id) met this month, for the player to fight
        self.rng = random.Random(seed)
        self.provinces = {p.id: ProvinceState(p.id, p.owner, p.owner, p.population)
                          for p in provmap.provinces.values()}
        self.overlord = {tag: (r["overlord"]["tag"], r["overlord"]["kind"]) if r.get("overlord") else None
                         for tag, r in realms.items()}
        self.realms = {tag: RealmState(tag, 0.0, 0.0) for tag in realms}
        self.armies = []
        self.messages = []                 # what happened this month, for the player
        self._next_army = 1
        self.wars = []
        self.truces = {}                   # "a|b" -> [year, month] the truce lasts until
        self.alliances = [sorted(r["tags"]) for r in self.relations if r["kind"] == "alliance"]
        self.battles = []                  # this month's battle reports
        self._next_war = 1
        self.history = []                  # [date, text] of the great events: deaths, successions
        self.marriages = []                # pairs of realms whose houses have married
        self._init_history(BEYOND_THE_MAP)
        self._init_people()
        for tag, realm in self.realms.items():
            realm.manpower = 0.6 * self.levy_pool(tag)
            realm.treasury = round(max(300.0, 2 * self.budget(tag).income), -1)
        if armies:
            self._first_armies()
            self.appoint_commanders()
        self._init_diplomacy()

    def attach_ai(self, nav, naval=None):
        """Let the AI rule every realm but the player's (it needs the map's navigation to march)."""
        from .ai import AI
        self.nav = nav
        if naval is not None:
            self.naval_nav = naval
        self.ai = AI(self, nav)
        return self.ai

    def naval(self, tag):
        """Has the realm ships to carry its armies?"""
        return tag in NAVAL_REALMS or any(p.buildings.get("harbour") for p in self.provinces_of(tag))

    def nav_for(self, army):
        """The navigation an army marches (and sails) by."""
        naval = getattr(self, "naval_nav", None)
        if naval is not None and self.naval(army.owner):
            return naval
        return self.nav

    # --- lookups ----------------------------------------------------------------------------------

    def static(self, pid):
        return self.provmap.provinces[pid]

    def provinces_of(self, tag):
        return [p for p in self.provinces.values() if p.owner == tag]

    def capital(self, tag):
        cap = self.info[tag]["capital"]
        return cap if self.provinces[cap].owner == tag else next((p.id for p in self.provinces_of(tag)), None)

    def tradition(self, tag):
        return REALM_TRADITION.get(tag) or rules.TRADITION.get(self.info[tag]["culture"], "latin")

    def units_for(self, tag):
        tradition = self.tradition(tag)
        return [u for u in UNITS.values() if u.tradition == tradition]

    def armies_of(self, tag):
        return [a for a in self.armies if a.owner == tag]

    def name(self, tag):
        return self.info[tag]["short"]

    # --- what a province is worth ----------------------------------------------------------------

    def effect(self, pid, name):
        """The sum of one effect of every building in the province."""
        total = 0.0
        for kind, level in self.provinces[pid].buildings.items():
            total += BUILDINGS[kind].effects.get(name, 0.0) * level
        return total

    def fort(self, pid):
        return self.static(pid).fort + int(self.effect(pid, "fort"))

    def unrest_target(self, pid):
        """Where unrest settles: foreign faith and tongue stir it, churches and order calm it."""
        p, info = self.provinces[pid], self.static(pid)
        realm = self.info[p.owner]
        unrest = 0.0
        if info.religion != realm["religion"]:
            unrest += 2.0
        if info.culture != realm["culture"]:
            unrest += 1.0
        if p.controller != p.owner:
            unrest += 3.0
        ruler = self.ruler(p.owner)
        calm = self.trait_effect(ruler, "order", 0.0) if ruler else 0.0
        return max(0.0, unrest - self.effect(pid, "order") - calm)

    def income(self, pid):
        """(tax, production, commerce) a month, before anyone takes a share."""
        p, info = self.provinces[pid], self.static(pid)
        order = max(0.3, 1.0 - p.unrest / 20.0)
        tax = p.population * rules.TAX_PER_THOUSAND * p.prosperity * order * (1 + self.effect(pid, "tax")) * \
            self.ruler_tax(p.owner)
        price = rules.GOOD_PRICE.get(info.good, 15)
        production = price * math.sqrt(max(p.population, 0.0) / 10.0) * p.prosperity * \
            (1 + self.effect(pid, "production"))
        commerce = info.city * rules.COMMERCE_PER_THOUSAND * p.prosperity * order * \
            (1 + self.effect(pid, "commerce")) * (rules.COASTAL_COMMERCE if info.coastal else 1.0)
        return tax, production, commerce

    def levy_pool(self, tag):
        """How many men the realm could call to arms if it emptied its villages."""
        return sum(p.population * 1000 * rules.LEVY_SHARE * (1 + self.effect(p.id, "levy"))
                   for p in self.provinces_of(tag) if p.controller == tag)

    def budget(self, tag):
        b = Budget()
        for p in self.provinces.values():
            if p.controller != tag and p.owner != tag:
                continue
            tax, production, commerce = self.income(p.id)
            share = 1.0 if p.controller == p.owner else (rules.OCCUPIED_INCOME if p.controller == tag else 0.0)
            b.tax += tax * share
            b.production += production * share
            b.commerce += commerce * share
            if p.owner == tag:   # the old castles are kept by the lords' men; the new walls cost wages
                b.forts += self.effect(p.id, "fort") * rules.FORT_UPKEEP
        b.beyond = self.beyond_the_map.get(tag, 0.0)
        gross = b.tax + b.production + b.commerce + b.beyond
        b.court = min(rules.COURT_UPKEEP[self.info[tag]["rank"]], 0.25 * gross) + gross * rules.COURT_SHARE
        b.armies = sum(a.upkeep for a in self.armies_of(tag))
        hoard = self.realms[tag].treasury - HOARD_MONTHS * gross
        if hoard > 0:   # palaces, feasts, gifts to the church: a full treasury does not stay full
            b.court += hoard * LARGESSE
        lord = self.overlord.get(tag)
        if lord:
            b.tribute_out = gross * TRIBUTE[lord[1]]
        for vassal, held in self.overlord.items():
            if held and held[0] == tag and self.realms[vassal].alive:
                vb = self._gross(vassal)
                b.tribute_in += vb * TRIBUTE[held[1]]
        return b

    def _gross(self, tag):
        total = 0.0
        for p in self.provinces.values():
            if p.owner == tag and p.controller == tag:
                total += sum(self.income(p.id))
        return total

    # --- building ----------------------------------------------------------------------------------

    def can_build(self, pid, kind):
        """(True, cost, months) or (False, reason)."""
        p, info = self.provinces[pid], self.static(pid)
        b = BUILDINGS[kind]
        level = p.buildings.get(kind, 0)
        if p.controller != p.owner:
            return False, "The province is occupied."
        if p.works:
            return False, f"Already building: {BUILDINGS[p.works['kind']].names[0]}."
        if level >= b.levels:
            return False, "Already built to the full."
        if level == 0 and len(p.buildings) >= rules.slots(info.city):
            return False, "No room left: a bigger town holds more buildings."
        if b.needs == "coastal" and not info.coastal:
            return False, "Needs a coast."
        if b.needs == "mine" and info.good not in rules.MINED:
            return False, "Needs metal or salt in the ground."
        if b.needs == "horses" and not (info.good in ("horses", "livestock") or info.terrain in ("steppe", "plains")):
            return False, "Needs pasture: plains, steppe or herds."
        if b.needs == "town" and info.city < (0, 5, 15)[level]:
            return False, f"Needs a town of {(0, 5, 15)[level]},000 people."
        if kind == "walls" and self.fort(pid) >= 5:
            return False, "The fortifications are as strong as they can be."
        cost, months = b.costs[level], b.months[level]
        if self.realms[p.owner].treasury < cost:
            return False, f"Costs {cost} ducats."
        return True, cost, months

    def build(self, pid, kind):
        check = self.can_build(pid, kind)
        if not check[0]:
            return False
        _, cost, months = check
        p = self.provinces[pid]
        self.realms[p.owner].treasury -= cost
        p.works = {"kind": kind, "months": months}
        return True

    def building_name(self, pid, kind, level):
        if kind == "church" and self.info[self.provinces[pid].owner]["religion"] == "sunni":
            return rules.MOSQUE_NAMES[level - 1]
        return BUILDINGS[kind].names[level - 1]

    # --- troops ----------------------------------------------------------------------------------

    def can_recruit(self, pid, unit_id):
        p = self.provinces[pid]
        u = UNITS[unit_id]
        realm = self.realms[p.owner]
        if p.controller != p.owner:
            return False, "The province is occupied."
        if u.tradition != self.tradition(p.owner):
            return False, "Not raised in this realm."
        if u.tier > self.effect(pid, "recruit"):
            return False, f"Needs a {BUILDINGS['castle'].names[u.tier - 1]}."
        if u.kind == "horse" and u.tier >= 1 and self.effect(pid, "cavalry") < 1 and self.effect(pid, "recruit") < 2:
            return False, "Needs stables or a castle."
        if realm.manpower < u.men:
            return False, "Not enough men left to call."
        if realm.treasury < u.cost:
            return False, f"Costs {u.cost} ducats."
        if len(p.recruits) >= 1 + int(self.effect(pid, "recruit")):
            return False, "The muster ground is full this month."
        return True, u.cost

    def recruit(self, pid, unit_id):
        check = self.can_recruit(pid, unit_id)
        if not check[0]:
            return False
        p = self.provinces[pid]
        u = UNITS[unit_id]
        realm = self.realms[p.owner]
        realm.treasury -= u.cost
        realm.manpower -= u.men
        p.recruits.append(unit_id)
        return True

    def new_army(self, tag, x, y, regiments, name=None):
        army = Army(f"a{self._next_army}", tag, name or f"Army of {self.name(tag)}", x, y, regiments)
        self._next_army += 1
        self.armies.append(army)
        return army

    def split_army(self, army):
        """Half of the army's regiments march off as a new army; returns it (or None)."""
        if len(army.regiments) < 2:
            return None
        half = army.regiments[len(army.regiments) // 2:]
        army.regiments = army.regiments[:len(army.regiments) // 2]
        new = self.new_army(army.owner, army.x + 2, army.y + 2, half)
        new.moves = min(army.moves, new.march)
        army.march = min(r.type.march for r in army.regiments)
        return new

    def merge_armies(self, army):
        """Every army of the realm standing close by joins this one; returns how many joined."""
        joined = 0
        for other in list(self.armies):
            if other is not army and other.owner == army.owner and math.hypot(other.x - army.x, other.y - army.y) < 8:
                army.regiments += other.regiments
                army.march = min(army.march, other.march)
                army.moves = min(army.moves, other.moves)
                self.armies.remove(other)
                joined += 1
        return joined

    def army_at_town(self, tag, pid):
        x, y = self.static(pid).town
        for a in self.armies_of(tag):
            if math.hypot(a.x - x, a.y - y) < 6:
                return a
        return None

    def _first_armies(self):
        """Each realm's field army in September 1402: troops of its tradition, as many as its rank
        warrants and its purse can keep."""
        for tag, realm in self.info.items():
            size = ARMY_SIZE[realm["rank"]]
            where, name = self.capital(tag), None
            if tag in FIELD_ARMIES:
                where, size, name = FIELD_ARMIES[tag]
            if where is None:
                continue
            b = self.budget(tag)
            purse = min(ARMY_SHARE * b.income, 0.9 * (b.balance + b.armies))
            template = TEMPLATES[self.tradition(tag)]
            cheapest = min(template, key=lambda u: UNITS[u].upkeep)
            regiments, upkeep = [], 0.0
            for u in template * 4:
                if len(regiments) >= size:
                    break
                men = UNITS[u].men
                if upkeep + UNITS[u].upkeep > purse:
                    u = cheapest
                    if regiments and upkeep + UNITS[u].upkeep > purse:
                        break
                    # the smallest lords keep a company, not a regiment
                    men = max(60, min(UNITS[u].men, int(UNITS[u].men * purse / UNITS[u].upkeep)))
                regiments.append(Regiment(u, men, 0.2))
                upkeep += regiments[-1].upkeep
            if tag in FIELD_ARMIES:
                regiments = [Regiment(u, UNITS[u].men, 0.5) for u in (TEMPLATES[self.tradition(tag)] * 5)[:size]]
            self.new_army(tag, *self.static(where).town, regiments, name)

    # --- the month -------------------------------------------------------------------------------

    def tell(self, tag, text):
        if tag == self.player:
            self.messages.append(text)

    def end_month(self):
        """Close the month: money, works, people, troops. Returns the messages for the player."""
        self.messages = []
        self.battles = []
        self.pending_battles = []
        self.proposals = [p for p in self.proposals if p.get("fresh")]
        for p in self.proposals:
            p["fresh"] = False
        if self.ai is not None:
            self.ai.month()
        budgets = {tag: self.budget(tag) for tag in self.realms if self.realms[tag].alive}
        for tag, b in budgets.items():
            realm = self.realms[tag]
            realm.treasury += b.balance
            if realm.treasury < 0:
                self._debt(tag)
            realm.prestige += sum(self.effect(p.id, "prestige") for p in self.provinces_of(tag))
            ruler = self.ruler(tag)
            if ruler is not None:
                realm.prestige += self.trait_effect(ruler, "prestige", 0.0)
            pool = self.levy_pool(tag)
            realm.manpower = min(pool, realm.manpower + pool * rules.MANPOWER_RECOVERY)
        for p in self.provinces.values():
            self._province_month(p)
        self.people_month()
        self.appoint_commanders()
        for army in self.armies:
            army.new_month()
            army.walk()
        self.war_month()
        self.history_month()
        self.diplomacy_month()
        self.date = self.date.next()
        return self.messages

    def _debt(self, tag):
        """An empty treasury: unpaid troops desert, a tenth of every regiment at a time."""
        realm = self.realms[tag]
        for army in self.armies_of(tag):
            for r in army.regiments:
                r.men = int(r.men * 0.9)
            army.regiments = [r for r in army.regiments if r.men >= 50]
        self.armies = [a for a in self.armies if a.regiments]
        self.tell(tag, f"The treasury is empty ({realm.treasury:,.0f} ducats): unpaid soldiers desert.")

    def _province_month(self, p):
        info = self.static(p.id)
        growth = (rules.GROWTH_PER_YEAR + self.effect(p.id, "growth")) * p.prosperity / 12
        p.population *= 1 + growth
        p.prosperity = min(1.0, p.prosperity + rules.PROSPERITY_RECOVERY)
        p.unrest += (self.unrest_target(p.id) - p.unrest) * 0.25
        if p.works and p.controller == p.owner:
            p.works["months"] -= 1
            if p.works["months"] <= 0:
                kind = p.works["kind"]
                p.buildings[kind] = p.buildings.get(kind, 0) + 1
                p.works = None
                self.tell(p.owner, f"{info.name}: the {self.building_name(p.id, kind, p.buildings[kind])} "
                                   f"is finished.")
        if p.recruits and p.controller == p.owner:
            regiments = [Regiment(u, UNITS[u].men) for u in p.recruits]
            army = self.army_at_town(p.owner, p.id)
            if army:
                army.regiments += regiments
            else:
                army = self.new_army(p.owner, *info.town, regiments)
            self.tell(p.owner, f"{info.name}: {len(regiments)} new regiment{'s' * (len(regiments) > 1)} "
                               f"joined the {army.name}.")
            p.recruits = []

    # --- offers to the player ----------------------------------------------------------------------

    def propose_peace(self, tag, war, terms):
        if any(p["kind"] == "peace" and p["war"] == war.id for p in self.proposals):
            return
        self.proposals.append({"kind": "peace", "from": tag, "war": war.id, "terms": terms, "fresh": True})
        self.messages.append(f"{self.name(tag)} offers peace: {self.peace_text(war, terms)}")

    def answer(self, proposal, yes):
        """The player's answer to an offer."""
        if proposal in self.proposals:
            self.proposals.remove(proposal)
        if proposal["kind"] == "peace":
            war = next((w for w in self.wars if w.id == proposal["war"]), None)
            if war is None:
                return None
            if yes:
                return self.make_peace(war, proposal["terms"])
            self.nudge(self.player, proposal["from"], -5)
        return None

    # --- saving -----------------------------------------------------------------------------------

    def to_dict(self):
        return {
            "date": [self.date.year, self.date.month], "player": self.player, "next_army": self._next_army,
            "provinces": [asdict(p) for p in self.provinces.values()],
            "realms": [asdict(r) for r in self.realms.values()],
            "overlord": self.overlord,
            "wars": [war_to_dict(w) for w in self.wars], "truces": self.truces, "alliances": self.alliances,
            "next_war": self._next_war, "opinions": self.opinions, "grudges": self.grudges,
            "proposals": self.proposals, "start": [self.start_date.year, self.start_date.month],
            "history": self.history, "marriages": self.marriages, "court": self.people_to_dict(),
            "chronicle": self.history_to_dict(),
            "armies": [{"id": a.id, "owner": a.owner, "name": a.name, "x": a.x, "y": a.y, "march": a.march,
                        "moves": a.moves, "regiments": [asdict(r) for r in a.regiments], "commander": a.commander,
                        "route": {"points": a.route.points, "costs": a.route.costs} if a.route else None}
                       for a in self.armies],
            "rng": self.rng.getstate(),
        }

    @classmethod
    def from_dict(cls, data, provmap, realms, relations=()):
        c = cls(provmap, realms, relations, player=data["player"], date=Date(*data["date"]), armies=False)
        c._next_army = data["next_army"]
        c.provinces = {p["id"]: ProvinceState(**p) for p in data["provinces"]}
        c.realms = {r["tag"]: RealmState(**r) for r in data["realms"]}
        c.overlord = {tag: tuple(v) if v else None for tag, v in data["overlord"].items()}
        c.wars = [war_from_dict(w) for w in data["wars"]]
        c.truces = data["truces"]
        c.alliances = data["alliances"]
        c._next_war = data["next_war"]
        c.opinions, c.grudges, c.proposals = data["opinions"], data["grudges"], data["proposals"]
        c.start_date = Date(*data["start"])
        c.history, c.marriages = data["history"], data["marriages"]
        c.people_from_dict(data["court"])
        c.history_from_dict(data["chronicle"])
        c.borders_changed()
        c.armies = []
        for a in data["armies"]:
            route = Route(a["route"]["points"], a["route"]["costs"]) if a["route"] else None
            c.armies.append(Army(a["id"], a["owner"], a["name"], a["x"], a["y"],
                                 [Regiment(**r) for r in a["regiments"]], a["march"], a["moves"], route,
                                 a.get("commander")))
        state = data["rng"]
        c.rng.setstate((state[0], tuple(state[1]), state[2]))
        return c
