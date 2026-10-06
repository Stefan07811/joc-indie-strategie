"""Pit equal-cost armies of each faction against each other on open ground (for balancing).

Results are averaged over several budgets, so that rounding (how many whole regiments fit)
does not decide the outcome.

    python tools/duel.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legendele.game import GameData  # noqa: E402
from legendele.game.battle import Regiment, Side, resolve  # noqa: E402

FACTIONS = ("voievodat", "zmei", "iele", "strigoi", "outlaws", "solomonari")


def army(data, fid, budget, tiers):
    """Spend `budget` round-robin on the faction's units of the given tiers (no heroes)."""
    units = sorted((u for u, d in data.units.items() if d["faction"] == fid and d["tier"] in tiers
                    and d["ability"] != "hero"), key=lambda u: data.units[u]["cost"])
    regiments, spent, i = [], 0, 0
    while units:
        u = units[i % len(units)]
        if spent + data.units[u]["cost"] > budget:
            units.remove(u)
            continue
        regiments.append(u)
        spent += data.units[u]["cost"]
        i += 1
    return regiments


def main():
    budgets = range(400, 1300, 100)
    data = GameData.load()
    for tiers, label in (((1,), "tier 1 only"), ((1, 2), "tiers 1-2")):
        print(f"\n{label}, 400-1200 gold each (row attacks column, % of fights won)")
        print(" " * 11 + "".join(f"{f[:9]:>10}" for f in FACTIONS))
        for a in FACTIONS:
            row = []
            for d in FACTIONS:
                wins = 0
                for seed, budget in ((s, b) for s in range(20) for b in budgets):
                    def side(fid, leader):
                        regs = [Regiment(u, data.units[u]["hp"]) for u in army(data, fid, budget, tiers)]
                        return Side(fid, regs, leader, creature=data.factions[fid]["creature"],
                                    storm=data.factions[fid]["traits"].get("weather_lords", 1.0))
                    wins += resolve(side(a, "A"), side(d, "D"), data.units, random.Random(seed)).attacker_won
                row.append(round(100 * wins / (20 * len(budgets))))
            print(f"{a[:10]:>10} " + "".join(f"{w:>10}" for w in row))


if __name__ == "__main__":
    main()
