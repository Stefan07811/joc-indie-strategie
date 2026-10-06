"""Relations between the legends: war, peace and alliance.

- At **war** you may march into each other's land and fight.
- At **peace** you may not enter each other's provinces or attack each other's armies.
  Making peace starts a truce; declaring war during it is treachery, and everyone remembers.
- **Allies** march freely through each other's land and defend each other: whoever declares war
  on one of them is at war with the other too.
Neutral land and the Outlaws are always fair game.
"""

from dataclasses import dataclass

from .legends import REBELS

WAR, PEACE, ALLIANCE = "war", "peace", "alliance"


@dataclass
class DiplomacyChange:
    kind: str  # "war", "peace", "alliance" or "break" (an alliance ends in peace)
    faction: str  # who acted
    other: str
    treachery: bool = False


@dataclass
class Proposal:
    kind: str  # "peace" or "alliance"
    faction: str  # who proposes
    other: str  # who must answer
    gold: int = 0  # offered along with a peace


class DiplomacyError(ValueError):
    pass


def key(a, b):
    return frozenset((a, b))


def rules(game):
    return game.data.map["diplomacy"]


def setup(game):
    """Starting relations between the playable factions."""
    playable = [f for f, d in game.data.factions.items() if d["playable"]]
    for i, a in enumerate(playable):
        for b in playable[i + 1:]:
            game.relations[key(a, b)] = rules(game)["start"]
    for a, b in rules(game)["start_wars"]:
        game.relations[key(a, b)] = WAR
        game.war_since[key(a, b)] = 0


def relation(game, a, b):
    if a == b:
        return "self"
    if a is None or b is None or REBELS in (a, b):
        return WAR
    return game.relations.get(key(a, b), WAR)


def never_allied(game, a, b):
    return any({a, b} == set(pair) for pair in rules(game)["never_allied"])


def in_truce(game, a, b):
    return game.round < game.truce_until.get(key(a, b), 0)


def allies_of(game, fid):
    return [f for f in game.turn_order if relation(game, fid, f) == ALLIANCE]


def at_war_with(game, fid):
    return [f for f in game.turn_order if f != fid and relation(game, fid, f) == WAR]


def shares_border(game, a, b):
    return any(game.provinces[n].owner == b for p in game.provinces_of(a) for n in p.neighbors)


def might(game, fid):
    """Rough military strength of a faction: its armies, plus half its garrisons."""
    armies = sum(game.strength(a.regiments) for a in game.armies_of(fid))
    garrisons = sum(game.strength(p.garrison) for p in game.provinces_of(fid))
    return armies + garrisons / 2


# --- what an AI thinks of another faction --------------------------------------------------

def attitude(game, fid, other):
    """How `fid` feels about `other`: (score, [(reason, points), ...]). Above ~30 is friendly."""
    r = rules(game)
    parts = []
    personality = game.data.factions[fid].get("ai", {})
    if personality.get("friendliness"):
        parts.append((f"{personality['personality']} nature", personality["friendliness"]))
    if never_allied(game, fid, other):
        parts.append(("Ancient enemies", -50))
    rel = relation(game, fid, other)
    if rel == ALLIANCE:
        parts.append(("Allies", 20))
    elif rel == WAR:
        parts.append(("At war", -10))
    if (other, fid) in game.grudges:
        parts.append(("Betrayed us", -r["grudge_penalty"]))
    if game.treachery.get(other):
        parts.append(("Breaks treaties", -r["treachery_penalty"] * game.treachery[other]))
    if shares_border(game, fid, other):
        parts.append(("Shared border", -10))
    if set(at_war_with(game, fid)) & set(at_war_with(game, other)) - {fid, other}:
        parts.append(("Common enemy", 20))
    if game.heart_turns.get(other, 0):
        parts.append(("Holds the Heart", -8 * game.heart_turns[other]))
    lead = len(game.provinces_of(other)) - 6
    if lead > 0:
        parts.append(("Too powerful", -4 * lead))
    return sum(v for _, v in parts), parts


# --- actions ---------------------------------------------------------------------------------

def declare_war(game, fid, other):
    if relation(game, fid, other) == WAR:
        raise DiplomacyError("Already at war")
    treachery = relation(game, fid, other) == ALLIANCE or in_truce(game, fid, other)
    if treachery:
        game.treachery[fid] = game.treachery.get(fid, 0) + 1
        game.grudges.add((other, fid))
    _set(game, fid, other, WAR)
    word = "betray" if treachery else "declare war on"
    game._event(DiplomacyChange("war", fid, other, treachery),
                f"{game.faction_name(fid)} {word} {game.faction_name(other, True)}!")
    # allies honour their pact against the aggressor
    for ally in allies_of(game, other):
        if ally == fid or relation(game, ally, fid) == WAR:
            continue
        if relation(game, ally, fid) == ALLIANCE:
            _set(game, ally, fid, PEACE)
        _set(game, ally, fid, WAR)
        game._event(DiplomacyChange("war", ally, fid),
                    f"{game.faction_name(ally)} stand by {game.faction_name(other, True)} "
                    f"and go to war with {game.faction_name(fid, True)}.")


def make_peace(game, fid, other, gold=0):
    gold = max(0, min(gold, game.treasury[fid].gold))
    game.treasury[fid].gold -= gold
    game.treasury[other].gold += gold
    _set(game, fid, other, PEACE)
    game.truce_until[key(fid, other)] = game.round + rules(game)["truce_turns"]
    _withdraw(game, fid, other)
    paid = f", paying {gold} gold" if gold else ""
    game._event(DiplomacyChange("peace", fid, other),
                f"{game.faction_name(fid)} make peace with {game.faction_name(other, True)}{paid}.")


def make_alliance(game, fid, other):
    _set(game, fid, other, ALLIANCE)
    game.truce_until[key(fid, other)] = game.round + rules(game)["truce_turns"]
    game._event(DiplomacyChange("alliance", fid, other),
                f"{game.faction_name(fid)} and {game.faction_name(other, True)} swear an alliance.")


def break_alliance(game, fid, other):
    if relation(game, fid, other) != ALLIANCE:
        raise DiplomacyError("Not allies")
    _set(game, fid, other, PEACE)
    _withdraw(game, fid, other)
    game._event(DiplomacyChange("break", fid, other),
                f"{game.faction_name(fid)} end their alliance with {game.faction_name(other, True)}.")


def proposal_blocker(game, proposal):
    """Why this proposal cannot be made right now, or None."""
    a, b = proposal.faction, proposal.other
    if b not in game.turn_order or a not in game.turn_order:
        return "They are gone"
    rel = relation(game, a, b)
    if proposal.kind == "peace" and rel != WAR:
        return "Not at war"
    if proposal.kind == "alliance":
        if rel != PEACE:
            return "Must be at peace first"
        if never_allied(game, a, b):
            return "They will never ally with you"
        if set(at_war_with(game, b)) & set(allies_of(game, a)):
            return "At war with one of your allies"
    asked = game.last_proposal.get((a, b, proposal.kind))
    if asked is not None and game.round - asked < rules(game)["proposal_cooldown"]:
        return "Asked too recently"
    return None


def propose(game, proposal):
    """Offer peace or an alliance. An AI answers at once (True/False); a human answers later (None)."""
    reason = proposal_blocker(game, proposal)
    if reason:
        raise DiplomacyError(reason)
    game.last_proposal[(proposal.faction, proposal.other, proposal.kind)] = game.round
    if proposal.other in game.ai:
        accepted = game.ai[proposal.other].consider(game, proposal)
        settle(game, proposal, accepted)
        return accepted
    game.proposals.append(proposal)
    game.events.append(proposal)
    return None


def answer(game, proposal, accept):
    """The human player answers a pending proposal."""
    game.proposals.remove(proposal)
    if accept and proposal_blocker(game, proposal) not in (None, "Asked too recently"):
        return False  # things changed while the letter was on its way
    settle(game, proposal, accept)
    return accept


def settle(game, proposal, accepted):
    a, b = proposal.faction, proposal.other
    if not accepted:
        game.log.append(f"{game.faction_name(b)} refuse the {proposal.kind} offered by {game.faction_name(a, True)}.")
        return
    if proposal.kind == "peace":
        make_peace(game, a, b, proposal.gold)
    else:
        make_alliance(game, a, b)


def _withdraw(game, a, b):
    """Once at peace, armies standing on the other's land go home."""
    for army in list(game.armies.values()):
        p = game.provinces[army.province]
        if {army.faction, p.owner} == {a, b}:
            game._retreat(army, None)


def _set(game, a, b, rel):
    k = key(a, b)
    if rel == WAR and game.relations.get(k) != WAR:
        game.war_since[k] = game.round
    game.relations[k] = rel
