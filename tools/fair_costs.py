"""Measure what each unit is worth in battle, compared with Levy Spearmen (for balancing).

For every unit, find how many regiments of it (fractions allowed: the last one fights at partial
strength) beat 8 regiments of Levy Spearmen half of the time, attacking and defending alike.
The fair cost is the spearmen's total cost divided by that number.

    python tools/fair_costs.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legendele.game import GameData  # noqa: E402
from legendele.game.battle import Regiment, Side, resolve  # noqa: E402

REFERENCE, REF_COUNT, FIGHTS = "oteni", 8, 60


def regiments(data, uid, count):
    whole, part = int(count), count - int(count)
    regs = [Regiment(uid, data.units[uid]["hp"]) for _ in range(whole)]
    if part > 0.05:
        regs.append(Regiment(uid, data.units[uid]["hp"] * part))
    return regs


def win_rate(data, uid, count):
    wins = 0
    for seed in range(FIGHTS):
        ours = Side("x", regiments(data, uid, count), "General")
        theirs = Side("y", regiments(data, REFERENCE, REF_COUNT), "General")
        if seed % 2:
            wins += not resolve(theirs, ours, data.units, random.Random(seed)).attacker_won
        else:
            wins += resolve(ours, theirs, data.units, random.Random(seed)).attacker_won
    return wins / FIGHTS


def fair_count(data, uid):
    lo, hi = 0.5, 40.0
    for _ in range(18):
        mid = (lo + hi) / 2
        if win_rate(data, uid, mid) < 0.5:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    data = GameData.load()
    budget = data.units[REFERENCE]["cost"] * REF_COUNT
    print(f"{'unit':18}{'cost':>6}{'fair':>6}{'value per gold':>16}")
    for uid, u in data.units.items():
        fair = budget / fair_count(data, uid)
        print(f"{uid:18}{u['cost']:>6}{round(fair):>6}{fair / u['cost']:>16.2f}")


if __name__ == "__main__":
    main()
