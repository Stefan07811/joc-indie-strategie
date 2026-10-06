"""Traditions: what a realm learns over the years (data/techs.json).

One tradition is studied at a time: its gold is paid at the start and it is learnt after a few
seasons. Each brings a lasting bonus to the whole realm:
  income / food / upkeep / heal   multipliers on taxes, harvests, the armies' pay, healing
  attack / defense                multipliers on the realm's blows and guard in battle
  resolve                         added to how long its regiments hold
  order / moves / recruits        added to every province's order, every army's movement, the
                                  regiments each province can train at once
  siege                           seasons of siege works gained (ladders and rams come sooner)
"""

MULTIPLIERS = ("income", "food", "upkeep", "heal", "attack", "defense")


def known(game, fid):
    return game.techs.get(fid, [])


def available(game, fid):
    """Traditions `fid` could start studying now (whatever the cost)."""
    out = []
    for tid, t in game.data.techs.items():
        if t.get("faction", fid) != fid or tid in known(game, fid):
            continue
        if all(r in known(game, fid) for r in t.get("requires", ())):
            out.append(tid)
    return out


def blocker(game, fid, tid):
    """Why `fid` cannot start studying `tid` now, or None."""
    t = game.data.techs.get(tid)
    if t is None or t.get("faction", fid) != fid:
        return "Not one of your traditions"
    if tid in known(game, fid):
        return "Already known"
    missing = [game.data.techs[r]["name"] for r in t.get("requires", ()) if r not in known(game, fid)]
    if missing:
        return "Needs " + ", ".join(missing)
    if game.studying.get(fid):
        return "Already studying"
    if game.treasury[fid].gold < t["cost"]:
        return "Not enough gold"
    return None


def start(game, fid, tid):
    reason = blocker(game, fid, tid)
    if reason:
        raise ValueError(reason)
    t = game.data.techs[tid]
    game.treasury[fid].gold -= t["cost"]
    game.studying[fid] = {"tech": tid, "turns_left": t["turns"]}


def season(game):
    """Studies advance; finished traditions are learnt."""
    for fid in game.turn_order:
        study = game.studying.get(fid)
        if not study:
            continue
        study["turns_left"] -= 1
        if study["turns_left"] <= 0:
            game.techs.setdefault(fid, []).append(study["tech"])
            del game.studying[fid]
            if fid == game.player:
                game.log.append(f"Your scholars complete {game.data.techs[study['tech']]['name']}.")
    for fid in game.turn_order:
        if fid != game.player or game.spectate:
            ai_study(game, fid)


def bonus(game, fid, key):
    """The realm's total bonus of one kind: a product for multipliers, a sum for the rest."""
    if not fid or fid not in game.techs:
        return 1.0 if key in MULTIPLIERS else 0
    values = [game.data.techs[t][key] for t in game.techs[fid] if key in game.data.techs[t]]
    if key in MULTIPLIERS:
        out = 1.0
        for v in values:
            out *= v
        return out
    return sum(values)


def effects(game, tid):
    """A short list of what a tradition gives, for the screen."""
    t = game.data.techs[tid]
    words = {"income": "taxes", "food": "food", "upkeep": "upkeep", "heal": "healing", "attack": "attack",
             "defense": "defence"}
    out = []
    for key, word in words.items():
        if key in t:
            out.append(f"{round((t[key] - 1) * 100):+}% {word}")
    for key, word in (("resolve", "steadiness"), ("order", "order"), ("moves", "movement"),
                      ("recruits", "training"), ("siege", "siege works")):
        if key in t:
            value = t[key]
            out.append(f"+{round(value * 100)}% {word}" if isinstance(value, float) else f"+{value} {word}")
    return out


def ai_study(game, fid):
    """The computer's scholars: the cheapest tradition it can afford with gold to spare."""
    if game.studying.get(fid):
        return
    options = sorted(available(game, fid), key=lambda t: (game.data.techs[t]["cost"], t))
    for tid in options:
        if game.treasury[fid].gold >= game.data.techs[tid]["cost"] + 150:
            start(game, fid, tid)
            return
