"""The legends: each faction's unique powers, public order and Outlaw uprisings.

Faction powers are switched on by "traits" in factions.json, so they can be tuned without code:
  church_bane      (Principality) creatures fighting in a province with a Church strike weaker
  hoard_interest   (Dragonkin)    the treasury earns interest, capped by hoard_cap (+15 per Dragon Hoard)
  abduction        (Dragonkin)    an army next to a rival capital can abduct the heir for a ransom
  hora             (Fae Court)    enemy armies on Fae land lose strength every season (double at a Fairy Ring)
  forest_hidden    (Fae Court)    their armies in forests are unseen unless an enemy army stands close
  raise_dead       (Revenants)    after a victory, part of the fallen rise as new regiments
  winter_fury      (Revenants)    they strike harder in winter
"""

from dataclasses import dataclass

from . import battle

REBELS = "haiduci"
REBEL_UNITS = ("haiduc_brigands", "haiduc_marksmen")
HOARD_BONUS = 15
HEALER_RATE, MAX_HEALERS = 0.03, 2
FAILED_ABDUCTION_LOSS = 0.15


@dataclass
class Rebellion:
    province: str
    faction: str  # whose province rose up


@dataclass
class Abduction:
    faction: str
    victim: str
    province: str
    success: bool
    ransom: int


def traits(game, fid):
    return game.data.factions[fid].get("traits", {})


# --- battle modifiers ------------------------------------------------------------------------

def attack_modifier(game, fid, pid):
    """Faction powers that change how hard `fid` strikes when fighting in province `pid`."""
    mult = 1.0
    p = game.provinces[pid]
    if game.data.factions[fid]["creature"] and "church" in p.buildings:
        mult *= traits(game, p.owner).get("church_bane", 1.0) if p.owner else 1.0
    if game.season == "Winter":
        mult *= traits(game, fid).get("winter_fury", 1.0)
    return mult


def raise_dead(game, result, army=None, garrison_of=None):
    """After a Revenant victory, some of the fallen of both sides rise to join the winners."""
    fid = result.winning_faction
    power = traits(game, fid).get("raise_dead") if fid in game.data.factions else None
    if not power:
        return 0
    p = game.provinces[result.province]
    most = power["max"] + (1 if "crypt" in p.buildings and p.owner == fid else 0)
    fallen = result.attacker.losses + result.defender.losses
    count = min(most, int(fallen // power["hp_per_regiment"]))
    if army is not None:
        count = min(count, game.rules["max_regiments"] - len(army.regiments))
    if count <= 0:
        return 0
    risen = game._regiments([power["unit"]] * count)
    if army is not None:
        army.regiments += risen
    else:
        game.provinces[garrison_of].garrison += risen
    name = game.data.units[power["unit"]]["name"]
    note = f"{count} of the fallen rise again as {name}."
    result.notes.append(note)
    game.log.append(f"At {p.name}, {note[0].lower()}{note[1:]}")
    return count


# --- the seasons' magic ----------------------------------------------------------------------

def hora(game):
    """Enemy armies standing on Fae land are danced to exhaustion."""
    for army in list(game.armies.values()):
        p = game.provinces[army.province]
        if p.owner is None or not game.at_war(p.owner, army.faction):
            continue
        rate = traits(game, p.owner).get("hora", 0.0)
        if not rate:
            continue
        if "ring" in p.buildings:
            rate *= 2
        for r in army.regiments:
            r.hp -= game.data.units[r.unit]["hp"] * rate
        if game.player in (army.faction, p.owner):
            game.log.append(f"The Hora of {p.name} wears down {army.general}'s army.")
        game._bury(army, "is danced to death by the Hora")


def healers(game):
    """Armies with Midsummer Maidens recover a little each season, even far from home."""
    for army in game.armies.values():
        healers_here = sum(game.data.units[r.unit]["ability"] == "heal" for r in army.regiments)
        if healers_here:
            rate = HEALER_RATE * min(MAX_HEALERS, healers_here)
            for r in army.regiments:
                full = game.data.units[r.unit]["hp"]
                r.hp = min(full, r.hp + full * rate)


def interest(game, fid):
    """The Dragonkin hoard: a share of the treasury, capped (higher with each Dragon Hoard)."""
    rate = traits(game, fid).get("hoard_interest", 0.0)
    if not rate:
        return 0
    hoards = sum("hoard" in p.buildings for p in game.provinces_of(fid))
    cap = traits(game, fid)["hoard_cap"] + HOARD_BONUS * hoards
    return max(0, min(cap, round(game.treasury[fid].gold * rate)))


# --- the Fae in the forest ---------------------------------------------------------------------

def visible_to(game, viewer, army):
    """Can faction `viewer` see `army`? Fae armies in forests are hidden unless an army of
    `viewer` stands in the same or a neighbouring province."""
    if army.faction == viewer or not traits(game, army.faction).get("forest_hidden"):
        return True
    p = game.provinces[army.province]
    if p.terrain != "forest":
        return True
    near = {p.id, *p.neighbors}
    return any(a.faction == viewer and a.province in near for a in game.armies.values())


# --- the Dragonkin abduct an heir ------------------------------------------------------------

def abduction_target(game, army):
    """(target province, None) if `army` can abduct an heir now, or (None, reason)."""
    power = traits(game, army.faction).get("abduction")
    if not power:
        return None, "Only the Dragonkin abduct heirs"
    if game.round < game.abduct_ready.get(army.faction, 0):
        return None, f"The next abduction is possible in {game.abduct_ready[army.faction] - game.round} seasons"
    if army.moves_left <= 0:
        return None, "Needs a fresh turn"
    here = game.provinces[army.province]
    for pid in sorted({here.id, *here.neighbors}):
        p = game.provinces[pid]
        victim = p.owner
        if (victim and victim != army.faction and victim in game.turn_order and game.capital_of(victim) == pid
                and game.at_war(army.faction, victim)):
            return pid, None
    return None, "No enemy capital within reach"


def abduction_chance(game, army, pid):
    power = traits(game, army.faction)["abduction"]
    guards = len(game.provinces[pid].garrison) + sum(len(a.regiments) for a in game.armies_in(pid)
                                                      if a.faction != army.faction)
    return max(0.2, min(0.9, power["chance"] - 0.08 * guards))


def abduct(game, army):
    pid, reason = abduction_target(game, army)
    if reason:
        raise ValueError(reason)
    power = traits(game, army.faction)["abduction"]
    victim = game.provinces[pid].owner
    success = game.rng.random() < abduction_chance(game, army, pid)
    army.moves_left = 0
    game.abduct_ready[army.faction] = game.round + power["cooldown"]
    ransom = 0
    place = game.provinces[pid].name
    if success:
        ransom = max(0, min(power["ransom"], game.treasury[victim].gold))
        game.treasury[victim].gold -= ransom
        game.treasury[army.faction].gold += ransom
        message = (f"{army.general} carries off the heir of {game.faction_name(victim, True)} from {place}! "
                   f"A ransom of {ransom} gold is paid.")
    else:
        for r in army.regiments:
            r.hp -= game.data.units[r.unit]["hp"] * FAILED_ABDUCTION_LOSS
        message = f"The guards of {place} drive off {army.general}, who tried to abduct the heir."
    event = Abduction(army.faction, victim, pid, success, ransom)
    game._event(event, message)
    game._bury(army, "is cut down by the palace guard")
    return event


# --- public order and the Outlaws ------------------------------------------------------------

def public_order(game, p):
    """(order, [(reason, points), ...]) for a province with an owner. Below zero, the Outlaws may rise."""
    rules = game.data.map["order"]
    fid = p.owner
    parts = [("Base", rules["base"])]
    if game.capital_of(fid) == p.id:
        parts.append(("Capital", rules["capital"]))
    troops = len(p.garrison) + sum(len(a.regiments) for a in game.armies_in(p.id) if a.faction == fid)
    if troops:
        parts.append(("Troops", min(rules["max_troops"], troops * rules["per_regiment"])))
    for bid in p.buildings:
        if game.data.buildings[bid].get("order"):
            parts.append((game.data.buildings[bid]["name"], game.data.buildings[bid]["order"]))
    from .generals import order as generals_order
    camped = generals_order(game, p.id, fid)
    if camped:
        parts.append(("Generals", camped))
    if p.captured_round is not None:
        unrest = rules["conquest_unrest"] - (game.round - p.captured_round)
        if unrest > 0:
            parts.append(("Recently conquered", -unrest))
    t = game.treasury.get(fid)
    if t and t.food <= 0:
        parts.append(("Hunger", -rules["hunger"]))
    if t and t.gold < 0:
        parts.append(("Unpaid debts", -rules["debt"]))
    return sum(v for _, v in parts), parts


def rebellions(game):
    """Unhappy provinces may rise up; the rebels attack at once."""
    rules = game.data.map["order"]
    for p in list(game.provinces.values()):
        if p.owner not in game.turn_order or any(a.faction == REBELS for a in game.armies_in(p.id)):
            continue
        order, _ = public_order(game, p)
        if order >= 0:
            continue
        chance = min(rules["max_revolt_chance"], -order * rules["revolt_chance_per_point"])
        if game.rng.random() >= chance:
            continue
        size = min(rules["max_rebels"], 1 - order)
        names = game.data.factions[REBELS]["general_names"]
        rebels = game.add_army(REBELS, p.id, names[game.round % len(names)],
                               [REBEL_UNITS[i % 2] for i in range(size)])
        game._event(Rebellion(p.id, p.owner), f"Outlaws led by {rebels.general} rise up in {p.name}!")
        game._arrive(rebels, None)


class RebelAI:
    """Outlaws hold their ground and storm the walls once they think they can win."""

    def take_turn(self, game):
        for army in [a for a in game.armies.values() if a.faction == REBELS]:
            if army.id not in game.armies or game.over:
                continue
            if game.besieging(army):
                forecast = game.forecast(army, army.province)
                if forecast and forecast[0] and forecast[1] >= 0.3:
                    game.assault(army.id)
