"""The words behind the tooltips: what a regiment, a building, a number on the panel means."""

from ..game import diplomacy, economy, generals, legends
from . import theme


def unit(game, uid, regiment=None):
    u = game.data.units[uid]
    lines = [u["name"]]
    if u.get("description"):
        lines.append((u["description"], theme.TEXT_DIM))
    stats = f"Attack {u['attack']}  ·  Defence {u['defense']}  ·  Morale {u['morale']}  ·  Speed {u['speed']}"
    if regiment is not None:
        lines.append(f"Strength {round(regiment.hp)} / {u['hp']}")
        if regiment.rank:
            bonus = round(generals.VETERAN_BONUS * 100 * regiment.rank)
            lines.append((f"Veteran, {regiment.rank} chevron{'s' if regiment.rank > 1 else ''}: +{bonus}% attack "
                          f"and defence, +{generals.VETERAN_MORALE * regiment.rank} morale", theme.GOLD))
    else:
        lines.append(f"Strength {u['hp']}")
    lines.append(stats)
    lines.append((f"Cost {u['cost']} gold  ·  upkeep {u['upkeep']} gold and {economy.appetite(game, uid)} food",
                  theme.GOLD))
    if u["ability"]:
        a = game.data.abilities[u["ability"]]
        lines.append((f"{a['name']}: {a['description']}", theme.HIGHLIGHT))
    return lines


def ability(game, aid):
    a = game.data.abilities[aid]
    return [a["name"], a["description"]]


def building(game, bid):
    b = game.data.buildings[bid]
    lines = [b["name"], b.get("description", "")]
    lines.append((f"{b['cost']} gold  ·  {b['turns']} season{'s' if b['turns'] != 1 else ''} to build", theme.GOLD))
    return lines


def gold(game):
    bal = economy.balance(game, game.player)
    lines = ["Gold", ("Paid each season: taxes in, upkeep out.", theme.TEXT_DIM),
             (f"Taxes from provinces and buildings  +{bal.tax}", theme.GOOD)]
    if bal.interest:
        lines.append((f"Interest on the hoard  +{bal.interest}", theme.GOOD))
    lines.append((f"Upkeep of the armies  -{bal.upkeep}", theme.DANGER))
    lines.append((f"Each season  {bal.gold:+}", theme.GOLD))
    return lines


def food(game):
    bal = economy.balance(game, game.player)
    mult = game.data.map["seasons"][game.season]["food"]
    return ["Food", (f"Harvest this {game.season.lower()} (x{mult:g})  +{bal.food_made}", theme.GOOD),
            (f"Eaten by the armies  -{bal.food_eaten}", theme.DANGER),
            (f"Each season  {bal.food:+}", theme.GOLD),
            ("When the granaries are empty, armies lose men.", theme.TEXT_DIM)]


def conquest(game):
    need = game.victory_rules["conquest_provinces"]
    return ["Conquest victory", f"Hold {need} of the {len(game.provinces)} provinces to rule the Carpathians."]


def heart(game):
    turns = game.victory_rules["heart_turns"]
    return ["Legendary victory",
            f"Hold the Heart of the Mountains and your capital for {turns} seasons in a row.",
            ("Everyone turns on whoever holds it for long.", theme.TEXT_DIM)]


def order(game, p):
    value, parts = legends.public_order(game, p)
    lines = ["Public order", ("Below zero, the province may rise in revolt.", theme.TEXT_DIM)]
    for name, points in parts:
        lines.append((f"{name}  {points:+}", theme.GOOD if points >= 0 else theme.DANGER))
    lines.append((f"Total  {value:+}", theme.GOLD))
    return lines


def attitude(game, fid):
    score, parts = diplomacy.attitude(game, fid, game.player)
    lines = [f"What {game.faction_name(fid, True)} think of you",
             ("Above +20 they may accept an alliance; below -20 they look for war.", theme.TEXT_DIM)]
    for name, points in parts:
        lines.append((f"{name}  {points:+}", theme.GOOD if points >= 0 else theme.DANGER))
    lines.append((f"Total  {score:+}", theme.GOLD))
    return lines


RELATIONS = {
    "war": ["At war", "Armies may enter each other's land and fight."],
    "peace": ["At peace", "Borders are closed: neither may enter the other's land. Breaking peace during a truce "
                          "is treachery."],
    "alliance": ["Allies", "Open borders; each joins the other's defensive wars. Breaking it is treachery."],
}


def general(game, a):
    lines = [a.general + (f"  ·  rank {a.rank}" if a.rank else ""),
             (f"Rank {a.rank}: +{round(generals.RANK_ATTACK * 100 * a.rank)}% attack, holds longer"
              if a.rank else "Untried in battle.", theme.TEXT_DIM)]
    for trait in a.traits:
        t = game.data.traits[trait]
        lines.append((f"{t['name']}: {t['description']}", theme.GOOD if t["good"] else theme.DANGER))
    return lines


def army(game, a):
    lines = [a.general + (f"  ·  rank {a.rank}" if a.rank else ""),
             (f"{game.faction_name(a.faction)}  ·  {len(a.regiments)} regiments", theme.TEXT_DIM)]
    if a.traits:
        lines.append(("  ·  ".join(game.data.traits[t]["name"] for t in a.traits), theme.GOLD))
    if a.faction == game.player:
        lines.append(f"Movement left {a.moves_left} / {generals.moves(game, a)}")
    counts = {}
    for r in a.regiments:
        counts[r.unit] = counts.get(r.unit, 0) + 1
    for uid, n in counts.items():
        lines.append(f"{n} x {game.data.units[uid]['name']}")
    return lines


def province(game, p):
    terrain = game.data.terrain[p.terrain]
    lines = [p.name, (f"{terrain['name']}  ·  {game.faction_name(p.owner)}", theme.TEXT_DIM)]
    if p.garrison:
        lines.append(f"Garrison: {len(p.garrison)} regiments" + ("  ·  walls" if p.walls else ""))
    return lines
