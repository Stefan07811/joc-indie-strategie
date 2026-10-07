"""History: events that come to pass, missions that each realm pursues, and decisions a ruler can take.

An event fires for a realm when its time and conditions come: the great events of the age at their
dates (Timur leaves Anatolia, the sons of Bayezid fight for his throne, the Council of Constance, the
Hussites, Hunyadi, Skanderbeg, the crusade of Varna), and the chances of life (plague, famine, a rich
harvest, a peasant rising). The player chooses how to answer; the AI weighs the answers. Missions are a
realm's own ambitions, rewarded when achieved; decisions are great steps a ruler may take when the
conditions are met.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from .armies import Regiment
from .calendar import Date
from .rules import UNITS

SUNNI = "sunni"
OTTOMANS = ("ott_rum", "ott_isa", "ott_meh")


@dataclass
class Choice:
    label: str
    effect: Callable
    ai: float = 1.0                      # how likely the AI is to choose it
    about: str = ""


@dataclass
class Event:
    id: str
    title: str
    text: object                         # a string, or fn(c, tag) -> string
    realms: tuple = ()                   # the realms it may fire for; () = the whole world (news)
    start: Optional[Date] = None
    end: Optional[Date] = None
    chance: float = 1.0                  # a month, once the window is open and the conditions hold
    condition: Callable = None
    choices: list = field(default_factory=list)
    effect: Callable = None              # for news: what happens
    once: bool = True


@dataclass
class Mission:
    id: str
    realm: str
    title: str
    text: str
    done: Callable
    reward: Callable
    reward_text: str
    after: tuple = ()


@dataclass
class Decision:
    id: str
    title: str
    text: str
    realms: tuple                        # () = any realm that meets the conditions
    can: Callable                        # fn(c, tag) -> (bool, why)
    do: Callable
    ai: float = 0.3                      # a month's chance the AI takes it when it can
    once: bool = True


# --- conditions and effects -----------------------------------------------------------------------

def alive(c, *tags):
    return all(t in c.realms and c.realms[t].alive for t in tags)


def owns(c, tag, *pids):
    return all(c.provinces[p].owner == tag and c.provinces[p].controller == tag for p in pids)


def level(c, pid, kind):
    return c.provinces[pid].buildings.get(kind, 0)


def free(c, tag):
    return not c.overlord.get(tag)


def subject_of(c, tag, lord):
    held = c.overlord.get(tag)
    return bool(held) and held[0] == lord


def ruler_named(c, tag, name):
    r = c.ruler(tag)
    return r is not None and r.alive and r.name == name


def prestige(n):
    def f(c, tag):
        c.realms[tag].prestige += n
    return f


def gold(n):
    def f(c, tag):
        c.realms[tag].treasury += n
    return f


def manpower(n):
    def f(c, tag):
        c.realms[tag].manpower = max(0.0, c.realms[tag].manpower + n)
    return f


def calm(n):
    def f(c, tag):
        for p in c.provinces_of(tag):
            p.unrest = max(0.0, p.unrest - n)
    return f


def both(*effects):
    def f(c, tag):
        for e in effects:
            e(c, tag)
    return f


def nothing(c, tag):
    return None


def cede(c, pid, to):
    p = c.provinces[pid]
    p.owner = p.controller = to
    p.works, p.recruits, p.siege = None, [], None
    c.borders_changed()


def spawn_army(c, tag, pid, units, name=None, experience=0.3):
    x, y = c.static(pid).town
    return c.new_army(tag, x, y, [Regiment(u, UNITS[u].men, experience) for u in units], name)


def biggest_ottoman(c):
    alive_ = [t for t in OTTOMANS + ("ottomans",) if t in c.realms and c.realms[t].alive]
    return max(alive_, key=lambda t: len(c.provinces_of(t)), default=None)


def neighbours_of_ottomans(c):
    return {n for t in OTTOMANS if alive(c, t) for n in c.neighbours.get(t, ())} - set(OTTOMANS)


# --- the great events ------------------------------------------------------------------------------

def _timur_takes_smyrna(c, tag):
    if alive(c, "knights") and c.provinces["smyrna"].owner == "knights":
        cede(c, "smyrna", "aydin" if alive(c, "aydin") else "timurids")


def _timur_leaves(c, tag):
    c.armies = [a for a in c.armies if not (a.owner == "timurids" and a.name == "The Host of Timur")]
    for t, held in list(c.overlord.items()):
        if held and held[0] == "timurids" and t not in ("trebizond", "akkoyunlu"):
            c.overlord[t] = None


def _timur_dies(c, tag):
    r = c.ruler("timurids")
    if r is not None and r.name == "Timur":
        c.dies(r, "at Otrar, on the road to China")
    for t, held in list(c.overlord.items()):
        if held and held[0] == "timurids":
            c.overlord[t] = None
    c.beyond_the_map["timurids"] = 2500


def _sign_gallipoli(c, tag):
    if owns(c, tag, "thessaloniki") and alive(c, "byzantium"):
        cede(c, "thessaloniki", "byzantium")
    for other in ("byzantium", "venice", "genoa", "serbia"):
        if alive(c, other) and not c.at_war(tag, other):
            c.set_truce(tag, other, 60)
            c.nudge(tag, other, 20)


def _refuse_gallipoli(c, tag):
    for other in ("byzantium", "venice"):
        if alive(c, other):
            c.nudge(tag, other, -20)


def _war_on(target_of, goal_of):
    """An effect that declares war on whoever target_of(c, tag) names, for goal_of(c, tag, target)."""
    def f(c, tag):
        target = target_of(c, tag)
        if target is None:
            return
        goal = goal_of(c, tag, target)
        if goal and c.can_declare(tag, target, goal)[0]:
            c.declare_war(tag, target, goal)
    return f


def _owner_of(pid):
    return lambda c, tag: c.provinces[pid].owner if c.provinces[pid].owner != tag else None


def _conquer(pid):
    return lambda c, tag, target: {"kind": "conquest", "province": pid} if c.provinces[pid].owner == target else None


def _crush_barons(c, tag):
    c.realms[tag].treasury -= 3000
    c.realms[tag].prestige += 5
    calm(1.0)(c, tag)


def _pardon_barons(c, tag):
    c.realms[tag].prestige -= 5
    for p in c.provinces_of(tag):
        if c.static(p.id).culture == "croatian":
            p.unrest += 2.0


def _constance(c, tag):
    if alive(c, "papal"):
        c.realms["papal"].prestige += 20
        for t in c.realms:
            if c.info[t]["religion"] == "catholic" and t != "papal" and alive(c, t):
                c.nudge(t, "papal", 10)


def _hus(c, tag):
    for p in c.provinces_of("bohemia"):
        if c.static(p.id).culture == "czech":
            p.unrest += 2.0


def _crush_hussites(c, tag):
    for army in c.armies_of(tag):
        for r in army.regiments:
            r.men = int(r.men * 0.7)
    for p in c.provinces_of(tag):
        p.unrest += 3.0
    c.realms[tag].prestige += 5


def _four_articles(c, tag):
    if alive(c, "papal"):
        c.nudge(tag, "papal", -30)
    calm(2.0)(c, tag)
    c.realms[tag].prestige -= 5


def _grunwald(c, tag):
    for t in ("poland", "lithuania"):
        if alive(c, t):
            c.realms[t].prestige += 20
            c.realms[t].manpower = max(0.0, c.realms[t].manpower - 3000)


def _hunyadi(c, tag):
    john = c.add_person("John Hunyadi", 1406, False, tag, "Hunyadi", traits=["strategist", "brave"],
                        historical=True)
    john.martial, john.diplomacy, john.stewardship = 9, 6, 6
    armies = sorted(c.armies_of(tag), key=lambda a: -a.men)
    if armies:
        armies[0].commander = john.id


def _skanderbeg(c, tag):
    """George Kastrioti leaves the Sultan's army and raises Albania."""
    sk_tag = "kastrioti"
    realm = c.realms[sk_tag]
    lord = c.overlord.get(sk_tag)
    if not realm.alive:
        realm.alive = True
        for pid in ("kruja", "dibra"):
            if c.provinces[pid].owner in OTTOMANS + ("ottomans",):
                cede(c, pid, sk_tag)
        if not c.provinces_of(sk_tag):
            realm.alive = False
            return
    sk = c.add_person("George Kastrioti, Skanderbeg", 1405, False, sk_tag, "Kastrioti",
                      traits=["strategist", "brave", "ambitious"], historical=True)
    sk.martial, sk.diplomacy, sk.stewardship = 10, 7, 5
    c.rulers[sk_tag] = sk.id
    c.overlord[sk_tag] = None
    army = spawn_army(c, sk_tag, c.provinces_of(sk_tag)[0].id,
                      ["stradioti", "stradioti", "stradioti", "bowmen", "spearmen", "spearmen"],
                      "The League's Host", 0.5)
    army.commander = sk.id
    if lord and alive(c, lord[0]) and c.can_declare(sk_tag, lord[0], {"kind": "independence"})[0]:
        c.overlord[sk_tag] = lord
        c.declare_war(sk_tag, lord[0], {"kind": "independence"})


def _take_the_cross(c, tag):
    target = biggest_ottoman(c)
    if target is None:
        return
    border = [p for p in c.provinces_of(target)
              if any(c.provinces[n].owner == tag for n in c.static(p.id).neighbors)]
    goal = {"kind": "conquest", "province": max(border, key=lambda p: c.value(p.id)).id} if border else \
        {"kind": "tribute"}
    if c.can_declare(tag, target, goal)[0]:
        war = c.declare_war(tag, target, goal)
        for ally in ("poland", "wallachia", "serbia", "bosnia", "kastrioti", "byzantium"):
            if alive(c, ally) and ally not in war.attackers and ally not in war.defenders and ally != c.player \
                    and not c.at_war(ally, tag) and not subject_of(c, ally, target):
                war.attackers.append(ally)
        c.realms[tag].prestige += 10


def _refuse_the_cross(c, tag):
    c.realms[tag].prestige -= 10
    if alive(c, "papal"):
        c.nudge(tag, "papal", -20)


def _city_falls(c, tag):
    holder = c.provinces["constantinople"].owner
    c.realms[holder].prestige += 50
    c.change_info(holder, rank="empire")
    for t in c.realms:
        if alive(c, t) and c.info[t]["religion"] != SUNNI:
            c.nudge(t, holder, -20)


# --- the chances of life ------------------------------------------------------------------------

def _plague(c, tag):
    """The plague comes ashore at a great port and spreads to the lands around."""
    ports = [p for p in c.provinces.values() if c.static(p.id).coastal and c.static(p.id).city >= 8]
    if not ports:
        return
    start = c.rng.choice(ports)
    seen, frontier = {start.id}, [start.id]
    for _ in range(2):
        frontier = [n for pid in frontier for n in c.static(pid).neighbors if n not in seen]
        seen.update(frontier)
    for pid in seen:
        p = c.provinces[pid]
        p.population *= 1 - c.rng.uniform(0.06, 0.15)
        p.prosperity = max(0.3, p.prosperity - 0.2)
    c.plague_at = start.id
    c.tell(c.player, f"The plague has broken out at {c.static(start.id).name} and spreads through "
                     f"{len(seen)} provinces.")


def _famine(c, tag):
    for p in c.provinces_of(tag):
        p.prosperity = max(0.3, p.prosperity - 0.1)
        p.unrest += 1.0


def _harvest(c, tag):
    c.realms[tag].treasury += c.budget(tag).tax


def _revolt_province(c, tag):
    worst = max(c.provinces_of(tag), key=lambda p: p.unrest, default=None)
    return worst


def _crush_revolt(c, tag):
    p = _revolt_province(c, tag)
    if p is None:
        return
    p.prosperity = max(0.3, p.prosperity - 0.2)
    p.unrest = 2.0
    c.realms[tag].prestige -= 2


def _grant_demands(c, tag):
    p = _revolt_province(c, tag)
    if p is None:
        return
    c.realms[tag].treasury -= 8 * sum(c.income(p.id))
    p.unrest = max(0.0, p.unrest - 4)


def _restless(c, tag):
    return any(p.unrest > 6 for p in c.provinces_of(tag))


EVENTS = [
    Event("smyrna", "Timur Takes Smyrna",
          "Timur's army has stormed the Knights' castle of Smyrna in a fortnight and cut off the heads of its "
          "defenders. The city is given back to the beys of Aydın.", start=Date(1402, 12), end=Date(1403, 2),
          condition=lambda c, t: alive(c, "timurids", "knights") and c.provinces["smyrna"].owner == "knights",
          effect=_timur_takes_smyrna),
    Event("bayezid", "Bayezid Dies a Prisoner",
          "Bayezid the Thunderbolt, Sultan of the Ottomans, has died in Timur's captivity at Akşehir. His sons "
          "will fight over what is left of his empire.", start=Date(1403, 3), end=Date(1403, 3)),
    Event("timur_leaves", "Timur Leaves Anatolia",
          "The conqueror has turned east again. His horde rides away over the mountains, and the beys he set up "
          "and the sons of Bayezid are left to themselves.", start=Date(1403, 4), end=Date(1403, 8),
          condition=lambda c, t: alive(c, "timurids"), effect=_timur_leaves),
    Event("timur_dies", "The Death of Timur",
          "Timur has died at Otrar in the winter, on his way to make war on China. His sons and grandsons are "
          "already quarrelling over his empire; his vassals in the west owe nothing to anyone.",
          start=Date(1405, 2), end=Date(1405, 2), condition=lambda c, t: alive(c, "timurids"), effect=_timur_dies),
    Event("gallipoli", "The Treaty of Gallipoli",
          "The Byzantines, the Venetians, the Genoese and the Despot of Serbia offer us peace against our "
          "brothers, for a price: Thessaloniki and the coast must go back to the Emperor.", realms=("ott_rum",),
          start=Date(1403, 1), end=Date(1403, 6),
          condition=lambda c, t: owns(c, t, "thessaloniki") and alive(c, "byzantium") and
          not c.at_war(t, "byzantium"),
          choices=[Choice("Sign the treaty", _sign_gallipoli, 0.85,
                          "Thessaloniki goes to Byzantium; five years of peace with the Christians."),
                   Choice("Keep Thessaloniki", _refuse_gallipoli, 0.15, "The Christians will not forget.")]),
    Event("ulubad", "Bursa or the Grave",
          "Our brother İsa sits in Bursa and calls himself Sultan. The army is ready; the beys await our word.",
          realms=("ott_meh",), start=Date(1403, 3), end=Date(1403, 12), chance=0.35,
          condition=lambda c, t: alive(c, "ott_isa") and c.provinces["bursa"].owner == "ott_isa" and
          not c.at_war(t, "ott_isa") and not c.truce_with(t, "ott_isa"),
          choices=[Choice("March on Bursa", _war_on(_owner_of("bursa"), _conquer("bursa")), 0.9),
                   Choice("Wait for a better day", prestige(-5), 0.1)]),
    Event("suleyman_crosses", "Süleyman Crosses the Straits",
          "Rumelia is quiet and the treaty with the Christians holds. Across the straits our brother holds the "
          "old capital of our fathers.", realms=("ott_rum",), start=Date(1404, 1), end=Date(1406, 12),
          chance=0.15,
          condition=lambda c, t: c.provinces["bursa"].owner in ("ott_meh", "ott_isa") and
          not c.wars_of(t) and not c.truce_with(t, c.provinces["bursa"].owner),
          choices=[Choice("Cross to Anatolia", _war_on(_owner_of("bursa"), _conquer("bursa")), 0.8),
                   Choice("Stay in Rumelia", nothing, 0.2)]),
    Event("zara", "Ladislaus Crowned at Zara",
          "The rebel barons have crowned Ladislaus of Naples King of Hungary at Zara. The Croatian lords and "
          "Hrvoje are with him; the realm wavers.", realms=("hungary",), start=Date(1403, 8), end=Date(1403, 8),
          condition=lambda c, t: alive(c, "naples") and ruler_named(c, "hungary", "Sigismund of Luxembourg"),
          choices=[Choice("Crush the rebels", _crush_barons, 0.7, "3,000 ducats; order restored."),
                   Choice("Pardon the barons", _pardon_barons, 0.3, "The Croatian lands stay restless.")]),
    Event("grunwald", "The Battle of Grunwald",
          "Far to the north, the armies of Poland and Lithuania have crushed the Teutonic Knights at Grunwald. "
          "The Grand Master lies dead on the field.", start=Date(1410, 7), end=Date(1410, 7),
          condition=lambda c, t: alive(c, "poland"), effect=_grunwald),
    Event("constance", "The Council of Constance",
          "The Council of Constance has deposed the rival popes and elected one: the Great Schism is over.",
          start=Date(1417, 11), end=Date(1417, 11), effect=_constance),
    Event("hus", "Jan Hus Burned at Constance",
          "The preacher Jan Hus, promised safe conduct, has been burned as a heretic at Constance. Bohemia "
          "seethes.", start=Date(1415, 7), end=Date(1415, 7), condition=lambda c, t: alive(c, "bohemia"),
          effect=_hus),
    Event("hussites", "The Defenestration of Prague",
          "The Hussites have thrown the councillors of Prague from the windows of the town hall. The kingdom "
          "is in arms.", realms=("bohemia",), start=Date(1419, 7), end=Date(1420, 6),
          choices=[Choice("Crush the heretics", _crush_hussites, 0.6, "The army bleeds; the land burns."),
                   Choice("Accept the Four Articles", _four_articles, 0.4, "Peace at home; Rome is outraged.")]),
    Event("hunyadi", "John Hunyadi",
          "A knight of Wallachian blood from Hunedoara, John Hunyadi, has risen in the King's service. No "
          "captain in the realm is his equal.", realms=("hungary",), start=Date(1441, 1), end=Date(1442, 12),
          effect=_hunyadi, condition=lambda c, t: True),
    Event("skanderbeg", "Skanderbeg",
          "George Kastrioti, whom the Turks call Skanderbeg, has deserted the Sultan's army after Niš, taken "
          "Kruja by a ruse and raised the red banner with the black eagle.", start=Date(1443, 11),
          end=Date(1444, 6), effect=_skanderbeg,
          condition=lambda c, t: (not c.realms["kastrioti"].alive and
                                  any(c.provinces[p].owner in OTTOMANS + ("ottomans",) for p in ("kruja", "dibra")))
          or (c.realms["kastrioti"].alive and bool(c.overlord.get("kastrioti")) and
              c.overlord["kastrioti"][0] in OTTOMANS + ("ottomans",))),
    Event("varna", "The Pope Calls a Crusade",
          "Pope Eugene calls Christendom to drive the Turks from Europe. Poland, Wallachia and the Albanians "
          "will march if the King leads.", realms=("hungary",), start=Date(1443, 9), end=Date(1444, 6),
          condition=lambda c, t: biggest_ottoman(c) is not None and len(c.provinces_of(biggest_ottoman(c))) >= 15
          and not c.at_war(t, biggest_ottoman(c)),
          choices=[Choice("Take the cross", _take_the_cross, 0.7),
                   Choice("Refuse", _refuse_the_cross, 0.3)]),
    Event("city_falls", "The City Has Fallen",
          lambda c, t: f"Constantinople, the Queen of Cities, has fallen to {c.name(c.provinces['constantinople'].owner)}. "
                       "Christendom mourns.", start=Date(1402, 9), end=Date(1600, 1),
          condition=lambda c, t: c.info[c.provinces["constantinople"].owner]["religion"] == SUNNI,
          effect=_city_falls),
    Event("comet", "A Comet in the Sky",
          "A great comet with a long tail blazes over Christendom and Islam. The astrologers argue over what it "
          "portends.", start=Date(1456, 6), end=Date(1456, 6)),
    # the chances of life
    Event("plague", "The Plague", "", start=Date(1403, 1), end=Date(1600, 1), chance=1 / 90, effect=_plague,
          once=False),
    Event("famine", "A Year of Famine",
          "The harvest has failed and the granaries are empty. The people grumble and the tax-farmers come "
          "back with little.", realms=("*",), start=Date(1402, 9), end=Date(1600, 1), chance=1 / 400,
          condition=lambda c, t: c.date.month in (9, 10, 11), effect=_famine, once=False),
    Event("harvest", "A Rich Harvest",
          "The barns are full: the realm's taxes come in twice over this year.", realms=("*",),
          start=Date(1402, 9), end=Date(1600, 1), chance=1 / 300, condition=lambda c, t: c.date.month in (8, 9),
          effect=_harvest, once=False),
    Event("revolt", "The Peasants Rise",
          lambda c, t: f"The peasants of {c.static(_revolt_province(c, t).id).name} have risen against their lords "
                       "and the tax-collectors.", realms=("*",), start=Date(1402, 9), end=Date(1600, 1),
          chance=0.1, condition=lambda c, t: _restless(c, t), once=False,
          choices=[Choice("Send in the soldiers", _crush_revolt, 0.6, "The province is laid waste; order returns."),
                   Choice("Grant their demands", _grant_demands, 0.4, "Costs eight months of its income.")]),
]
EVENT = {e.id: e for e in EVENTS}


# --- decisions -----------------------------------------------------------------------------------

def _dragon(c, tag):
    c.realms[tag].prestige += 15
    for t in ("serbia", "celje", "wallachia", "bosnia", "austria", "poland"):
        if alive(c, t):
            c.nudge(tag, t, 15)


def _back_musa(c, tag):
    c.realms[tag].treasury -= 2500
    c.realms[tag].prestige += 10
    if alive(c, "ott_rum"):
        c.realms["ott_rum"].manpower *= 0.6
        for p in c.provinces_of("ott_rum"):
            p.unrest += 2.0
        c.nudge(tag, "ott_rum", -40)
    if alive(c, "ott_meh"):
        c.nudge(tag, "ott_meh", 20)


def _sultanate(c, tag):
    c.change_info(tag, name="Ottoman Sultanate", short="Ottoman Empire", rank="empire", title="Sultan")
    c.realms[tag].prestige += 30
    for t in OTTOMANS:
        if t != tag and alive(c, t):
            c.nudge(tag, t, -50)


def _hexamilion(c, tag):
    c.realms[tag].treasury -= 4000
    p = c.provinces["corinth"]
    p.buildings["walls"] = min(3, p.buildings.get("walls", 0) + 2)


def _church_union(c, tag):
    for t in c.realms:
        if not alive(c, t) or t == tag:
            continue
        if c.info[t]["religion"] == "catholic":
            c.nudge(tag, t, 15)
        elif c.info[t]["religion"] == "orthodox":
            c.nudge(tag, t, -10)
    for p in c.provinces_of(tag):
        p.unrest += 2.0


def _kingdom(c, tag):
    c.realms[tag].treasury -= 10000
    c.realms[tag].prestige -= 30
    info = c.info[tag]
    c.change_info(tag, rank="kingdom", name=f"Kingdom of {info['short']}", title="King")


def _belgrade_capital(c, tag):
    c.change_info(tag, capital="belgrade")
    c.realms[tag].prestige += 5


def _seek_protector(c, tag):
    best = max((t for t in c.neighbours.get(tag, ()) if alive(c, t) and
                c.info[t]["rank"] in ("kingdom", "empire") and not c.at_war(tag, t)),
               key=lambda t: c.opinion(tag, t), default=None)
    if best:
        c.overlord[tag] = (best, "protectorate")
        c.nudge(tag, best, 20)
        c.realms[tag].treasury += 1000
        c.tell(tag, f"We are now under the protection of {c.name(best)}.")


def _can(condition, why):
    def f(c, tag):
        return (True, None) if condition(c, tag) else (False, why)
    return f


DECISIONS = [
    Decision("dragon", "Found the Order of the Dragon",
             "Bind the great lords of the realm and its friends in an order of knighthood sworn to fight the Turk.",
             ("hungary",), _can(lambda c, t: c.date >= Date(1408, 1) and c.realms[t].prestige >= 10,
                                "From 1408, with 10 prestige."), _dragon, ai=0.2),
    Decision("musa", "Back Musa Çelebi",
             "A younger son of Bayezid has come to our court. With our gold and our men he could take Rumelia "
             "from Süleyman.", ("wallachia",),
             _can(lambda c, t: Date(1409, 1) <= c.date <= Date(1413, 12) and alive(c, "ott_rum") and
                  c.realms[t].treasury >= 2500, "Between 1409 and 1413, with 2,500 ducats."), _back_musa, ai=0.15),
    Decision("sultanate", "Proclaim the Sultanate",
             "We hold both Edirne and Bursa: the House of Osman is one again, and its head is Sultan.",
             OTTOMANS, _can(lambda c, t: owns(c, t, "edirne", "bursa"), "Hold both Edirne and Bursa."),
             _sultanate, ai=1.0),
    Decision("hexamilion", "Build the Hexamilion",
             "Rebuild the wall across the Isthmus of Corinth, and the Morea is shut against the Turk.",
             ("morea", "byzantium"),
             _can(lambda c, t: owns(c, t, "corinth") and c.realms[t].treasury >= 4000,
                  "Hold Corinth, with 4,000 ducats."), _hexamilion, ai=0.4),
    Decision("church_union", "Seek the Union of the Churches",
             "Accept the Pope's terms and reunite the Churches of Rome and Constantinople, for the help of the "
             "West.", ("byzantium",),
             _can(lambda c, t: c.date >= Date(1420, 1) and alive(c, "papal") and c.opinion(t, "papal") >= 0,
                  "From 1420, if the Pope will listen."), _church_union, ai=0.05),
    Decision("kingdom", "Proclaim a Kingdom",
             "The realm has grown great enough to be a kingdom. A crown will cost dearly and the old kings will "
             "sneer, but our heirs will thank us.", (),
             _can(lambda c, t: c.info[t]["rank"] in ("duchy",) and c.info[t]["government"] == "monarchy" and
                  c.realms[t].prestige >= 50 and c.realms[t].treasury >= 10000 and len(c.provinces_of(t)) >= 10
                  and free(c, t), "A free duchy of ten provinces, with 50 prestige and 10,000 ducats."),
             _kingdom, ai=0.5),
    Decision("belgrade_capital", "Make Belgrade the Capital",
             "Move the court to the great fortress at the meeting of the Danube and the Sava.", ("serbia",),
             _can(lambda c, t: owns(c, t, "belgrade") and c.info[t]["capital"] != "belgrade", "Hold Belgrade."),
             _belgrade_capital, ai=0.5),
    Decision("protector", "Seek a Protector",
             "We are too small to stand alone. A powerful neighbour would guard us, for a price in pride.", (),
             _can(lambda c, t: c.info[t]["rank"] == "county" and free(c, t) and not c.wars_of(t),
                  "For a small free lordship at peace."), _seek_protector, ai=0.0, once=False),
]
DECISION = {d.id: d for d in DECISIONS}


# --- the campaign's part ---------------------------------------------------------------------------

class Chronicles:
    """Events, missions and decisions as the months pass (part of Campaign)."""

    def _init_history(self, beyond):
        self.fired = []                  # the ids of the one-time events that have happened
        self.cooldowns = {}              # "event|realm" -> months before it may happen there again
        self.pending = []                # events waiting for the player's answer
        self.missions_done = []
        self.decisions_taken = []        # "decision|realm"
        self.beyond_the_map = dict(beyond)
        self.info_changes = {}           # realm -> {field: value}: crowns proclaimed, capitals moved
        self.plague_at = None
        self.start_size = {t: len(self.provinces_of(t)) for t in self.realms}

    def change_info(self, tag, **fields):
        self.info[tag].update(fields)
        self.info_changes.setdefault(tag, {}).update(fields)

    def set_truce(self, a, b, months):
        until = self.date
        for _ in range(months):
            until = until.next()
        self.truces["|".join(sorted((a, b)))] = [until.year, until.month]

    def event_text(self, event, tag):
        return event.text(self, tag) if callable(event.text) else event.text

    # --- events ---------------------------------------------------------------------------------

    def history_month(self):
        for event in EVENTS:
            if event.once and event.id in self.fired:
                continue
            if (event.start and self.date < event.start) or (event.end and self.date > event.end):
                continue
            if not event.realms:
                targets = [None]
            elif event.realms == ("*",):
                targets = [t for t in self.realms if self.realms[t].alive]
            else:
                targets = [t for t in event.realms if t in self.realms and self.realms[t].alive]
            for tag in targets:
                key = f"{event.id}|{tag}"
                if not event.once and self.cooldowns.get(key, 0) > 0:
                    continue
                if event.condition and not event.condition(self, tag):
                    continue
                if self.rng.random() > event.chance:
                    continue
                self.fire(event, tag)
                if event.once:
                    break
        for key in list(self.cooldowns):
            self.cooldowns[key] -= 1
            if self.cooldowns[key] <= 0:
                del self.cooldowns[key]
        self.missions_month()
        self.ai_decisions()

    def fire(self, event, tag):
        if event.once:
            self.fired.append(event.id)
        else:
            self.cooldowns[f"{event.id}|{tag}"] = 36
        text = self.event_text(event, tag)
        if event.choices:
            if tag == self.player:
                self.pending.append({"event": event.id, "realm": tag, "text": text})
                return
            weights = [ch.ai for ch in event.choices]
            choice = self.rng.choices(event.choices, weights=weights)[0]
            choice.effect(self, tag)
            if event.once:
                self.tell(self.player, f"{event.title}: {self.name(tag)} chose to {choice.label[0].lower()}"
                                       f"{choice.label[1:]}.")
                self.history.append([str(self.date), f"{event.title} ({self.name(tag)})"])
            return
        if event.effect:
            event.effect(self, tag)
        if not event.realms and text:
            self.tell(self.player, f"{event.title}. {text}")
        elif tag == self.player and text:
            self.tell(tag, f"{event.title}. {text}")
        if event.once:
            self.history.append([str(self.date), event.title])

    def choose(self, pending, index):
        """The player's answer to an event."""
        if pending in self.pending:
            self.pending.remove(pending)
        event = EVENT[pending["event"]]
        choice = event.choices[index]
        choice.effect(self, pending["realm"])
        return choice

    # --- missions --------------------------------------------------------------------------------

    def missions_month(self):
        from .missions import missions_of
        done = set(self.missions_done)
        for tag in self.realms:
            if not self.realms[tag].alive:
                continue
            for m in missions_of(self, tag):
                if m.id in done or any(a not in done for a in m.after):
                    continue
                if m.done(self, tag):
                    self.missions_done.append(m.id)
                    done.add(m.id)
                    m.reward(self, tag)
                    self.tell(tag, f"Mission accomplished: {m.title}. Reward: {m.reward_text}.")

    def missions_view(self, tag):
        from .missions import missions_of
        done = set(self.missions_done)
        out = []
        for m in missions_of(self, tag):
            state = "done" if m.id in done else ("locked" if any(a not in done for a in m.after) else "open")
            out.append({"id": m.id, "title": m.title, "text": m.text, "reward": m.reward_text, "state": state})
        return out

    # --- decisions --------------------------------------------------------------------------------

    def decisions_for(self, tag):
        """[(decision, can, why)] that the realm could take, now or later."""
        out = []
        for d in DECISIONS:
            if d.realms and tag not in d.realms:
                continue
            if d.once and f"{d.id}|{tag}" in self.decisions_taken:
                continue
            ok, why = d.can(self, tag)
            out.append((d, ok, why))
        return out

    def take_decision(self, did, tag):
        d = DECISION[did]
        ok, why = d.can(self, tag)
        if not ok:
            return False, why
        d.do(self, tag)
        self.decisions_taken.append(f"{d.id}|{tag}")
        self.tell(self.player, f"{self.name(tag)}: {d.title}.")
        self.history.append([str(self.date), f"{d.title} ({self.name(tag)})"])
        return True, None

    def ai_decisions(self):
        for tag in self.realms:
            if tag == self.player or not self.realms[tag].alive:
                continue
            for d, ok, _ in self.decisions_for(tag):
                if ok and self.rng.random() < d.ai:
                    self.take_decision(d.id, tag)

    # --- saving ------------------------------------------------------------------------------------

    def history_to_dict(self):
        return {"fired": self.fired, "cooldowns": self.cooldowns, "pending": self.pending,
                "missions_done": self.missions_done, "decisions_taken": self.decisions_taken,
                "beyond_the_map": self.beyond_the_map, "info_changes": self.info_changes,
                "plague_at": self.plague_at, "start_size": self.start_size}

    def history_from_dict(self, d):
        for k in ("fired", "cooldowns", "pending", "missions_done", "decisions_taken", "beyond_the_map",
                  "info_changes", "plague_at", "start_size"):
            setattr(self, k, d[k])
        for tag, fields in self.info_changes.items():
            self.info[tag].update(fields)
