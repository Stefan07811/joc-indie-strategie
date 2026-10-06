"""Gold, food, buildings and recruitment. Pure rules; Game calls these and keeps the state."""

from dataclasses import dataclass


@dataclass
class Treasury:
    gold: int
    food: int


@dataclass
class Balance:
    tax: int  # gold from provinces and buildings
    upkeep: int  # gold paid to the armies
    food_made: int  # this season, after the season's multiplier
    food_eaten: int

    @property
    def gold(self):
        return self.tax - self.upkeep

    @property
    def food(self):
        return self.food_made - self.food_eaten


def is_capital(game, pid):
    return any(f["capital"] == pid for f in game.data.factions.values())


def province_yield(game, p):
    """(gold, food) a province produces each season, before the season's food multiplier."""
    terrain = game.data.terrain[p.terrain]
    gold = terrain["tax"] + (game.rules["capital_tax"] if is_capital(game, p.id) else 0)
    food = terrain["food"]
    for bid in p.buildings:
        b = game.data.buildings[bid]
        gold += b["gold"]
        food += b["food"]
    return gold, food


def appetite(game, uid):
    """Food a regiment eats each season: bigger, costlier creatures eat more."""
    return max(1, round(game.data.units[uid]["cost"] / game.rules["gold_per_food"]))


def balance(game, fid, season=None):
    season = season or game.season
    tax = food = 0
    for p in game.provinces_of(fid):
        g, f = province_yield(game, p)
        tax += g
        food += f
    regiments = [r for a in game.armies_of(fid) for r in a.regiments]
    upkeep = sum(game.data.units[r.unit]["upkeep"] for r in regiments)
    eaten = sum(appetite(game, r.unit) for r in regiments)
    tax = round(tax * game.data.factions[fid]["income_mult"])
    return Balance(tax, upkeep, round(food * game.data.map["seasons"][season]["food"]), eaten)


# --- what may be built or recruited, and why not ------------------------------------------

def can_manage(game, fid, pid):
    """Reason the faction cannot build or recruit in `pid`, or None if it can."""
    p = game.provinces[pid]
    if p.owner != fid:
        return "Not your province"
    if game.has_enemy_army(fid, pid) or p.besieged_by is not None:
        return "Enemies at the gates"
    return None


def building_blocker(game, fid, pid, bid):
    reason = can_manage(game, fid, pid)
    if reason:
        return reason
    p = game.provinces[pid]
    b = game.data.buildings[bid]
    if bid in p.buildings:
        return "Already built"
    if p.construction:
        return "Already building"
    if len(p.buildings) >= game.rules["building_slots"]:
        return "No free slot"
    if "terrain" in b and p.terrain not in b["terrain"]:
        return f"Not on {game.data.terrain[p.terrain]['name'].lower()}"
    if b.get("walls") and p.walls:
        return "Already walled"
    if game.treasury[fid].gold < b["cost"]:
        return "Not enough gold"
    return None


def unit_blocker(game, fid, pid, uid):
    reason = can_manage(game, fid, pid)
    if reason:
        return reason
    u = game.data.units[uid]
    p = game.provinces[pid]
    if u["faction"] != fid or u["tier"] == 0:
        return "Not one of yours"
    if u["tier"] >= 2 and "barracks" not in p.buildings:
        return "Needs Barracks"
    if u["tier"] >= 3 and game.capital_of(fid) != pid:
        return "Capital only"
    if u["ability"] == "hero" and hero_taken(game, fid, uid):
        return "Already serves you"
    if len(p.recruits) >= game.rules["recruits_per_turn"]:
        return "Training grounds full"
    if game.treasury[fid].gold < u["cost"]:
        return "Not enough gold"
    return None


def hero_taken(game, fid, uid):
    in_armies = any(r.unit == uid for a in game.armies_of(fid) for r in a.regiments)
    queued = any(uid in p.recruits for p in game.provinces_of(fid))
    return in_armies or queued


def recruitable_units(game, fid):
    return [uid for uid, u in game.data.units.items() if u["faction"] == fid and u["tier"] > 0]
