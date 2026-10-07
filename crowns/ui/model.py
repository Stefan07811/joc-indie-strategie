"""What the panels show, worked out from the campaign with no graphics (so it can be tested)."""

from ..game import rules
from ..game.rules import BUILDINGS, UNITS

TERRAIN = {"plains": "Plains", "hills": "Hills", "mountains": "Mountains", "forest": "Forest", "steppe": "Steppe",
           "marsh": "Marsh", "desert": "Desert"}
RELIGION = {"catholic": "Catholic", "orthodox": "Orthodox", "sunni": "Sunni Islam", "bosnian_church": "Bosnian Church",
            "armenian": "Armenian Church", "tengri": "the old gods"}
KIND = {"vassal": "a vassal", "tributary": "a tributary", "protectorate": "under the protection",
        "union": "in union"}


def money(n):
    return f"{n:,.0f}"


def signed(n):
    return f"+{n:,.0f}" if n >= 0 else f"−{-n:,.0f}"


def good_name(good):
    return rules.GOOD_NAMES.get(good, good.replace("_", " ").capitalize())


def ruler_line(c, tag):
    info = c.info[tag]
    ruler = c.ruler(tag)
    if ruler is None:
        return info["title"]
    if ruler.name == "The Rector and Great Council":
        return ruler.name
    return f"{info['title']} {ruler.name}, aged {c.age(ruler)}"


def top_bar(c):
    tag = c.player
    realm = c.realms[tag]
    b = c.budget(tag)
    return {"realm": c.info[tag]["name"], "ruler": ruler_line(c, tag), "date": str(c.date),
            "treasury": money(realm.treasury), "balance": signed(b.balance), "manpower": money(realm.manpower),
            "prestige": f"{realm.prestige:.0f}", "wars": len(c.wars_of(tag))}


def budget_lines(c, tag):
    b = c.budget(tag)
    lines = [("Taxes", b.tax), ("Trade goods", b.production), ("Towns' commerce", b.commerce)]
    if b.tribute_in:
        lines.append(("Tribute received", b.tribute_in))
    if b.beyond:
        lines.append(("Lands beyond the map", b.beyond))
    lines += [("Court and officials", -b.court), ("Armies", -b.armies)]
    if b.forts:
        lines.append(("Walls and garrisons", -b.forts))
    if b.tribute_out:
        lines.append(("Tribute paid", -b.tribute_out))
    return lines, b.balance


def province_view(c, pid):
    p, info = c.provinces[pid], c.static(pid)
    tax, production, commerce = c.income(pid)
    owner = c.info[p.owner]
    view = {
        "name": info.name,
        "owner": owner["name"],
        "held": None if p.controller == p.owner else f"Occupied by {c.name(p.controller)}",
        "lines": [
            f"{TERRAIN.get(info.terrain, info.terrain)} · {info.culture.capitalize()} · "
            f"{RELIGION.get(info.religion, info.religion)}",
            f"{p.population * 1000:,.0f} people" + (f", {info.city * 1000:,.0f} in the town" if info.city else ""),
            f"Goods: {good_name(info.good)} · Prosperity {p.prosperity * 100:.0f}% · Unrest {p.unrest:.1f}",
            f"Income {tax + production + commerce:,.1f} a month (taxes {tax:,.1f}, goods {production:,.1f}, "
            f"commerce {commerce:,.1f})",
            f"Fortifications {c.fort(pid)} · garrison {c.garrison(pid):,.0f}",
        ],
        "siege": None,
        "buildings": [],
        "works": None,
        "build": [],
        "recruit": [],
        "mine": p.owner == c.player,
    }
    if p.siege:
        view["siege"] = (f"Besieged by {c.name(p.siege['by'])}: {min(99, p.siege['progress'] * 100):.0f}% "
                         f"after {p.siege['months']} month{'s' * (p.siege['months'] != 1)}")
    for kind, level in p.buildings.items():
        view["buildings"].append(f"{c.building_name(pid, kind, level)} ({level}/{BUILDINGS[kind].levels})")
    view["slots"] = f"{len(p.buildings)} of {rules.slots(info.city)} building places used"
    if p.works:
        kind = p.works["kind"]
        level = p.buildings.get(kind, 0) + 1
        view["works"] = f"Building: {c.building_name(pid, kind, level)}, {p.works['months']} more months"
    if view["mine"]:
        for kind, b in BUILDINGS.items():
            level = p.buildings.get(kind, 0)
            if level >= b.levels:
                continue
            check = c.can_build(pid, kind)
            name = c.building_name(pid, kind, level + 1)
            label = f"{name} — {b.costs[level]:,} ducats, {b.months[level]} months"
            view["build"].append({"kind": kind, "label": label, "about": b.about, "ok": check[0],
                                  "why": None if check[0] else check[1]})
        for u in c.units_for(p.owner):
            check = c.can_recruit(pid, u.id)
            view["recruit"].append({"unit": u.id, "label": f"{u.name} ({u.men} men) — {u.cost:,} ducats, "
                                                         f"{u.upkeep}/month", "about": u.about,
                                    "ok": check[0], "why": None if check[0] else check[1]})
        if p.recruits:
            view["works"] = (view["works"] + " · " if view["works"] else "") + \
                "Mustering: " + ", ".join(UNITS[u].name for u in p.recruits)
    return view


def army_view(c, army):
    groups = {}
    for r in army.regiments:
        g = groups.setdefault(r.unit, [0, 0, 0.0])
        g[0] += 1
        g[1] += r.men
        g[2] += r.experience
    rows = [f"{n} × {UNITS[u].name}: {men:,} men, experience {exp / n * 100:.0f}%"
            for u, (n, men, exp) in groups.items()]
    cmd = c.commander_of(army)
    view = {"name": army.name, "owner": c.info[army.owner]["name"], "men": f"{army.men:,} men",
            "commander": "Led by " + person_line(c, cmd) if cmd else "No captain",
            "upkeep": f"Upkeep {army.upkeep:,.0f} ducats a month", "rows": rows,
            "march": f"Can still march {army.moves:.0f} of {army.march:.0f} km this month",
            "orders": None, "mine": army.owner == c.player}
    if army.route is not None:
        months = max(0.0, army.route.cost - army.moves) / max(1.0, army.march)
        where = c.provmap.at(*army.route.end)
        to = f" to {where.name}" if where else ""
        view["orders"] = f"Marching{to}: " + ("arrives this month" if months <= 0 else
                                              f"{int(months) + 1} more month{'s' * (int(months) + 1 > 1)}")
    prov = c.provmap.at(army.x, army.y)
    if prov is not None and c.provinces[prov.id].siege and c.provinces[prov.id].siege["by"] == army.owner:
        view["orders"] = f"Besieging {prov.name}"
    return view


def relation_line(c, viewer, tag):
    if viewer == tag:
        return "Your realm"
    parts = []
    if c.at_war(viewer, tag):
        parts.append("At war with you")
    elif sorted((viewer, tag)) in c.alliances:
        parts.append("Your ally")
    elif c.truce_with(viewer, tag):
        parts.append("A truce holds")
    lord = c.overlord.get(tag)
    if lord:
        parts.append(f"{KIND[lord[1]].capitalize()} of {c.name(lord[0])}")
    mine = c.overlord.get(viewer)
    if mine and mine[0] == tag:
        parts.append("Your overlord")
    parts.append(f"Opinion of you {c.opinion(viewer, tag):+.0f}")
    return " · ".join(parts)


def realm_view(c, tag, viewer):
    info = c.info[tag]
    realm = c.realms[tag]
    view = {
        "name": info["name"], "ruler": ruler_line(c, tag),
        "court": court_view(c, tag),
        "relation": relation_line(c, viewer, tag),
        "situation": info["situation"],
        "facts": f"{len(c.provinces_of(tag))} provinces · {sum(p.population for p in c.provinces_of(tag)) * 1000:,.0f}"
                 f" people · income {c.budget(tag).income:,.0f} a month · "
                 f"{sum(a.men for a in c.armies_of(tag)):,} men in the field",
        "actions": [],
        "wars": [],
        "uncertain": info.get("uncertain"),
        "alive": realm.alive,
    }
    if tag == viewer or not realm.alive:
        return view
    goals = []
    lord = c.overlord.get(viewer)
    if lord and lord[0] == tag:
        goals.append(("War for independence", {"kind": "independence"}))
    else:
        border = [p for p in c.provinces_of(tag)
                  if any(c.provinces[n].owner == viewer for n in c.static(p.id).neighbors)]
        for p in sorted(border, key=lambda p: -c.value(p.id))[:4]:
            goals.append((f"War to conquer {c.static(p.id).name}", {"kind": "conquest", "province": p.id}))
        goals.append(("War to make them pay tribute", {"kind": "tribute"}))
    for label, goal in goals:
        ok, why = c.can_declare(viewer, tag, goal)
        view["actions"].append({"do": "war", "goal": goal, "label": label, "ok": ok, "why": why})
    ok, why = c.alliance_answer(viewer, tag)
    view["actions"].append({"do": "ally", "label": "Propose an alliance", "ok": ok, "why": None if ok else why})
    if sorted((viewer, tag)) in c.alliances:
        view["actions"].append({"do": "break", "label": "Break the alliance", "ok": True, "why": None})
    ok, why = c.tribute_answer(viewer, tag)
    view["actions"].append({"do": "tribute", "label": "Demand tribute", "ok": True,
                            "why": None if ok else why})
    for offer in marriage_offers(c, viewer, tag):
        view["actions"].append({"do": "marry", "label": offer["label"], "ok": offer["ok"], "why": offer["why"],
                                "pair": (offer["ours"], offer["theirs"])})
    gift = max(100, int(c.budget(tag).income / 100) * 100)
    view["actions"].append({"do": "gift", "amount": gift, "label": f"Send a gift of {gift:,} ducats",
                            "ok": c.realms[viewer].treasury >= gift, "why": None})
    for war in c.wars:
        if viewer in war.enemies(tag) and tag in (war.leader, war.target) and viewer in (war.leader, war.target):
            view["wars"].append(war_view(c, war, viewer))
    return view


def war_view(c, war, viewer):
    score = c.score(war)
    mine = score if war.side(viewer) == "attackers" else -score
    other = war.target if viewer == war.leader else war.leader
    offers = []
    for label, terms in peace_offers(c, war, viewer, other):
        offers.append({"label": label, "terms": terms, "ok": c.would_accept(war, terms, other)})
    return {"id": war.id, "name": c.war_name(war), "goal": c.goal_text(war),
            "score": f"War score {mine:+.0f} (in your favour)" if mine >= 0 else f"War score {mine:+.0f} (against you)",
            "sides": "With you: " + ", ".join(c.name(t) for t in (war.attackers if war.side(viewer) == "attackers"
                                                                    else war.defenders)) +
                     " · Against you: " + ", ".join(c.name(t) for t in war.enemies(viewer)),
            "log": war.log[-4:], "offers": offers}


def peace_offers(c, war, viewer, other):
    """The peace terms the player can put forward."""
    offers = [("Offer a white peace", {"loser": None})]
    held = [p.id for p in c.provinces_of(other) if p.controller == viewer]
    goal = war.goal
    if war.side(viewer) == "attackers":
        if goal["kind"] == "conquest" and c.provinces[goal["province"]].owner == other:
            offers.append((f"Demand {c.static(goal['province']).name}",
                           {"loser": other, "provinces": [goal["province"]]}))
        if goal["kind"] == "tribute":
            offers.append(("Demand tribute", {"loser": other, "tribute": True}))
        if goal["kind"] == "independence":
            offers.append(("Demand our freedom", {"loser": other, "independence": True}))
    if held:
        offers.append(("Demand the land we hold: " + ", ".join(c.static(p).name for p in held[:3]) +
                       ("…" if len(held) > 3 else ""), {"loser": other, "provinces": held}))
    gold = int(max(0, min(c.realms[other].treasury, 6 * c.budget(other).income)) / 100) * 100
    if gold:
        offers.append((f"Demand {gold:,} ducats", {"loser": other, "gold": gold}))
    if war.side(viewer) == "defenders" and goal["kind"] == "conquest" and \
            c.provinces[goal["province"]].owner == viewer:
        offers.append((f"Give up {c.static(goal['province']).name}",
                       {"loser": viewer, "provinces": [goal["province"]]}))
    if war.side(viewer) == "defenders" and goal["kind"] == "tribute":
        offers.append(("Agree to pay tribute", {"loser": viewer, "tribute": True}))
    return offers


def playable(c):
    """The realms the player can choose, the great first."""
    order = {"empire": 0, "kingdom": 1, "duchy": 2, "county": 3}
    return sorted((t for t in c.realms if c.realms[t].alive),
                  key=lambda t: (order[c.info[t]["rank"]], c.info[t]["short"]))


def person_line(c, p, role=None):
    """'Heir: Mihail (17) — brave, just · martial 7, diplomacy 5, stewardship 6'."""
    if p is None:
        return ""
    traits = ", ".join(p.traits)
    if c.age(p) < 16:
        return f"{role + ': ' if role else ''}{p.name} ({c.age(p)}), still a child"
    skills = (f"martial {c.skill(p, 'martial')}, diplomacy {c.skill(p, 'diplomacy')}, "
              f"stewardship {c.skill(p, 'stewardship')}")
    who = f"{p.name} ({c.age(p)})"
    if role:
        who = f"{role}: {who}"
    return f"{who}{' — ' + traits if traits else ''} · {skills}"


def court_view(c, tag):
    ruler = c.ruler(tag)
    view = {"ruler": person_line(c, ruler, c.info[tag]["title"]), "spouse": None, "heir": None, "children": [],
            "character": None}
    if ruler is None:
        return view
    traits = ", ".join(ruler.traits)
    view["character"] = (f"{traits.capitalize() + ' · ' if traits else ''}martial {c.skill(ruler, 'martial')}, "
                         f"diplomacy {c.skill(ruler, 'diplomacy')}, stewardship {c.skill(ruler, 'stewardship')}")
    if ruler.spouse:
        view["spouse"] = person_line(c, c.people[ruler.spouse], "Wife" if not ruler.female else "Husband")
    heir = c.heir_of(tag)
    view["heir"] = person_line(c, heir, "Heir") if heir else (
        "Heir: chosen by election" if c.info[tag]["government"] in ("republic", "theocracy", "order")
        else "Heir: none — the line may fail")
    for cid in ruler.children:
        child = c.people[cid]
        if child.alive and (heir is None or child.id != heir.id):
            married = f", married to {c.people[child.spouse].name}" if child.spouse else ""
            view["children"].append(f"{'Daughter' if child.female else 'Son'}: {child.name} ({c.age(child)}){married}")
    return view


def marriage_offers(c, viewer, tag, most=3):
    """Matches the player can propose between the two houses."""
    ours = c.marriageable(viewer)
    theirs = c.marriageable(tag)
    offers = []
    for a in ours:
        for b in theirs:
            if a.female == b.female:
                continue
            ok, why = c.marriage_answer(a.id, b.id)
            offers.append({"ours": a.id, "theirs": b.id, "ok": ok, "why": None if ok else why,
                           "label": f"Marry {a.name} ({c.age(a)}) to {b.name} ({c.age(b)})",
                           "gap": abs(c.age(a) - c.age(b))})
    offers.sort(key=lambda o: (not o["ok"], o["gap"]))
    return offers[:most]
