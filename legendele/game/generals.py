"""Generals and veterans: the men who live through the war remember it.

A general earns experience in battle and climbs the ranks (up to 8 stars); every rank makes his army
strike a little harder and hold a little longer. Deeds give him traits, good or bad: win while
outnumbered and he may become Brave, storm walls and he may become a Siege Master, lose and he may
turn Coward. A general can fall in battle; a lieutenant then takes command.

Regiments that survive battles become veterans (up to 3 chevrons): harder blows, better guard and
steadier nerves.
"""

RANKS = (0, 3, 7, 12, 18, 25, 33, 42, 52)  # experience needed for each rank (0 to 8 stars)
RANK_ATTACK = 0.03  # per star
RANK_RESOLVE = 0.01
MAX_TRAITS = 3
OPPOSITES = {("brave", "coward"), ("swift", "drunkard"), ("frugal", "greedy"), ("beloved", "cruel")}

VETERAN_XP = (0, 3, 7, 12)  # experience for each chevron (0 to 3)
VETERAN_BONUS = 0.08  # attack and defence per chevron
VETERAN_MORALE = 5  # morale per chevron

FALL_CHANCE = {"won": 0.03, "lost": 0.10}


# --- generals ----------------------------------------------------------------------------------

def rank_for(xp):
    return max(i for i, need in enumerate(RANKS) if xp >= need)


def next_rank_xp(army):
    return RANKS[army.rank + 1] if army.rank + 1 < len(RANKS) else None


def _traits(game, army):
    return [game.data.traits[t] for t in army.traits if t in game.data.traits]


def attack_mult(game, army, assault=False):
    if army is None:
        return 1.0
    mult = 1 + RANK_ATTACK * army.rank
    for t in _traits(game, army):
        mult *= t.get("attack", 1.0)
        if assault:
            mult *= t.get("assault", 1.0)
    return mult


def defense_mult(game, army):
    mult = 1.0
    for t in _traits(game, army) if army else ():
        mult *= t.get("defense", 1.0)
    return mult


def resolve_bonus(game, army):
    if army is None:
        return 0.0
    return RANK_RESOLVE * army.rank + sum(t.get("resolve", 0.0) for t in _traits(game, army))


def creature_bane(game, army):
    mult = 1.0
    for t in _traits(game, army) if army else ():
        mult *= t.get("creatures", 1.0)
    return mult


def moves(game, army):
    from .techs import bonus
    return max(1, game.data.map["army_moves"] + sum(t.get("moves", 0) for t in _traits(game, army))
               + bonus(game, army.faction, "moves"))


def upkeep_mult(game, army):
    mult = 1.0
    for t in _traits(game, army):
        mult *= t.get("upkeep", 1.0)
    return mult


def winter_hardy(game, army):
    return any(t.get("winter") for t in _traits(game, army))


def order(game, pid, fid):
    """Order the generals camped in a province bring to it (Beloved +, Cruel -)."""
    return sum(t.get("order", 0) for a in game.armies_in(pid) if a.faction == fid for t in _traits(game, a))


def give_trait(game, army, trait, quiet=False):
    """Add a trait if there is room and it does not clash; returns True if he got it."""
    if trait in army.traits or len(army.traits) >= MAX_TRAITS or trait not in game.data.traits:
        return False
    if any({trait, t} == set(pair) for pair in OPPOSITES for t in army.traits):
        return False
    fresh = army.moves_left == moves(game, army)
    army.traits.append(trait)
    # a fresh army marches by its new nature; one already on the road keeps what is left, up to that
    army.moves_left = moves(game, army) if fresh else min(army.moves_left, moves(game, army))
    if army.faction == game.player and not quiet:
        t = game.data.traits[trait]
        game.log.append(f"{army.general} is now known as {t['name']}: {t['description']}")
    return True


def birth(game, army):
    """A new general may come with a trait of his own."""
    rng = game.rng
    if rng.random() < 0.5:
        good = [k for k, t in game.data.traits.items() if t["good"]]
        bad = [k for k, t in game.data.traits.items() if not t["good"]]
        pool = good if rng.random() < 0.7 else bad
        if pool:
            give_trait(game, army, rng.choice(sorted(pool)), quiet=True)


def after_battle(game, army, won, *, outnumbered=False, assault=False, defending=False, versus_creatures=False):
    """Experience, rank and perhaps a new trait for the general of `army`; he may also fall."""
    if army is None or army.id not in game.armies:
        return
    rng = game.rng
    army.xp += (3 + (2 if outnumbered else 0)) if won else 1
    new_rank = rank_for(army.xp)
    if new_rank > army.rank:
        army.rank = new_rank
        if army.faction == game.player:
            game.log.append(f"{army.general} rises to rank {army.rank}.")
    chances = []
    if won:
        chances += [("brave", 0.35 if outnumbered else 0.0), ("siege_master", 0.3 if assault else 0.0),
                    ("monster_slayer", 0.25 if versus_creatures else 0.0), ("tactician", 0.12),
                    ("stalwart", 0.15 if defending else 0.0), ("inspiring", 0.06), ("cruel", 0.04),
                    ("winter_warrior", 0.2 if game.season == "Winter" else 0.0), ("reckless", 0.04)]
    else:
        chances += [("coward", 0.18), ("stalwart", 0.05 if defending else 0.0)]
    for trait, p in chances:
        if p and rng.random() < p and give_trait(game, army, trait):
            break
    if rng.random() < FALL_CHANCE["won" if won else "lost"]:
        fall(game, army)


def fall(game, army):
    """The general dies; a lieutenant takes the army over."""
    old = army.general
    army.general = game._new_general(army.faction)
    army.xp, army.rank, army.traits = 0, 0, []
    birth(game, army)
    from .state import GeneralFell
    game._event(GeneralFell(army.faction, old, army.general, army.province),
                f"{old} of {game.faction_name(army.faction, True)} falls in battle; {army.general} takes command.")


def idle(game):
    """Each season, generals camped at home may pick up habits."""
    rng = game.rng
    for army in game.armies.values():
        if game.provinces[army.province].owner == army.faction and rng.random() < 0.015:
            give_trait(game, army, rng.choice(("drunkard", "beloved", "greedy", "frugal")))


# --- veterans ----------------------------------------------------------------------------------

def veteran_mult(regiment):
    return 1 + VETERAN_BONUS * getattr(regiment, "rank", 0)


def season_of_battle(regiments, won):
    """Experience for the regiments that lived through a battle."""
    for r in regiments:
        r.xp += 2 if won else 1
        r.rank = max(i for i, need in enumerate(VETERAN_XP) if r.xp >= need)
