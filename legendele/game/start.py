"""Start options for a new campaign: how many rivals, whose homeland is whose, the year the war
begins and how much land wins it.

The options are resolved once, when the game is made, into the legends that take part
("factions") and the homeland each of them starts in ("homes": legend -> the legend whose
provinces, capital and starting armies' places it takes). Both are saved with the game.
"""

ERAS = {
    1400: {"name": "1400: Age of Legends", "summary": "The war begins with bare realms and little gold.",
           "gold": 0, "techs": [], "buildings": [], "veterans": 0},
    1450: {"name": "1450: Age of Kings",
           "summary": "Older, richer realms: 200 more gold, two traditions learnt, barracks in the capital "
                      "and an elite regiment in every starting army.",
           "gold": 200, "techs": ["drill", "markets"], "buildings": ["barracks"], "veterans": 1},
}
VICTORY = {
    "short": ("Short war", 0.5),
    "normal": ("Normal war", 0.7),
    "long": ("Long war", 0.85),
}
DEFAULTS = {"rivals": 5, "shuffle": False, "era": 1400, "victory": "normal"}


def playable(data):
    return [f for f, d in data.factions.items() if d["playable"]]


def resolve(data, player, options, rng):
    """The options filled in with "factions" and "homes" (unless a saved game already has them)."""
    o = {**DEFAULTS, **(options or {})}
    o["era"] = int(o["era"])
    if o["era"] not in ERAS:
        raise ValueError(f"Unknown era: {o['era']}")
    if o["victory"] not in VICTORY:
        raise ValueError(f"Unknown victory: {o['victory']}")
    every = playable(data)
    if "factions" not in o:
        others = [f for f in every if f != player]
        n = max(1, min(len(others), int(o["rivals"])))
        chosen = set(rng.sample(others, n)) if n < len(others) else set(others)
        o["factions"] = [f for f in every if f == player or f in chosen]
    if "homes" not in o:
        homes = list(o["factions"])
        if o["shuffle"]:
            rng.shuffle(homes)
        o["homes"] = dict(zip(o["factions"], homes))
    o["rivals"] = len(o["factions"]) - 1
    return o


def owners(options):
    """{the legend a homeland belongs to in map.json: the legend that starts there}."""
    return {home: fid for fid, home in options["homes"].items()}


def capital_garrison(data, fid):
    capital = data.factions[fid]["capital"]
    return list(next(p.get("garrison", ()) for p in data.provinces if p["id"] == capital))


def province_start(data, options, p):
    """(owner, garrison) of a map province at the start of this game."""
    owner, garrison = p["owner"], list(p.get("garrison", ()))
    if owner is None or not data.factions[owner]["playable"]:
        return owner, garrison
    new = owners(options).get(owner)
    if new is None:  # this legend sits the war out: its lands are free, held by the Rebels
        from .legends import REBEL_UNITS
        return None, list(REBEL_UNITS)
    if new != owner and garrison:
        garrison = capital_garrison(data, new) if p["id"] == data.factions[owner]["capital"] \
            else [_like(data, new, uid) for uid in garrison]
    return new, garrison


def start_armies(data, options):
    """[(faction, province, general, regiments)]: each legend's own armies, in its homeland's places."""
    by = {}
    for a in data.map["start_armies"]:
        by.setdefault(a["faction"], []).append(a)
    era = ERAS[options["era"]]
    armies = []
    for fid, home in options["homes"].items():
        for a, spot in zip(by.get(fid, []), by.get(home, [])):
            regiments = list(a["regiments"])
            if era["veterans"]:
                elite = [u for u, d in data.units.items() if d["faction"] == fid and d["tier"] == 2]
                regiments += elite[:era["veterans"]]
            armies.append((fid, spot["province"], a["general"], regiments))
    return armies


def _like(data, fid, uid):
    """`fid`'s unit of the same tier as `uid` (or its first levy)."""
    tier = data.units[uid]["tier"]
    mine = [u for u, d in data.units.items() if d["faction"] == fid and d["tier"] == tier] or \
        [u for u, d in data.units.items() if d["faction"] == fid and d["tier"] == 1]
    return mine[0]


def conquest(data, options):
    return round(len(data.provinces) * VICTORY[options["victory"]][1])
