"""Armies of each tradition, equal in cost or in campaign strength, fought against each other.

    python tools/battle_balance.py SEEDS power|cost [JSON of battle constants to try]
"""
import itertools, sys, time
from multiprocessing import Pool
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from crowns.game.armies import Army, Regiment
from crowns.game.battle import Battle
from crowns.game.rules import UNITS

MIX = {
    "latin": [("knights", 2), ("men_at_arms", 1), ("crossbowmen", 2), ("militia", 3), ("light_horse", 1)],
    "vlach": [("boyars", 2), ("calarasi", 3), ("vlach_archers", 2), ("great_host", 3)],
    "balkan": [("vlastela", 2), ("stradioti", 2), ("bowmen", 2), ("spearmen", 4)],
    "greek": [("archontes", 1), ("stratiotai", 2), ("greek_archers", 3), ("militia_greek", 4)],
    "ottoman": [("sipahis", 3), ("akinjis", 2), ("azaps", 3), ("janissaries", 1)],
    "steppe": [("horse_archers", 6), ("mirza_horse", 2)],
    "levant": [("mamluks", 2), ("kurdish_horse", 2), ("levant_foot", 3)],
}
BUDGET = 9000
SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
MODE = sys.argv[2] if len(sys.argv) > 2 else "cost"
TERRAINS = ["plains", "hills"]


def power(u, men, terrain="plains"):
    t = UNITS[u]
    p = t.melee + 0.8 * t.missile + 0.5 * t.defence
    if t.kind == "horse":
        p *= {"plains": 1.15, "hills": 0.9}.get(terrain, 1.0)
    return men / 100.0 * p * (0.5 + t.morale / 20.0) * 1.1



def army(tag):
    regs = [(u, n) for u, n in MIX[tag] for _ in range(n)]
    if MODE == "cost":
        k = BUDGET / sum(UNITS[u].cost for u, _ in regs)
    else:
        k = 900 / sum(power(u, UNITS[u].men) for u, _ in regs)
    return Army(tag, tag, tag, 0, 0, [Regiment(u, int(UNITS[u].men * k), 0.2) for u, _ in regs])


PARAMS = {}


def fight(job):
    a, d, seed, terrain, params = job
    import crowns.game.battle as B
    for k, v in params.items():
        setattr(B, k, v)
    b = Battle(army(a), army(d), UNITS, terrain, seed=seed)
    w = b.run(dt=1.0)
    lost = [sum(u.start_men - u.men for u in b.units if u.side == s) / sum(u.start_men for u in b.units if u.side == s)
            for s in (0, 1)]
    return a, d, w, b.time, lost


if __name__ == "__main__":
    tags = list(MIX)
    import json
    params = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    jobs = [(a, d, s, t, params) for a in tags for d in tags if a != d for s in range(SEEDS) for t in TERRAINS]
    t0 = time.time()
    with Pool(4) as pool:
        res = pool.map(fight, jobs)
    wins = {}
    times = []
    att = 0
    lost_w, lost_l = [], []
    for a, d, w, tm, lost in res:
        wins.setdefault((a, d), []).append(w == 0)
        wins.setdefault((d, a), []).append(w == 1)
        att += w == 0
        times.append(tm)
        lost_w.append(lost[w]); lost_l.append(lost[1 - w])
    print("        " + " ".join(f"{t[:6]:>7}" for t in tags) + "   total")
    for r in tags:
        row = []
        allw = []
        for c in tags:
            if r == c:
                row.append("     --")
            else:
                v = wins[(r, c)]
                allw += v
                row.append(f"{100 * sum(v) / len(v):6.0f}%")
        print(f"{r:>8}" + " ".join(row) + f"  {100 * sum(allw) / len(allw):5.0f}%")
    print(f"attacker wins {100 * att / len(res):.0f}%  mean time {sum(times) / len(times):.0f}s  max {max(times):.0f}s"
          f"  timeouts {sum(t >= 1800 for t in times)}  winner lost {100 * sum(lost_w) / len(lost_w):.0f}%"
          f"  loser lost {100 * sum(lost_l) / len(lost_l):.0f}%   ({time.time() - t0:.0f}s)")
