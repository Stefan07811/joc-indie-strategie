"""Let the AI play the campaign for decades and tell how the world turns out: who grows, who falls, how
many wars and battles, how full the treasuries are. For balancing.

    python tools/campaign_sim.py [YEARS] [SEED] [PLAYER]
"""

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crowns.game.campaign import Campaign  # noqa: E402
from crowns.game.navigation import NavalNavigation, Navigation  # noqa: E402
from crowns.game.realms import load  # noqa: E402
from crowns.mapdata import Ground  # noqa: E402
from crowns.provinces import ProvinceMap  # noqa: E402


def snapshot(c):
    held = Counter(p.owner for p in c.provinces.values())
    alive = [t for t, r in c.realms.items() if r.alive]
    top = ", ".join(f"{t} {n}" for t, n in held.most_common(8))
    ott = sum(n for t, n in held.items() if t.startswith("ott_"))
    rich = sorted(((r.treasury, t) for t, r in c.realms.items() if r.alive), reverse=True)[:3]
    return (f"{c.date}: {len(alive)} realms alive; Ottomans hold {ott}; wars {len(c.wars)}; "
            f"battles so far {len(c.battles)}\n    largest: {top}\n    richest: "
            + ", ".join(f"{t} {v:,.0f}" for v, t in rich))


def main(years=50, seed=1, player=None):
    provmap = ProvinceMap()
    ground = Ground()
    nav = Navigation(ground, provmap)
    naval = NavalNavigation(ground, provmap)
    realms, relations = load()
    c = Campaign(provmap, realms, relations, player=player, seed=seed)
    c.nav, c.naval_nav = nav, naval
    c.attach_ai(nav, naval)
    peaces = Counter()
    declared = Counter()
    make_peace, declare_war = c.make_peace, c.declare_war

    def counting_peace(war, terms):
        kind = "provinces" if terms.get("provinces") else ("tribute" if terms.get("tribute") else
                ("gold" if terms.get("gold") else ("independence" if terms.get("independence") else "white")))
        peaces[kind] += 1
        return make_peace(war, terms)

    def counting_war(tag, other, goal):
        declared[goal["kind"]] += 1
        return declare_war(tag, other, goal)
    c.make_peace, c.declare_war = counting_peace, counting_war
    print(snapshot(c))
    t0 = time.time()
    for month in range(12 * years):
        c.end_month()
        c.pending, c.proposals = [], []
        if (month + 1) % 120 == 0:
            print(snapshot(c), f"  ({time.time() - t0:.0f} s)")
            print("    wars declared:", dict(declared), " peaces:", dict(peaces))
    return c


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else 50, int(args[1]) if len(args) > 1 else 1, args[2] if len(args) > 2 else None)
