"""Agents: the men and creatures who work in the shadows of the war.

A **spy** sees the armies standing in its province and next door (even the Fae hidden in the
woods) and can sabotage an enemy province: works set back, the garrison sickened. A **priest**
(a sorcerer, a herb witch, a necromancer, after the legend) calms one of its own provinces, or stirs
up unrest in a foe's. Agents go anywhere, three provinces a season; an action takes the rest of the
season, and a failed one may cost the agent its life.
"""

import heapq
from dataclasses import dataclass

KINDS = ("spy", "priest")
COST = {"spy": 80, "priest": 90}
MAX_EACH = 2
MOVES = 3
NAMES = {
    "spy": {"voievodat": "Spy", "zmei": "Imp Spy", "iele": "Will-o'-the-wisp", "strigoi": "Night Crow",
            "outlaws": "Lookout", "solomonari": "Storm Raven"},
    "priest": {"voievodat": "Priest", "zmei": "Sorcerer", "iele": "Herb Witch", "strigoi": "Necromancer",
               "outlaws": "Wandering Monk", "solomonari": "Solomonar"},
}
ACTIONS = {
    # action: (agent kind, chance of success, chance of being caught on failure, description)
    "sabotage": ("spy", 0.5, 0.5, "Set back the works and sicken the garrison of an enemy province."),
    "calm": ("priest", 1.0, 0.0, "+2 order in one of your provinces for 3 seasons."),
    "unrest": ("priest", 0.55, 0.4, "-2 order in a rival's province for 3 seasons."),
}
SEASONS = 3


@dataclass
class Agent:
    id: int
    faction: str
    kind: str
    province: str
    moves_left: int = MOVES


@dataclass
class AgentDeed:
    faction: str
    kind: str
    action: str
    province: str
    victim: str | None
    success: bool
    caught: bool


def name(fid, kind):
    return NAMES[kind].get(fid, kind.capitalize())


def of(game, fid, kind=None):
    return [a for a in game.agents.values() if a.faction == fid and (kind is None or a.kind == kind)]


def hire_blocker(game, fid, kind):
    if len(of(game, fid, kind)) >= MAX_EACH:
        return f"At most {MAX_EACH}"
    if game.treasury[fid].gold < COST[kind]:
        return "Not enough gold"
    if not game.provinces_of(fid):
        return "No land to hire in"
    return None


def hire(game, fid, kind, pid=None):
    reason = hire_blocker(game, fid, kind)
    if reason:
        raise ValueError(reason)
    if pid is None or game.provinces[pid].owner != fid:
        capital = game.capital_of(fid)
        pid = capital if capital in game.provinces and game.provinces[capital].owner == fid \
            else game.provinces_of(fid)[0].id
    game.treasury[fid].gold -= COST[kind]
    agent = Agent(game._next_agent_id, fid, kind, pid)
    game._next_agent_id += 1
    game.agents[agent.id] = agent
    return agent


def reachable(game, agent):
    """{province: cost} the agent can reach this season (one point a province, anywhere)."""
    best = {agent.province: 0}
    queue = [(0, agent.province)]
    while queue:
        cost, pid = heapq.heappop(queue)
        if cost > best[pid]:
            continue
        for nid in game.provinces[pid].neighbors:
            if cost + 1 <= agent.moves_left and cost + 1 < best.get(nid, 99):
                best[nid] = cost + 1
                heapq.heappush(queue, (cost + 1, nid))
    del best[agent.province]
    return best


def move(game, agent_id, pid):
    agent = game.agents[agent_id]
    cost = reachable(game, agent).get(pid)
    if cost is None:
        raise ValueError("Too far this season")
    agent.moves_left -= cost
    agent.province = pid


def _friendly(game, fid, pid):
    return game.friendly_land(fid, pid)


def action_blocker(game, agent, action):
    kind = ACTIONS[action][0]
    if agent.kind != kind:
        return "Not this agent's work"
    if agent.moves_left <= 0:
        return "Needs a fresh season"
    p = game.provinces[agent.province]
    if action == "calm":
        return None if p.owner == agent.faction else "Only in your own provinces"
    if p.owner is None or _friendly(game, agent.faction, p.id):
        return "Only in a rival's province"
    return None


def actions(game, agent):
    """[(action, blocker or None)] this agent could try where it stands."""
    return [(a, action_blocker(game, agent, a)) for a, spec in ACTIONS.items() if spec[0] == agent.kind]


def act(game, agent_id, action):
    """Try a deed. Returns the AgentDeed (also logged as an event)."""
    agent = game.agents[agent_id]
    reason = action_blocker(game, agent, action)
    if reason:
        raise ValueError(reason)
    _, chance, risk, _ = ACTIONS[action]
    p = game.provinces[agent.province]
    agent.moves_left = 0
    success = game.rng.random() < chance
    caught = not success and game.rng.random() < risk
    who = name(agent.faction, agent.kind)
    if success:
        if action == "calm":
            p.mods.append([f"{who}'s blessing", 2, game.round + SEASONS])
        elif action == "unrest":
            p.mods.append([f"Stirred up by a {who.lower()}", -2, game.round + SEASONS])
        elif action == "sabotage":
            if p.construction:
                p.construction["turns_left"] += 2
            for r in p.garrison:
                r.hp *= 0.7
            p.garrison[:] = [r for r in p.garrison if r.hp >= 8]
    if caught:
        del game.agents[agent_id]
    verdict = {"calm": "calms the people of", "unrest": "stirs up unrest in", "sabotage": "sabotages"}[action]
    if success:
        line = f"A {who.lower()} of {game.faction_name(agent.faction, True)} {verdict} {p.name}."
    else:
        line = f"A {who.lower()} of {game.faction_name(agent.faction, True)} fails in {p.name}" + \
               (" and is caught." if caught else ".")
    deed = AgentDeed(agent.faction, agent.kind, action, p.id, p.owner, success, caught)
    game._event(deed, line)
    return deed


def sees(game, viewer, pid):
    """Does one of `viewer`'s spies watch this province (from it or next door)?"""
    p = game.provinces[pid]
    near = {pid, *p.neighbors}
    return any(a.faction == viewer and a.kind == "spy" and a.province in near for a in game.agents.values())


def season(game):
    """Fresh legs for every agent; those of fallen realms melt away."""
    for agent in list(game.agents.values()):
        if agent.faction in game.eliminated:
            del game.agents[agent.id]
        else:
            agent.moves_left = MOVES


# --- the computer's agents -------------------------------------------------------------------

def ai_hire(game, fid):
    """A spy and a priest, from the second year on, once the treasury allows (before the builders and
    recruiters spend it all)."""
    if game.round < 4:
        return
    for kind in KINDS:
        if not of(game, fid, kind) and game.treasury[fid].gold > 150 and hire_blocker(game, fid, kind) is None:
            hire(game, fid, kind)


def ai_turn(game, fid):
    """Calm the restless at home, stir up and sabotage the enemy."""
    from .legends import public_order
    enemies = {p.id for p in game.provinces.values()
               if p.owner and p.owner != fid and game.at_war(fid, p.owner)}
    for agent in list(of(game, fid)):
        if agent.kind == "priest":
            restless = [p.id for p in game.provinces_of(fid) if public_order(game, p)[0] < 1]
            targets = restless or sorted(enemies)
            action = "calm" if restless else "unrest"
        else:
            targets = sorted(enemies, key=lambda pid: (pid != game.capital_of(game.provinces[pid].owner), pid))
            action = "sabotage"
        if not targets:
            continue
        reach = reachable(game, agent)
        here = [t for t in targets if t == agent.province]
        if not here:
            near = [t for t in targets if t in reach]
            if near:
                move(game, agent.id, near[0])
            else:
                step = min(reach, key=lambda pid: min(game.distances(fid, pid).get(t, 99) for t in targets[:3]),
                           default=None)
                if step:
                    move(game, agent.id, step)
                continue
        if agent.id in game.agents and action_blocker(game, agent, action) is None \
                and (action == "calm" or game.rng.random() < 0.4):
            act(game, agent.id, action)
