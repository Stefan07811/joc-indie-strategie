"""The great men of each realm and their discontent: the boyars, barons, archons or beys who hold the land
and the swords, and the pretender they would put on the throne. Their mood rises with defeats, lost lands,
an empty treasury, a weak or child ruler, and falls with victories, gifts and peace. When it boils over
they rise, and a civil war decides between the ruler and the pretender.

Mixed into Campaign (it needs the people of people.py)."""

import math
from dataclasses import asdict, dataclass
from typing import Optional

FACTION_NAMES = {"vlach": "the boyars", "latin": "the barons", "balkan": "the great lords", "greek": "the archons",
                 "ottoman": "the beys", "steppe": "the mirzas", "levant": "the emirs"}
# the quarrels of 1402: the faction's name and the pretender it looked to
HISTORIC = {"wallachia": ("the Dănești boyars", "Dan", 1395),
            "hungary": ("the barons' league", "Ladislaus of Naples", 1377),
            "byzantium": ("the partisans of John VII", "John Palaiologos", 1370),
            "serbia": ("the friends of Vuk Lazarević", "Vuk Lazarević", 1380),
            "bosnia": ("the lords of Hrvoje", "Tvrtko Tvrtković", 1380),
            "moldavia": ("the boyars of Iuga", "Iuga", 1370)}
POWER = {"empire": 30.0, "kingdom": 42.0, "duchy": 38.0, "county": 30.0}


@dataclass
class Faction:
    name: str
    discontent: float = 30.0
    pretender: Optional[str] = None     # a person's id
    quiet: int = 0                      # months of fear after a rising was crushed


class Factions:
    def _init_factions(self):
        self.factions = {}
        self.defeats = {}                # realm -> a weight of recent defeats, fading
        for tag, info in self.info.items():
            if info.get("government") not in ("monarchy", "tribal"):
                continue
            name, pretender, born = HISTORIC.get(tag, (FACTION_NAMES.get(self.tradition(tag), "the lords"),
                                                       None, None))
            f = Faction(name, discontent=55.0 if tag in HISTORIC else 30.0)
            if pretender:
                p = self.add_person(pretender, born, False, tag, historical=True)
                f.pretender = p.id
            self.factions[tag] = f

    def faction(self, tag):
        return self.factions.get(tag)

    def faction_power(self, tag):
        """The share (0-1) of the realm's might the great men could carry with them."""
        rank = self.info[tag]["rank"]
        return POWER.get(rank, 35.0) / 100.0

    def pretender_of(self, tag):
        """The man the faction would crown: their own, or else a kinsman of the ruler who is not the heir."""
        f = self.factions.get(tag)
        if f is None:
            return None
        p = self.people.get(f.pretender) if f.pretender else None
        if p is not None and p.alive and p.id != self.rulers.get(tag):
            return p
        ruler = self.ruler(tag)
        heir = self.heir_of(tag) if ruler else None
        kin = [k for k in self.family(tag) if not k.female and k.alive and k is not ruler and k is not heir and
               self.age(k) >= 16]
        if kin:
            f.pretender = max(kin, key=lambda k: self.age(k)).id
            return self.people[f.pretender]
        return None

    def note_defeat(self, tag, weight=1.0):
        if tag in self.factions:
            self.defeats[tag] = self.defeats.get(tag, 0.0) + weight

    # --- the month -------------------------------------------------------------------------------------

    def discontent_target(self, tag):
        """Where the great men's mood is heading."""
        target = 30.0
        ruler = self.ruler(tag)
        if ruler is not None:
            target -= 3.0 * (self.skill(ruler, "diplomacy") - 5)
            if self.age(ruler) < 16:
                target += 20.0                              # a child on the throne, and a regency to quarrel over
        target += 12.0 * min(3.0, self.defeats.get(tag, 0.0))
        mine = self.provinces_of(tag)
        lost = sum(1 for p in mine if p.controller != tag)
        if mine:
            target += 30.0 * lost / len(mine)
        realm = self.realms[tag]
        income = max(1.0, self.budget(tag).income)
        if realm.treasury < 0:
            target += 15.0
        elif realm.treasury > 6 * income and not self.wars_of(tag):
            target -= 8.0
        return max(0.0, min(100.0, target))

    def factions_month(self):
        for tag, f in self.factions.items():
            if not self.realms[tag].alive:
                continue
            target = self.discontent_target(tag)
            f.discontent += (target - f.discontent) * 0.06 + self.rng.uniform(-1.5, 1.5)
            if f.quiet > 0:
                f.quiet -= 1
                f.discontent = min(f.discontent, 30.0)
            f.discontent = max(0.0, min(100.0, f.discontent))
            self.defeats[tag] = self.defeats.get(tag, 0.0) * 0.93

    # --- what a ruler can do -------------------------------------------------------------------------

    def appease_cost(self, tag, kind):
        income = max(10.0, self.budget(tag).income)
        return round({"privileges": 2.5, "feast": 1.0}.get(kind, 0.0) * income, -1)

    def appease(self, tag, kind):
        """privileges: lands and offices given away; feast: a great feast and gifts; arrest: the leaders
        seized (feared, but it may set the realm alight)."""
        f = self.factions.get(tag)
        if f is None:
            return
        if kind in ("privileges", "feast"):
            cost = self.appease_cost(tag, kind)
            self.realms[tag].treasury -= cost
            f.discontent -= 28.0 if kind == "privileges" else 12.0
            if kind == "privileges":
                self.realms[tag].prestige -= 3
        elif kind == "arrest":
            if self.rng.random() < 0.35:
                self.tell(tag, f"The arrests fail: {f.name} rise in arms!")
                return self.civil_war(tag)
            f.discontent -= 40.0
            f.quiet = 24
            self.tell(tag, f"The leaders of {f.name} are in chains. The rest keep their heads down, for now.")
        f.discontent = max(0.0, f.discontent)

    def civil_war(self, tag):
        """The great men rise for the pretender: the realm's own armies decide it. Returns True if the
        throne changes hands."""
        f = self.factions[tag]
        pretender = self.pretender_of(tag)
        share = self.faction_power(tag) * (0.6 + 0.6 * f.discontent / 100.0)
        ruler = self.ruler(tag)
        skill = 1.0 + 0.05 * (self.skill(ruler, "martial") - 5) if ruler is not None else 0.8
        loyal = (1.0 - share) * skill * self.rng.uniform(0.6, 1.4)
        rebels = share * self.rng.uniform(0.6, 1.4)
        for army in self.armies_of(tag):                    # brother against brother
            for r in army.regiments:
                r.men = int(r.men * 0.8)
            army.regiments = [r for r in army.regiments if r.men >= 50]
        self.armies = [a for a in self.armies if a.regiments]
        if rebels > loyal and pretender is not None:
            text = (f"Civil war in {self.name(tag)}: {f.name} carry the day and {pretender.name} takes the "
                    f"throne" + (f"; {ruler.name} flees into exile." if ruler else "."))
            self.rulers[tag] = pretender.id
            pretender.court = tag
            f.discontent, f.pretender, f.quiet = 20.0, None, 24
            changed = True
        else:
            fate = ""
            if pretender is not None:
                if self.rng.random() < 0.5:
                    self.dies(pretender, "on the block")
                    fate = f" {pretender.name} is taken and beheaded."
                else:
                    fate = f" {pretender.name} flees abroad."
                f.pretender = None
            text = f"Civil war in {self.name(tag)}: the ruler's men crush the rising of {f.name}.{fate}"
            f.discontent, f.quiet = 10.0, 48
            changed = False
        self.tell(tag, text)
        if tag != self.player:
            self.tell(self.player, text)
        self.history.append([str(self.date), text])
        return changed

    def factions_to_dict(self):
        return {"factions": {t: asdict(f) for t, f in self.factions.items()}, "defeats": self.defeats}

    def factions_from_dict(self, data):
        if not data:
            return
        self.factions = {t: Faction(**f) for t, f in data["factions"].items()}
        self.defeats = data.get("defeats", {})


def mood(discontent):
    return ("loyal" if discontent < 20 else "content" if discontent < 40 else "restless" if discontent < 60 else
            "angry" if discontent < 80 else "ready to rise")


def mood_bar(discontent, width=20):
    filled = int(round(math.floor(discontent) / 100 * width))
    return "#" * filled + "-" * (width - filled)
