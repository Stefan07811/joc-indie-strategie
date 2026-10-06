"""Tales from the land: events from Romanian folklore (data/events.json) that befall a realm now
and then, each with a choice. The human player chooses in a pop-up; the computer's legends take
their event's "ai" choice at once.

An event's effects (all optional):
  gold, food            added to the treasury (negative to pay)
  order / order_all     order in the event's province / every province, for "turns" seasons
  regiment              a free regiment of that unit, arriving in the province next season
  trait                 given to one of the realm's generals (the most experienced who can take it)
  heal_armies / hurt_armies   share of full strength restored to / taken from every army
  hurt_target           share of strength taken from the armies standing in the province
  gamble                {"chance": p, "win": {...}, "lose": {...}}
"""

from dataclasses import dataclass

from . import generals

EVENT_CHANCE = 0.3  # each season, the chance a realm meets an event
DEFAULT_TURNS = 3


@dataclass
class Tale:
    """An event that befell a realm (in the pending list while the human player decides)."""
    event: str
    faction: str
    province: str | None = None


def eligible(game, fid):
    out = []
    for eid, e in game.data.events.items():
        if "seasons" in e and game.season not in e["seasons"]:
            continue
        if "factions" in e and fid not in e["factions"]:
            continue
        if fid in e.get("not_factions", ()):
            continue
        if e.get("target") == "province" and not game.provinces_of(fid):
            continue
        out.append(eid)
    return out


def season(game):
    """Maybe one event for each realm this season."""
    for fid in list(game.turn_order):
        if fid in game.eliminated or game.rng.random() >= EVENT_CHANCE:
            continue
        options = eligible(game, fid)
        if not options:
            continue
        eid = game.rng.choice(sorted(options))
        e = game.data.events[eid]
        pid = None
        if e.get("target") == "province":
            pid = game.rng.choice(sorted(p.id for p in game.provinces_of(fid)))
        tale = Tale(eid, fid, pid)
        if fid == game.player and not game.spectate:
            game.pending_events.append(tale)
            game.events.append(tale)
        else:
            choose(game, tale, e.get("ai", 0))


def text(game, tale, string):
    return string.replace("{province}", game.provinces[tale.province].name if tale.province else "the land")


def choose(game, tale, index):
    """Carry out the chosen answer. Returns the line written in the chronicle."""
    if tale in game.pending_events:
        game.pending_events.remove(tale)
    e = game.data.events[tale.event]
    choice = e["choices"][index]
    apply(game, tale, choice.get("effects", {}))
    line = f"{e['title']}: {text(game, tale, choice.get('result', choice['label']))}"
    if tale.faction == game.player:
        game.log.append(line)
    return line


def apply(game, tale, effects):
    fid, rng = tale.faction, game.rng
    t = game.treasury[fid]
    t.gold += effects.get("gold", 0)
    t.food = max(0, t.food + effects.get("food", 0))
    turns = effects.get("turns", DEFAULT_TURNS)
    title = game.data.events[tale.event]["title"]
    if effects.get("order") and tale.province:
        game.provinces[tale.province].mods.append([title, effects["order"], game.round + turns])
    if effects.get("order_all"):
        for p in game.provinces_of(fid):
            p.mods.append([title, effects["order_all"], game.round + turns])
    if effects.get("regiment"):
        pid = tale.province or game.capital_of(fid)
        if pid in game.provinces and game.provinces[pid].owner == fid:
            game.provinces[pid].recruits.append(effects["regiment"])
    if effects.get("trait"):
        candidates = sorted(game.armies_of(fid), key=lambda a: -a.xp)
        for army in candidates:
            if generals.give_trait(game, army, effects["trait"]):
                break
    for key, sign in (("heal_armies", 1), ("hurt_armies", -1)):
        if effects.get(key):
            for army in game.armies_of(fid):
                _change(game, army, sign * effects[key])
    if effects.get("hurt_target") and tale.province:
        for army in game.armies_in(tale.province):
            if army.faction == fid:
                _change(game, army, -effects["hurt_target"])
    if effects.get("gamble"):
        g = effects["gamble"]
        won = rng.random() < g["chance"]
        apply(game, tale, g["win"] if won else g["lose"])
        if fid == game.player:
            game.log.append(f"{title}: " + ("fortune smiles." if won else "it goes badly."))


def _change(game, army, share):
    for r in army.regiments:
        full = game.data.units[r.unit]["hp"]
        r.hp = max(1.0, min(full, r.hp + full * share))
    game._bury(army, "is wiped out")


def order(game, p):
    """[(name, points)] of the events still weighing on a province's mood."""
    return [(name, points) for name, points, until in p.mods if until > game.round]


def summary(game, effects):
    """A short description of a choice's effects, for the buttons."""
    parts = []
    if effects.get("gold"):
        parts.append(f"{effects['gold']:+} gold")
    if effects.get("food"):
        parts.append(f"{effects['food']:+} food")
    turns = effects.get("turns", DEFAULT_TURNS)
    if effects.get("order"):
        parts.append(f"{effects['order']:+} order here ({turns} seasons)")
    if effects.get("order_all"):
        parts.append(f"{effects['order_all']:+} order everywhere ({turns} seasons)")
    if effects.get("regiment"):
        parts.append(f"a free {game.data.units[effects['regiment']]['name']} regiment")
    if effects.get("trait"):
        parts.append(f"a general becomes {game.data.traits[effects['trait']]['name']}")
    if effects.get("heal_armies"):
        parts.append("armies heal")
    if effects.get("hurt_armies") or effects.get("hurt_target"):
        parts.append("armies suffer")
    if effects.get("gamble"):
        g = effects["gamble"]
        parts.append(f"{round(g['chance'] * 100)}% chance: {summary(game, g['win'])}; "
                     f"otherwise: {summary(game, g['lose'])}")
    return ", ".join(parts) or "nothing changes"
