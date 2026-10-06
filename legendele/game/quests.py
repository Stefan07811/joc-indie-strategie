"""Quests of legend (data/quests.json): each realm has a few, and each brings a hero of the old
tales to its side when fulfilled.

Goals:
  win_battles   win this many battles from the start of the campaign
  take_from     take this many provinces from a given legend
  gold          have this much gold in the treasury
  abductions    carry off this many heirs (the Dragonkin)
  provinces     rule this many provinces (vassals included)
  terrain       hold this many provinces of a terrain
The hero joins the realm's capital (or its first province) the season after the quest is done.
"""

from dataclasses import dataclass


@dataclass
class QuestDone:
    faction: str
    quest: str
    hero: str


def of(game, fid):
    return [q for q, d in game.data.quests.items() if d["faction"] == fid]


def done(game, fid, qid):
    return qid in game.quests_done.get(fid, [])


def progress(game, fid, qid):
    """(how far, how far it must go) for one quest."""
    goal = game.data.quests[qid]["goal"]
    stats = game.stats.get(fid, {})
    kind, need = goal["kind"], goal["count"]
    if kind == "win_battles":
        have = stats.get("won", 0)
    elif kind == "take_from":
        have = stats.get(f"from_{goal['faction']}", 0)
    elif kind == "gold":
        have = game.treasury[fid].gold if fid in game.treasury else 0
    elif kind == "abductions":
        have = stats.get("abducted", 0)
    elif kind == "provinces":
        have = game.realm_size(fid)
    elif kind == "terrain":
        have = sum(1 for p in game.provinces_of(fid) if p.terrain == goal["terrain"])
    else:
        have = 0
    return min(have, need), need


def season(game):
    """Quests fulfilled this season bring their heroes."""
    for fid in game.turn_order:
        for qid in of(game, fid):
            if done(game, fid, qid):
                continue
            have, need = progress(game, fid, qid)
            if have < need:
                continue
            game.quests_done.setdefault(fid, []).append(qid)
            q = game.data.quests[qid]
            home = game.capital_of(fid)
            if home not in game.provinces or game.provinces[home].owner != fid:
                mine = game.provinces_of(fid)
                home = mine[0].id if mine else None
            if home:
                game.provinces[home].recruits.append(q["hero"])
            hero = game.data.units[q["hero"]]["name"]
            game._event(QuestDone(fid, qid, q["hero"]),
                        f"{q['title']}: {hero} rides to join {game.faction_name(fid, True)}!")
