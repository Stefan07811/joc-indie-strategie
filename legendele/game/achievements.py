"""Achievements: deeds the player is remembered for, from one campaign to the next.

The rules here only say which deeds a campaign (or a custom battle) has earned; the player's profile
(profile.py) remembers them for good. Every check looks at the human player only, never in an
AI-only game.
"""

from dataclasses import dataclass

from . import diplomacy, foreign
from .agents import AgentDeed


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    secret: bool = False  # the description is hidden until it is earned


def _won(game):
    return game.winner is not None and game.winner.faction == game.player


def _stat(game, key):
    return game.stats.get(game.player, {}).get(key, 0)


def _deeds(events, kind):
    return [e for e in events if isinstance(e, kind)]


def _foe_beaten(game, events):
    for e in events:
        r = getattr(e, "result", None)
        if r is not None and type(e).__name__ == "Battle" and r.winning_faction == game.player \
                and foreign.is_power(game, r.losing_faction):
            return True
    return False


def _lowest_ebb(game):
    sizes = [snap["factions"].get(game.player, {}).get("provinces", 99) for snap in game.history]
    return min(sizes, default=99)


# id: (name, description, check(game, events) -> bool)
CAMPAIGN = {
    "first_blood": ("First Blood", "Win your first battle.", lambda g, e: _stat(g, "won") >= 1),
    "warlord": ("Warlord", "Win 25 battles in one campaign.", lambda g, e: _stat(g, "won") >= 25),
    "realm": ("A Realm Worth Ruling", "Rule 10 provinces.", lambda g, e: len(g.provinces_of(g.player)) >= 10),
    "heart": ("Heart of the Mountains", "Take the Heart of the Mountains.", lambda g, e: g.heart_holder() == g.player),
    "hero": ("Out of the Old Tales", "Fulfil a quest and win a hero of legend.",
             lambda g, e: len(g.quests_done.get(g.player, [])) >= 1),
    "every_tale": ("Every Tale Told", "Fulfil both quests of your legend in one campaign.",
                   lambda g, e: len(g.quests_done.get(g.player, [])) >= 2),
    "scholar": ("Keeper of Traditions", "Learn 5 traditions in one campaign.",
                lambda g, e: len(g.techs.get(g.player, [])) >= 5),
    "markets": ("Open Markets", "Trade with 3 legends at once.",
                lambda g, e: len(diplomacy.trade_partners(g, g.player)) >= 3),
    "wedding": ("A Royal Wedding", "Join your house to another by marriage.",
                lambda g, e: any(g.player in k for k in g.marriages)),
    "overlord": ("Bend the Knee", "Make another legend your vassal.",
                 lambda g, e: bool(diplomacy.vassals_of(g, g.player))),
    "kidnapper": ("A Princess for the Dragon", "Carry off a rival's heir.", lambda g, e: _stat(g, "abducted") >= 1),
    "spymaster": ("Spymaster", "Succeed at a deed in the shadows with an agent.",
                  lambda g, e: any(d.faction == g.player and d.success for d in _deeds(e, AgentDeed))),
    "raiders": ("Shield of the Land", "Defeat the raiders of a foreign power in battle.", _foe_beaten),
    "conquest": ("Conqueror", "Win a war by conquest.", lambda g, e: _won(g) and g.winner.kind == "conquest"),
    "legend": ("Living Legend", "Win a war by holding the Heart of the Mountains.",
               lambda g, e: _won(g) and g.winner.kind == "legend"),
    "brink": ("Back from the Brink", "Win a war after being down to a single province.",
              lambda g, e: _won(g) and _lowest_ebb(g) <= 1, True),
    "hard": ("Against All Odds", "Win a war on Hard or Legendary.",
             lambda g, e: _won(g) and g.difficulty in ("hard", "legendary")),
    "lots": ("Drawn by Lot", "Win a war with shuffled homelands.",
             lambda g, e: _won(g) and g.options.get("shuffle", False)),
    "kings": ("Age of Kings", "Win a war that begins in 1450.", lambda g, e: _won(g) and g.options.get("era") == 1450),
    "everyone": ("All Against One", "Win a war against all five rivals.",
                 lambda g, e: _won(g) and len(g.factions) >= 6),
}
# A victory with every legend; the last one is earned once all six are.
LEGENDS = ("voievodat", "zmei", "iele", "strigoi", "outlaws", "solomonari")
OTHER = {
    "lead": ("In the Thick of It", "Win a battle you lead yourself on the field."),
    "custom": ("Armchair General", "Win a custom battle."),
    "all_legends": ("Legends of the Carpathians", "Win a war with each of the six legends."),
}


def victory_id(fid):
    return f"win_{fid}"


def every(data):
    """All achievements, in the order the achievements screen shows them."""
    out = [Achievement(i, spec[0], spec[1], *spec[3:]) for i, spec in CAMPAIGN.items()]
    out += [Achievement(i, name, text) for i, (name, text) in OTHER.items() if i != "all_legends"]
    for fid in LEGENDS:
        if fid in data.factions:
            out.append(Achievement(victory_id(fid), f"Victory for {data.factions[fid]['name']}",
                                   f"Win a war leading {data.factions[fid]['name']}."))
    out.append(Achievement("all_legends", *OTHER["all_legends"]))
    return out


def campaign(game, events=(), known=()):
    """Achievement ids this campaign has earned now (that are not in `known` yet)."""
    if game.spectate:
        return []
    earned = [i for i, spec in CAMPAIGN.items() if i not in known and spec[2](game, events)]
    if _won(game):
        mine = victory_id(game.player)
        if mine not in known:
            earned.append(mine)
        wins = {victory_id(f) for f in LEGENDS if f in game.data.factions}
        if "all_legends" not in known and wins <= set(known) | set(earned):
            earned.append("all_legends")
    return earned
