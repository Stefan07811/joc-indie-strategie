"""The powers beyond the border: the Kingdom of Hungary, the Kingdom of Poland, the Sultan and the
Tatars of the Wild Fields. They do not fight for the Carpathians, but they raid them.

Now and then (more often as the years pass) a power sends raiders over the border into a province of
a legend that pays it no tribute. The raiders fight whatever stands in their way, besiege or plunder
the province (gold, a building, the people's peace), ride on to the next one, and go home with their
loot after a few seasons. Paying a power tribute every season keeps its raiders away; the Christian
kingdoms also sell mercenaries to the legends that border them.
"""

from dataclasses import dataclass

RAIDS_FROM_ROUND = 6  # the first two years are quiet
RAID_CHANCE = 0.04  # per power and season at first...
RAID_CHANCE_PER_YEAR = 0.006  # ...growing each year...
MAX_RAID_CHANCE = 0.12
RAID_SEASONS = 4  # raiders go home after this long, or after two plunders
MERCENARY_PRICE = 1.5  # times the unit's cost


def raiders(game, power):
    return f"{game.data.factions[power]['adjective']} raiders"


@dataclass
class Raid:
    power: str
    victim: str
    province: str


@dataclass
class Plundered:
    power: str
    victim: str
    province: str
    gold: int


def powers(game):
    return [fid for fid, f in game.data.factions.items() if f.get("foreign")]


def is_power(game, fid):
    return bool(fid and game.data.factions.get(fid, {}).get("foreign"))


def borders(game, power):
    lands = set(game.data.factions[power]["foreign"]["lands"])
    return sorted({pid for f in game.data.map.get("foreign", []) if f["name"] in lands
                   for pid in f.get("borders", ())})


def neighbours_of(game, fid):
    """The powers whose lands touch the realm of `fid`."""
    mine = {p.id for p in game.provinces_of(fid)}
    return [power for power in powers(game) if mine & set(borders(game, power))]


def pays(game, fid, power):
    return power in game.tribute.get(fid, ())


def tribute_cost(game, power):
    return game.data.factions[power]["foreign"]["tribute"]


def start_tribute(game, fid, power):
    game.tribute.setdefault(fid, [])
    if power not in game.tribute[fid]:
        game.tribute[fid].append(power)
        game.log.append(f"{game.faction_name(fid)} agree to pay tribute to {game.faction_name(power, True)}.")


def stop_tribute(game, fid, power):
    if pays(game, fid, power):
        game.tribute[fid].remove(power)
        game.log.append(f"{game.faction_name(fid)} stop paying tribute to {game.faction_name(power, True)}.")


def mercenaries(game, fid, power):
    """(unit id, price) a power sells to `fid` (only to realms on its border)."""
    if power not in neighbours_of(game, fid):
        return []
    return [(uid, round(game.data.units[uid]["cost"] * MERCENARY_PRICE))
            for uid in game.data.factions[power]["foreign"]["mercenaries"]]


def hire(game, fid, power, uid):
    """Pay for a mercenary regiment; it joins in a border province (or the capital) next season."""
    offer = dict(mercenaries(game, fid, power))
    if uid not in offer:
        raise ValueError("They will not sell you those")
    if game.treasury[fid].gold < offer[uid]:
        raise ValueError("Not enough gold")
    game.treasury[fid].gold -= offer[uid]
    mine = [pid for pid in borders(game, power) if game.provinces[pid].owner == fid]
    pid = mine[0] if mine else game.capital_of(fid)
    game.provinces[pid].recruits.append(uid)
    game.log.append(f"{game.data.units[uid]['name']} from {game.faction_name(power, True)} ride to "
                    f"{game.provinces[pid].name} for {game.faction_name(fid, True)}.")


# --- each season ---------------------------------------------------------------------------------

def season(game):
    """Tribute is paid, and new raids may begin."""
    for fid in game.turn_order:
        for power in list(game.tribute.get(fid, ())):
            cost = tribute_cost(game, power)
            t = game.treasury[fid]
            if t.gold >= cost:
                t.gold -= cost
            else:
                stop_tribute(game, fid, power)
        if fid != game.player or game.spectate:
            _ai_tribute(game, fid)
    if game.round < RAIDS_FROM_ROUND:
        return
    chance = min(MAX_RAID_CHANCE, RAID_CHANCE + RAID_CHANCE_PER_YEAR * (game.round // 4))
    for power in powers(game):
        if game.rng.random() < chance:
            start_raid(game, power)


def _ai_tribute(game, fid):
    for power in neighbours_of(game, fid):
        raided = game.raided.get(power, {}).get(fid, 0)
        if not pays(game, fid, power) and raided >= 2 and game.treasury[fid].gold > 300:
            start_tribute(game, fid, power)


def start_raid(game, power):
    victims = [pid for pid in borders(game, power)
               if game.provinces[pid].owner in game.turn_order and not pays(game, game.provinces[pid].owner, power)]
    if not victims:
        return None
    pid = game.rng.choice(victims)
    victim = game.provinces[pid].owner
    f = game.data.factions[power]
    size = min(6, 2 + game.round // 12)
    units = [f["foreign"]["raid_units"][i % len(f["foreign"]["raid_units"])] for i in range(size)]
    names = f["general_names"]
    army = game.add_army(power, pid, names[game.rng.randrange(len(names))], units)
    game.raids[army.id] = {"victim": victim, "plunders": 0, "seasons": 0}
    row = game.raided.setdefault(power, {})
    row[victim] = row.get(victim, 0) + 1
    game._event(Raid(power, victim, pid),
                f"{raiders(game, power)} cross the border into {game.provinces[pid].name}!")
    game._arrive(army, None)
    return army


def plunder(game, p, power):
    """Raiders take a province: they loot it instead of keeping it."""
    victim = p.owner
    t = game.treasury.get(victim)
    loot = min(t.gold, 40 + 15 * len(p.buildings)) if t else 0
    if t:
        t.gold -= max(0, loot)
    if p.buildings and game.rng.random() < 0.5:
        p.buildings.remove(game.rng.choice(p.buildings))
    p.garrison = []
    p.besieged_by = None
    p.mods.append(["Plundered", -2, game.round + 4])
    for army in game.armies_in(p.id):
        if army.faction == power and army.id in game.raids:
            game.raids[army.id]["plunders"] += 1
    game._event(Plundered(power, victim, p.id, max(0, loot)),
                f"{raiders(game, power)} plunder {p.name} and carry off {max(0, loot)} gold.")


def take_turn(game):
    """The raiders' orders: storm what they besiege, ride on to the next prize, or go home."""
    for army in [a for a in list(game.armies.values()) if is_power(game, a.faction)]:
        if army.id not in game.armies or game.over:
            continue
        state = game.raids.setdefault(army.id, {"victim": None, "plunders": 0, "seasons": 0})
        state["seasons"] += 1
        if state["seasons"] > RAID_SEASONS or state["plunders"] >= 2 or not army.regiments:
            go_home(game, army)
            continue
        if game.besieging(army):
            forecast = game.forecast(army, army.province)
            if forecast and forecast[0] and forecast[1] >= 0.4:
                game.assault(army.id)
            continue
        reach = game.reachable(army)
        prizes = [pid for pid in reach if game.provinces[pid].owner == state["victim"]
                  and not any(m[0] == "Plundered" for m in game.provinces[pid].mods)]
        if prizes:
            target = max(prizes, key=lambda pid: (len(game.provinces[pid].buildings), -reach[pid].cost, pid))
            game.move_army(army.id, target)
        elif game.provinces[army.province].owner != state["victim"]:
            go_home(game, army)


def go_home(game, army):
    game._leave(army)
    del game.armies[army.id]
    game.raids.pop(army.id, None)
    game.log.append(f"The {raiders(game, army.faction)} ride home with their loot.")
