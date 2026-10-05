"""Computer-controlled factions.

M1 behaviour: each army marches toward the nearest province its faction does not own,
preferring the Heart of the Mountains on ties. Real goals and risk evaluation come in M5.
"""


class SimpleAI:
    def __init__(self, faction):
        self.faction = faction

    def take_turn(self, game):
        for army in sorted(game.armies_of(self.faction), key=lambda a: a.id):
            target = self._goal(game, army)
            if target is None or target == army.province:
                continue
            reach = game.reachable(army)
            if not reach:
                continue
            # Step to the reachable province that leaves us closest to the goal.
            dist_to_goal = game.distances(self.faction, target)
            dest = min(reach, key=lambda pid: (dist_to_goal.get(pid, float("inf")), reach[pid].cost, pid))
            if dist_to_goal.get(dest, float("inf")) >= dist_to_goal.get(army.province, float("inf")):
                continue
            game.move_army(army.id, dest)
            game.log.append(f"{game.faction_name(self.faction)}: {army.general} marches to {game.provinces[dest].name}.")

    def _goal(self, game, army):
        dist = game.distances(self.faction, army.province)
        candidates = [
            p for p in game.provinces.values()
            if p.owner != self.faction and not game.blocked_for(self.faction, p.id)
        ]
        if not candidates:
            return None
        best = min(candidates, key=lambda p: (dist[p.id], p.special != "heart", p.id))
        return best.id
