"""Computer-controlled factions.

M2 behaviour: every army picks the most valuable province it can realistically take
(close, weakly held, ideally the Heart or an enemy capital), checks its odds with the same
battle maths the game uses, and marches there. Besiegers storm the walls once the odds are
good, otherwise they let hunger do the work. Smarter planning and personalities come in M5.
"""

MIN_SHARE_LEFT = 0.45  # only fight battles we expect to win with at least this much of the army left


class SimpleAI:
    def __init__(self, faction):
        self.faction = faction

    def take_turn(self, game):
        for army_id in sorted(a.id for a in game.armies_of(self.faction)):
            if game.over:
                return
            army = game.armies.get(army_id)
            if army is None:
                continue
            if game.besieging(army):
                self._siege(game, army)
            else:
                self._march(game, army)

    def _siege(self, game, army):
        forecast = game.forecast(army, army.province)
        if forecast and forecast[0] and forecast[1] >= MIN_SHARE_LEFT:
            game.assault(army.id)

    def _march(self, game, army):
        target = self._goal(game, army)
        if target is None or target == army.province:
            return
        reach = game.reachable(army)
        if target in reach:
            if game.has_enemy_army(self.faction, target):
                wins, share_left = game.forecast(army, target)
                if not wins or share_left < MIN_SHARE_LEFT:
                    return  # wait for a better moment
            game.move_army(army.id, target)
            return
        # Otherwise step toward it, through friendly land or provinces we can take without a fight.
        dist_to_goal = game.distances(self.faction, target)
        steps = [pid for pid in reach if game.passable(self.faction, pid) or not game.defended(self.faction, pid)]
        if not steps:
            return
        dest = min(steps, key=lambda pid: (dist_to_goal.get(pid, float("inf")), reach[pid].cost, pid))
        if dist_to_goal.get(dest, float("inf")) < dist_to_goal.get(army.province, float("inf")):
            game.move_army(army.id, dest)

    def _goal(self, game, army):
        dist = game.distances(self.faction, army.province)
        best, best_score = None, 0.0
        for p in game.provinces.values():
            if p.owner == self.faction and not game.has_enemy_army(self.faction, p.id):
                continue
            if any(a.faction == self.faction and a.id != army.id and game.besieging(a) for a in game.armies_in(p.id)):
                continue  # a comrade is already starving it out
            value = self._value(game, p)
            if not self._can_take(game, army, p):
                continue
            score = value / (1 + dist[p.id])
            if score > best_score or (score == best_score and best and p.id < best):
                best, best_score = p.id, score
        return best

    def _value(self, game, p):
        if p.owner == self.faction:
            return 8.0  # an enemy army on our own soil
        if p.special == "heart":
            return 6.0
        if p.owner and game.capital_of(p.owner) == p.id:
            return 5.0
        return 3.0 if p.owner is None else 3.5

    def _can_take(self, game, army, p):
        """Would `army` beat what holds province `p` (its armies, and later its garrison)?"""
        ours = game.strength(army.regiments)
        enemies = [a for a in game.armies_in(p.id) if a.faction != self.faction]
        theirs = sum(game.strength(a.regiments) for a in enemies)
        if p.owner != self.faction and p.garrison:
            theirs += game.strength(p.garrison) * (1.5 if p.walls else 1.0) * 0.7  # sieges wear them down
        return theirs == 0 or ours >= theirs * 1.1
