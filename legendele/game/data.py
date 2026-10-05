"""Loads and validates the JSON game data (factions, units, map)."""

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DataError(ValueError):
    pass


@dataclass(frozen=True)
class GameData:
    factions: dict
    units: dict
    map: dict

    @property
    def terrain(self):
        return self.map["terrain"]

    @property
    def provinces(self):
        return self.map["provinces"]

    @classmethod
    def load(cls, data_dir=DATA_DIR):
        data_dir = Path(data_dir)

        def read(name):
            return json.loads((data_dir / name).read_text(encoding="utf-8"))

        data = cls(factions=read("factions.json"), units=read("units.json"), map=read("map.json"))
        data.validate()
        return data

    def validate(self):
        ids = [p["id"] for p in self.provinces]
        if len(ids) != len(set(ids)):
            raise DataError("duplicate province ids")
        known = set(ids)
        for p in self.provinces:
            if p["terrain"] not in self.terrain:
                raise DataError(f"{p['id']}: unknown terrain {p['terrain']!r}")
            if p["owner"] is not None and p["owner"] not in self.factions:
                raise DataError(f"{p['id']}: unknown owner {p['owner']!r}")
            for n in p.get("neighbors", ()):
                if n not in known:
                    raise DataError(f"{p['id']}: unknown neighbour {n!r}")
        for fid, f in self.factions.items():
            if f["capital"] is not None and f["capital"] not in known:
                raise DataError(f"{fid}: unknown capital {f['capital']!r}")
            for t in f["terrain_mastery"]:
                if t not in self.terrain:
                    raise DataError(f"{fid}: unknown mastered terrain {t!r}")
        for uid, u in self.units.items():
            if u["faction"] not in self.factions:
                raise DataError(f"unit {uid}: unknown faction {u['faction']!r}")
        for a in self.map["start_armies"]:
            if a["faction"] not in self.factions or a["province"] not in known:
                raise DataError(f"bad starting army {a}")
            for uid in a["regiments"]:
                if uid not in self.units:
                    raise DataError(f"starting army of {a['general']}: unknown unit {uid!r}")
