"""Saving and loading a campaign as plain JSON.

Everything that changes during a campaign is written out; the fixed game data (factions, units,
map) is not, so a save only works with the data it was made with (checked by the map's name).
The pop-up events of the turn in progress are not kept.
"""

import json
from dataclasses import asdict
from pathlib import Path

from .battle import Regiment
from .diplomacy import Proposal, key
from .economy import Treasury
from .events import Tale
from .state import Army, Game, Victory

VERSION = 1


class SaveError(ValueError):
    pass


def _pair(k):
    return "|".join(sorted(k))


def _unpair(s):
    return key(*s.split("|"))


def to_dict(game):
    return {
        "version": VERSION,
        "map": game.data.map["name"],
        "player": game.player,
        "round": game.round,
        "provinces": {
            pid: {
                "owner": p.owner, "walls": p.walls, "garrison": [asdict(r) for r in p.garrison],
                "besieged_by": p.besieged_by, "buildings": p.buildings, "construction": p.construction,
                "recruits": p.recruits, "captured_round": p.captured_round, "mods": p.mods,
                "siege_turns": p.siege_turns,
            }
            for pid, p in game.provinces.items()
        },
        "armies": [
            {"id": a.id, "faction": a.faction, "province": a.province, "general": a.general,
             "regiments": [asdict(r) for r in a.regiments], "moves_left": a.moves_left,
             "xp": a.xp, "rank": a.rank, "traits": a.traits}
            for a in game.armies.values()
        ],
        "log": game.log[-200:],
        "rng": _rng_state(game.rng),
        "eliminated": game.eliminated,
        "heart_turns": game.heart_turns,
        "winner": asdict(game.winner) if game.winner else None,
        "treasury": {fid: asdict(t) for fid, t in game.treasury.items()},
        "spectate": game.spectate,
        "next_army_id": game._next_army_id,
        "generals_named": game._generals_named,
        "abduct_ready": game.abduct_ready,
        "relations": {_pair(k): v for k, v in game.relations.items()},
        "war_since": {_pair(k): v for k, v in game.war_since.items()},
        "truce_until": {_pair(k): v for k, v in game.truce_until.items()},
        "treachery": game.treachery,
        "grudges": sorted(list(g) for g in game.grudges),
        "last_proposal": [[a, b, kind, r] for (a, b, kind), r in game.last_proposal.items()],
        "proposals": [asdict(p) for p in game.proposals],
        "history": game.history,
        "stats": game.stats,
        "difficulty": game.difficulty,
        "pending_events": [asdict(t) for t in game.pending_events],
        "tribute": game.tribute,
        "raids": {str(k): v for k, v in game.raids.items()},
        "raided": game.raided,
        "techs": game.techs,
        "studying": game.studying,
        "trade": sorted(_pair(k) for k in game.trade),
        "marriages": sorted(_pair(k) for k in game.marriages),
        "vassals": game.vassals,
    }


def from_dict(data, d, ai_factory=None):
    if d.get("version") != VERSION:
        raise SaveError(f"This save was made by another version of the game ({d.get('version')}).")
    if d.get("map") != data.map["name"]:
        raise SaveError(f"This save is for the map {d.get('map')!r}.")
    game = Game.new(data, d["player"], ai_factory=ai_factory, difficulty=d.get("difficulty", "normal"))
    game.round = d["round"]
    for pid, saved in d["provinces"].items():
        p = game.provinces[pid]
        p.owner = saved["owner"]
        p.walls = saved["walls"]
        p.garrison = [Regiment(**r) for r in saved["garrison"]]
        p.besieged_by = saved["besieged_by"]
        p.buildings = list(saved["buildings"])
        p.construction = saved["construction"]
        p.recruits = list(saved["recruits"])
        p.captured_round = saved["captured_round"]
        p.mods = [list(m) for m in saved.get("mods", [])]
        p.siege_turns = saved.get("siege_turns", 0)
    game.armies = {
        a["id"]: Army(a["id"], a["faction"], a["province"], a["general"],
                      [Regiment(**r) for r in a["regiments"]], a["moves_left"],
                      a.get("xp", 0), a.get("rank", 0), list(a.get("traits", ())))
        for a in d["armies"]
    }
    game.log = list(d["log"])
    game.events = []
    game.rng.setstate(_rng_restore(d["rng"]))
    game.eliminated = list(d["eliminated"])
    game.heart_turns = dict(d["heart_turns"])
    game.winner = Victory(**d["winner"]) if d["winner"] else None
    game.treasury = {fid: Treasury(**t) for fid, t in d["treasury"].items()}
    game.spectate = d["spectate"]
    game._next_army_id = d["next_army_id"]
    game._generals_named = dict(d["generals_named"])
    game.abduct_ready = dict(d["abduct_ready"])
    game.relations = {_unpair(k): v for k, v in d["relations"].items()}
    game.war_since = {_unpair(k): v for k, v in d["war_since"].items()}
    game.truce_until = {_unpair(k): v for k, v in d["truce_until"].items()}
    game.treachery = dict(d["treachery"])
    game.grudges = {tuple(g) for g in d["grudges"]}
    game.last_proposal = {(a, b, kind): r for a, b, kind, r in d["last_proposal"]}
    game.proposals = [Proposal(**p) for p in d["proposals"]]
    game.history = list(d.get("history", game.history))  # saves from before the chronicle have none
    game.stats = {fid: dict(row) for fid, row in d.get("stats", {}).items()}
    game.pending_events = [Tale(**t) for t in d.get("pending_events", [])]
    game.tribute = {fid: list(powers) for fid, powers in d.get("tribute", {}).items()}
    game.raids = {int(k): dict(v) for k, v in d.get("raids", {}).items()}
    game.raided = {power: dict(row) for power, row in d.get("raided", {}).items()}
    game.techs = {fid: list(t) for fid, t in d.get("techs", {}).items()}
    game.studying = {fid: dict(s) for fid, s in d.get("studying", {}).items()}
    game.trade = {_unpair(k) for k in d.get("trade", [])}
    game.marriages = {_unpair(k) for k in d.get("marriages", [])}
    game.vassals = dict(d.get("vassals", {}))
    for fid in game.eliminated:
        game.ai.pop(fid, None)
    return game


def summary(d):
    """What a save slot shows without loading the whole campaign."""
    return {"player": d["player"], "round": d["round"], "provinces": sum(
        1 for p in d["provinces"].values() if p["owner"] == d["player"]), "over": bool(d["winner"])
        or d["player"] in d["eliminated"]}


def save_game(game, path, extra=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = to_dict(game)
    if extra:
        d.update(extra)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)  # never leave a half-written save behind


def read_save(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SaveError(f"Cannot read the save: {e}") from None


def load_game(data, path, ai_factory=None):
    return from_dict(data, read_save(path), ai_factory)


def _rng_state(rng):
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _rng_restore(state):
    version, internal, gauss = state
    return version, tuple(internal), gauss
