"""The people: rulers, heirs, wives and children, and the captains who lead the armies.

Everyone ages a month at a time and may die, more often in childhood and old age. Married couples
have children; the ruling houses marry among themselves, which warms the realms towards each other.
When a ruler dies the heir takes the throne: his eldest son, else a brother, a nephew, a daughter
where women may reign, else anyone of the house. If an heir already rules elsewhere, the two realms
pass into one hand. If the line fails, a new house is raised and the land is restless. Republics
elect a new head, the Church and the Knights a new prelate or grand master. A ruler's skills and
character tell: a good steward raises more in taxes, a diplomat is better liked, a soldier fights
better at the head of his army.
"""

from dataclasses import asdict, dataclass, field
from typing import Optional

from . import names

TRAITS = {
    # name: effects
    "brave": {"martial": 2}, "craven": {"martial": -2}, "strategist": {"martial": 3},
    "just": {"stewardship": 1, "order": 0.5}, "cruel": {"diplomacy": -2},
    "pious": {"prestige": 0.1}, "ambitious": {"aggression": 1.6}, "content": {"aggression": 0.5},
    "patient": {"aggression": 0.8, "diplomacy": 1}, "greedy": {"stewardship": 1, "diplomacy": -1},
    "generous": {"diplomacy": 2, "stewardship": -1}, "scholar": {"stewardship": 1, "diplomacy": 1},
    "cunning": {"diplomacy": 2}, "sickly": {"health": 0.6}, "strong": {"health": 1.3, "martial": 1},
    "drunkard": {"stewardship": -2, "health": 0.8}, "lustful": {"fertility": 1.4},
    "chaste": {"fertility": 0.6},
}
RANDOM_TRAITS = ["brave", "craven", "just", "cruel", "pious", "ambitious", "content", "patient", "greedy",
                 "generous", "scholar", "cunning", "sickly", "strong", "drunkard", "lustful", "chaste"]
OPPOSITE = {"brave": "craven", "craven": "brave", "ambitious": "content", "content": "ambitious",
            "greedy": "generous", "generous": "greedy", "lustful": "chaste", "chaste": "lustful",
            "sickly": "strong", "strong": "sickly", "just": "cruel", "cruel": "just"}
# A reading of the rulers of 1402 from what the chronicles say of them.
HISTORICAL = {
    "Mircea the Elder": ["brave", "strategist", "ambitious"],
    "Alexander the Good": ["just", "pious", "patient"],
    "Sigismund of Luxembourg": ["ambitious", "cunning", "lustful"],
    "Wenceslaus IV": ["drunkard", "content"],
    "Jobst of Moravia": ["greedy", "cunning"],
    "Władysław II Jagiełło": ["pious", "patient"],
    "Vytautas the Great": ["ambitious", "strategist"],
    "Timur": ["strategist", "cruel", "ambitious"],
    "Süleyman Çelebi": ["drunkard", "generous"],
    "İsa Çelebi": ["ambitious"],
    "Mehmed Çelebi": ["patient", "cunning", "brave"],
    "Manuel II Palaiologos": ["scholar", "pious"],
    "Theodore I Palaiologos": ["cunning"],
    "Stefan Lazarević": ["scholar", "pious", "brave"],
    "Đurađ Branković": ["cunning", "patient"],
    "Hrvoje Vukčić Hrvatinić": ["ambitious", "cunning"],
    "Sandalj Hranić Kosača": ["ambitious", "greedy"],
    "Stephen Ostoja": ["content"],
    "Ladislaus": ["ambitious", "cruel"],
    "Boniface IX": ["greedy"],
    "Michele Steno": ["cunning"],
    "Carlo I Tocco": ["ambitious"],
    "İsfendiyar Bey": ["cunning"],
    "Yakub II": ["scholar"],
    "Mehmed II of Karaman": ["ambitious", "brave"],
    "Manuel III Megas Komnenos": ["patient"],
    "George VII": ["brave"],
    "Philibert de Naillac": ["brave", "pious"],
    "Henry XVI the Rich": ["greedy"],
    "Gjon Kastrioti": ["brave"],
    "an-Nasir Faraj": ["cruel"],
}
FEMALE_RULERS = {"Helena Thopia", "Regina Balšić"}
ALIASES = {"Albert of Austria": "Albert IV"}     # heirs named differently where they already reign
FEMALE_RELATIONS = {"sister", "daughter", "mother"}
# Where a daughter may inherit when there is no son, brother or nephew.
DAUGHTERS_INHERIT = {"catholic", "orthodox", "armenian"}
# Yearly chance of dying, by age, for people who live in castles and palaces.
MORTALITY = [(1, 0.18), (5, 0.05), (15, 0.012), (40, 0.016), (50, 0.026), (60, 0.042), (70, 0.075),
             (80, 0.14), (200, 0.26)]
BIRTH_CHANCE = 0.028          # a month, for a married woman of 16 to 42
CHILDBED_DEATH = 0.015
MARRIAGE_OPINION = 25
COUNCIL = "The Rector and Great Council"      # Ragusa's rector served a month: the council is the ruler
POPES = {"Innocent": 7, "Gregory": 12, "Martin": 5, "Eugene": 4, "Nicholas": 5, "Callixtus": 3, "Pius": 2,
         "Paul": 2, "Sixtus": 4, "Alexander": 5, "Urban": 7, "Clement": 7, "Julius": 2, "Leo": 10}
KINSMAN = 0.65        # when the line fails, the chance a cousin of the house is found to take the throne
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
         "XVI", "XVII", "XVIII", "XIX", "XX"]


@dataclass
class Person:
    id: str
    name: str
    born: int
    female: bool
    court: str                           # the realm whose court they belong to
    dynasty: Optional[str] = None
    father: Optional[str] = None
    mother: Optional[str] = None
    spouse: Optional[str] = None
    children: list = field(default_factory=list)
    traits: list = field(default_factory=list)
    martial: int = 5
    diplomacy: int = 5
    stewardship: int = 5
    alive: bool = True
    died: Optional[int] = None
    captain: bool = False                # a captain of the court, not of the ruling house
    historical: bool = False


class Court:
    """The people of every realm (part of Campaign)."""

    # --- the people of 1402 ----------------------------------------------------------------------

    def _init_people(self):
        self.people = {}
        self.rulers = {}
        self.designated = {}
        self._next_person = 1
        for tag, info in self.info.items():
            r = info["ruler"]
            ruler = self.add_person(r["name"], r.get("born") or 1350, r["name"] in FEMALE_RULERS, tag,
                                    r.get("dynasty"), traits=HISTORICAL.get(r["name"]), historical=True)
            self.rulers[tag] = ruler.id
        by_name = {self.people[pid].name: self.people[pid] for pid in self.rulers.values()}
        for tag, info in self.info.items():
            ruler = self.ruler(tag)
            female = ruler.female
            if info.get("spouse"):
                spouse = self.add_person(info["spouse"], min(ruler.born + (8 if not female else -4), 1386),
                                         not female, tag, None, historical=True)
                ruler.spouse, spouse.spouse = spouse.id, ruler.id
            heir = info.get("heir")
            if not heir:
                continue
            h = by_name.get(ALIASES.get(heir["name"], heir["name"]))     # an heir who rules elsewhere
            if h is None:
                h = self.add_person(heir["name"], heir.get("born") or ruler.born + 25,
                                    heir["relation"] in FEMALE_RELATIONS, tag, heir.get("dynasty") or ruler.dynasty,
                                    traits=HISTORICAL.get(heir["name"]), historical=True)
            if heir["relation"] == "son":
                h.father = ruler.id
                ruler.children.append(h.id)
            elif heir["relation"] == "father":
                ruler.father = h.id
                h.children.append(ruler.id)
            self.designated[tag] = h.id

    def add_person(self, name, born, female, court, dynasty=None, traits=None, father=None, mother=None,
                   historical=False, captain=False):
        rng = self.rng
        if traits is None:
            traits = []
            for _ in range(rng.choice((1, 1, 2, 2, 3))):
                t = rng.choice(RANDOM_TRAITS)
                if t not in traits and OPPOSITE.get(t) not in traits:
                    traits.append(t)
        skill = (lambda: rng.randint(4, 8)) if historical else (lambda: rng.randint(2, 8))
        p = Person(f"p{self._next_person}", name, born, female, court, dynasty, father, mother,
                   traits=list(traits), martial=skill(), diplomacy=skill(), stewardship=skill(),
                   historical=historical, captain=captain)
        self._next_person += 1
        self.people[p.id] = p
        return p

    # --- who is who ---------------------------------------------------------------------------------

    def ruler(self, tag):
        return self.people.get(self.rulers.get(tag))

    def age(self, person):
        return self.date.year - person.born

    def skill(self, person, kind):
        """A skill with the person's traits counted in (0 .. 12)."""
        value = getattr(person, kind) + sum(TRAITS[t].get(kind, 0) for t in person.traits)
        return max(0, min(12, value))

    def trait_effect(self, person, name, default=1.0):
        value = default
        for t in person.traits:
            if name in TRAITS[t]:
                value = value * TRAITS[t][name] if default == 1.0 else value + TRAITS[t][name]
        return value

    def family(self, tag):
        """The living members of the ruler's house at the realm's court."""
        ruler = self.ruler(tag)
        if ruler is None:
            return []
        return [p for p in self.people.values() if p.alive and p.court == tag and not p.captain and
                (p.dynasty and p.dynasty == ruler.dynasty or p.id in (ruler.id, ruler.spouse) or
                 p.father == ruler.id or p.mother == ruler.id)]

    def heir_of(self, tag):
        """Who would take the throne if the ruler died today."""
        ruler = self.ruler(tag)
        if ruler is None:
            return None
        gov = self.info[tag]["government"]
        if gov in ("republic", "theocracy", "order"):
            return None   # elected
        designated = self.people.get(self.designated.get(tag))
        if designated is not None and designated.alive and designated.id != ruler.id:
            return designated

        def living(ids, female=False):
            out = [self.people[i] for i in ids if self.people[i].alive and self.people[i].female == female]
            return sorted(out, key=lambda p: p.born)

        sons = living(ruler.children)
        if gov == "tribal":   # seniority: the eldest man of the house goes first
            kin = [p for p in self.family(tag) if not p.female and p.id != ruler.id and self.age(p) >= 16]
            if kin:
                return min(kin, key=lambda p: p.born)
        if sons:
            return sons[0]
        father = self.people.get(ruler.father)
        if father is not None:
            brothers = living([c for c in father.children if c != ruler.id])
            if brothers:
                return brothers[0]
            for b in sorted((self.people[c] for c in father.children if c != ruler.id), key=lambda p: p.born):
                nephews = living(b.children)
                if nephews:
                    return nephews[0]
        if self.info[tag]["religion"] in DAUGHTERS_INHERIT:
            daughters = living(ruler.children, female=True)
            if daughters:
                return daughters[0]
        kin = [p for p in self.family(tag) if p.id != ruler.id and p.dynasty == ruler.dynasty and
               p.id != ruler.spouse and not p.female]
        return min(kin, key=lambda p: p.born) if kin else None

    # --- the passing months ------------------------------------------------------------------------

    def people_month(self):
        rng = self.rng
        year = self.date.year
        for p in list(self.people.values()):
            if not p.alive or p.name == COUNCIL:
                continue
            age = year - p.born
            yearly = next(rate for limit, rate in MORTALITY if age < limit)
            health = self.trait_effect(p, "health")
            if rng.random() < yearly / 12 / health:
                self.dies(p)
        for wife in list(self.people.values()):
            if not (wife.alive and wife.female and wife.spouse):
                continue
            husband = self.people[wife.spouse]
            if not husband.alive or not 16 <= year - wife.born <= 42:
                continue
            chance = BIRTH_CHANCE * self.trait_effect(wife, "fertility") * self.trait_effect(husband, "fertility")
            if len(wife.children) >= 3:
                chance *= 0.75
            if rng.random() < chance:
                self.birth(husband, wife)
        self._arrange_marriages()

    def birth(self, father, mother):
        rng = self.rng
        court = father.court
        culture = self.info[court]["culture"] if court in self.info else "italian"
        female = rng.random() < 0.49
        taken = {self.people[c].name for c in father.children if self.people[c].alive}
        table = names.FEMALE if female else names.MALE
        name = names.pick(table, culture, rng)
        if not female and father.father and rng.random() < 0.35:
            name = self.people[father.father].name.split()[0]
        for _ in range(5):
            if name not in taken:
                break
            name = names.pick(table, culture, rng)
        child = self.add_person(name, self.date.year, female, court, father.dynasty, father=father.id,
                                mother=mother.id)
        father.children.append(child.id)
        mother.children.append(child.id)
        if court == self.player and self.rulers.get(court) in (father.id, mother.id):
            self.tell(court, f"A {'daughter' if female else 'son'}, {name}, is born to "
                             f"{father.name.split(',')[0]}.")
        if rng.random() < CHILDBED_DEATH:
            self.dies(mother, "in childbed")
        return child

    def dies(self, person, how=None):
        person.alive = False
        person.died = self.date.year
        if person.spouse and person.spouse in self.people:
            self.people[person.spouse].spouse = None
        for army in self.armies:
            if getattr(army, "commander", None) == person.id:
                army.commander = None
        for tag, rid in list(self.rulers.items()):
            if rid == person.id:
                self.succession(tag, person, how)
            elif person.court == tag and tag == self.player and person.id == getattr(self.heir_of(tag), "id", None):
                self.tell(tag, f"{person.name}, heir to the throne, has died{' ' + how if how else ''}.")

    def succession(self, tag, dead, how=None):
        """The ruler of `tag` is dead: the next one takes the throne."""
        info = self.info[tag]
        gov = info["government"]
        rng = self.rng
        heir = self.heir_of(tag) if gov not in ("republic", "theocracy", "order") else None
        crisis = False
        if heir is not None:
            ruled = [t for t, rid in self.rulers.items() if rid == heir.id and t != tag]
            self.rulers[tag] = heir.id
            if ruled:
                # one ruler for two realms: the lesser realm is joined to the greater in union
                senior = ruled[0]
                self.overlord[tag] = (senior, "union")
                self.tell(tag, f"{heir.name} of {self.name(senior)} inherits {self.name(tag)}: the two realms "
                               f"are joined in union.")
            else:
                heir.court = tag
        else:
            culture = info["culture"]
            if tag == "papal":
                age = rng.randint(55, 75)
                dynasty = None
                name = self._papal_name()
            elif gov in ("republic", "theocracy", "order"):
                age = rng.randint(50, 72)
                house = names.pick(names.HOUSES, culture, rng)
                dynasty = None if gov in ("theocracy", "order") else house
                name = names.pick(names.MALE, culture, rng) + ("" if dynasty is None else f" {house}")
            elif dead.dynasty and rng.random() < KINSMAN:
                age = rng.randint(20, 50)          # a cousin of the house is found
                dynasty = dead.dynasty
                name = names.pick(names.MALE, culture, rng)
                for p in self.provinces_of(tag):
                    p.unrest += 1.0
            else:
                age = rng.randint(25, 50)
                dynasty = names.pick(names.HOUSES, culture, rng)
                name = f"{names.pick(names.MALE, culture, rng)} {dynasty}"
                crisis = True
            new = self.add_person(name, self.date.year - age, False, tag, dynasty)
            self.rulers[tag] = new.id
            heir = new
        self.designated.pop(tag, None)
        ruler = self.ruler(tag)
        how = f" {how}" if how else ""
        title = info["title"]
        text = f"{title} {dead.name} of {self.name(tag)} has died{how}. {ruler.name} now reigns."
        if crisis:
            text = (f"{title} {dead.name} of {self.name(tag)} has died{how}, the last of the line. The lords "
                    f"raise {ruler.name} to the throne, and the land is restless.")
            for p in self.provinces_of(tag):
                p.unrest += 4.0
            self.realms[tag].prestige -= 10
        self.tell(self.player, text)
        self.history.append([str(self.date), text])

    def _papal_name(self):
        """A new pope takes a papal name and its next number."""
        used = getattr(self, "papal_numbers", None)
        if used is None:
            used = self.papal_numbers = dict(POPES)
        chosen = self.rng.choice(sorted(used))
        used[chosen] += 1
        n = used[chosen]
        return f"{chosen} {ROMAN[n] if n < len(ROMAN) else n}"

    # --- marriages ---------------------------------------------------------------------------------

    def marriageable(self, tag):
        """The unmarried grown members of the ruling house."""
        return [p for p in self.family(tag) if not p.spouse and not p.captain and
                (self.age(p) >= 16 if p.female else self.age(p) >= 17) and self.age(p) <= (35 if p.female else 55)]

    def marriage_answer(self, ours, theirs):
        """Would the house of `theirs` give their hand to `ours`?"""
        a, b = self.people[ours], self.people[theirs]
        ta, tb = a.court, b.court
        if a.female == b.female or a.spouse or b.spouse or not a.alive or not b.alive:
            return False, "They cannot marry."
        if self.at_war(ta, tb):
            return False, "Not while we are at war."
        ra, rb = self.info[ta]["religion"], self.info[tb]["religion"]
        christian = {"catholic", "orthodox", "bosnian_church", "armenian"}
        if ra != rb and not (ra in christian and rb in christian):
            return False, "Not across faiths."
        if self.opinion(ta, tb) < -10:
            return False, f"{self.name(tb)} does not want the match."
        return True, f"{self.name(tb)} agrees to the match."

    def marry(self, a_id, b_id):
        a, b = self.people[a_id], self.people[b_id]
        husband, wife = (a, b) if not a.female else (b, a)
        husband.spouse, wife.spouse = wife.id, husband.id
        if wife.court != husband.court:
            if self.rulers.get(wife.court) != wife.id:   # a reigning queen keeps her court
                old = wife.court
                wife.court = husband.court
                self.nudge(old, husband.court, MARRIAGE_OPINION)
                self.marriages.append(sorted((old, husband.court)))
        return husband, wife

    def propose_marriage(self, ours, theirs):
        ok, why = self.marriage_answer(ours, theirs)
        if ok:
            a, b = self.people[ours], self.people[theirs]
            self.marry(ours, theirs)
            self.tell(a.court if a.court == self.player else b.court,
                      f"{a.name} and {b.name} are married.")
        return ok, why

    def _arrange_marriages(self):
        """The houses marry off their grown children: to another ruling house if one will have them, else
        into the local nobility."""
        rng = self.rng
        for tag in self.realms:
            if not self.realms[tag].alive:
                continue
            for p in self.marriageable(tag):
                age = self.age(p)
                if tag == self.player and age < 24:
                    continue   # the player arranges the young ones' marriages
                if rng.random() > 0.05:
                    continue
                matched = False
                partners = [o for t in self.neighbours.get(tag, ()) if self.realms[t].alive
                            for o in self.marriageable(t) if o.female != p.female]
                rng.shuffle(partners)
                for o in partners[:4]:
                    if self.marriage_answer(p.id, o.id)[0] and self.opinion(tag, o.court) >= 0:
                        self.marry(p.id, o.id)
                        matched = True
                        break
                if not matched and (age >= 20 or rng.random() < 0.3):
                    culture = self.info[tag]["culture"]
                    house = names.pick(names.HOUSES, culture, rng)
                    spouse = self.add_person(f"{names.pick(names.FEMALE if not p.female else names.MALE, culture, rng)}"
                                             f" {house}", self.date.year - max(15, age - rng.randint(0, 8)),
                                             not p.female, tag, None)
                    self.marry(p.id, spouse.id)

    # --- captains ------------------------------------------------------------------------------------

    def commander_of(self, army):
        return self.people.get(getattr(army, "commander", None))

    def appoint_commanders(self):
        """Every army gets a captain: a grown man of the ruling house if one is free, else a noble."""
        busy = {a.commander for a in self.armies if getattr(a, "commander", None)}
        for army in self.armies:
            if getattr(army, "commander", None) in self.people and self.people[army.commander].alive:
                continue
            kin = [p for p in self.family(army.owner) if not p.female and 18 <= self.age(p) <= 65 and
                   p.id not in busy]
            if kin and self.rng.random() < 0.7:
                best = max(kin, key=lambda p: self.skill(p, "martial"))
                if self.skill(best, "martial") >= 5:
                    army.commander = best.id
                    busy.add(best.id)
                    continue
            culture = self.info[army.owner]["culture"]
            house = names.pick(names.HOUSES, culture, self.rng)
            captain = self.add_person(f"{names.pick(names.MALE, culture, self.rng)} {house}",
                                      self.date.year - self.rng.randint(25, 50), False, army.owner, None,
                                      captain=True)
            army.commander = captain.id
            busy.add(captain.id)

    def leadership(self, army):
        """How much the captain adds to the army's strength (1.0 for an average one)."""
        cmd = self.commander_of(army)
        if cmd is None:
            return 0.9
        return 1.0 + 0.04 * (self.skill(cmd, "martial") - 5)

    def after_battle(self, winner, loser, fates=None):
        """Captains die in battle, the beaten more often, or are taken and ransomed; victors learn.
        fates: {army id: "killed" / "captured"} when the battle was fought out on the field."""
        for army, other, risk in ((winner, loser, 0.03), (loser, winner, 0.12)):
            cmd = self.commander_of(army)
            if cmd is None or not cmd.alive:
                continue
            if fates is not None:
                fate = fates.get(army.id)
            else:
                roll = self.rng.random()
                fate = "killed" if roll < risk else ("captured" if army is loser and roll < risk * 2.5 else None)
            if fate == "killed":
                self.dies(cmd, "in battle")
                if army.owner == self.player or cmd.court == self.player:
                    self.tell(self.player, f"{cmd.name} fell in battle.")
            elif fate == "captured":
                self.ransom(cmd, army.owner, other.owner)
        cmd = self.commander_of(winner)
        if cmd is not None and cmd.alive and self.rng.random() < 0.2:
            cmd.martial = min(10, cmd.martial + 1)

    def ransom(self, person, payer, taker):
        """A captain taken in battle comes home when his lord pays for him, as was the custom."""
        price = round(200 + 60 * self.skill(person, "martial") + (300 if person.id in self.rulers.values() else 0), -1)
        paid = min(price, max(0.0, self.realms[payer].treasury))
        self.realms[payer].treasury -= paid
        self.realms[taker].treasury += paid
        text = f"{person.name} was taken in battle; {self.name(payer)} paid {paid:,.0f} ducats to have him back."
        self.tell(payer, text)
        self.tell(taker, text)

    # --- the ruler's mark on the realm ---------------------------------------------------------------

    def ruler_tax(self, tag):
        ruler = self.ruler(tag)
        return 1.0 if ruler is None else 1.0 + 0.02 * (self.skill(ruler, "stewardship") - 5)

    def ruler_charm(self, tag):
        ruler = self.ruler(tag)
        return 0 if ruler is None else 2 * (self.skill(ruler, "diplomacy") - 5)

    def aggression(self, tag):
        ruler = self.ruler(tag)
        return 1.0 if ruler is None else self.trait_effect(ruler, "aggression")

    # --- saving ----------------------------------------------------------------------------------------

    def people_to_dict(self):
        return {"people": [asdict(p) for p in self.people.values()], "rulers": self.rulers,
                "designated": self.designated, "next_person": self._next_person,
                "papal_numbers": getattr(self, "papal_numbers", None)}

    def people_from_dict(self, d):
        self.people = {p["id"]: Person(**p) for p in d["people"]}
        self.rulers = d["rulers"]
        self.designated = d["designated"]
        self._next_person = d["next_person"]
        if d.get("papal_numbers"):
            self.papal_numbers = d["papal_numbers"]
