"""The provinces as drawn on the map (tools/provinces.py made them): which province is where.

Pure data, no graphics: the label raster (province index of every map pixel, 0 for water) and the
description of every province.
"""

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
from PIL import Image

DATA = Path(__file__).resolve().parent / "data" / "map"


@dataclass
class ProvinceInfo:
    id: str
    index: int
    name: str
    owner: str
    culture: str
    religion: str
    town: tuple
    label: tuple
    area: int
    terrain: str
    coastal: bool
    neighbors: list = field(default_factory=list)


class ProvinceMap:
    def __init__(self):
        raw = json.loads((DATA / "provinces.json").read_text(encoding="utf-8"))
        self.provinces = {p["id"]: ProvinceInfo(**{**p, "town": tuple(p["town"]), "label": tuple(p["label"])})
                          for p in raw}
        self.by_index = {p.index: p for p in self.provinces.values()}

    @cached_property
    def labels(self):
        rgb = np.asarray(Image.open(DATA / "provinces.png")).astype(np.int32)
        return rgb[..., 0] + 256 * rgb[..., 1]

    def at(self, x, y):
        """The province at map pixel (x, y), or None at sea."""
        h, w = self.labels.shape
        if not (0 <= x < w and 0 <= y < h):
            return None
        return self.by_index.get(int(self.labels[int(y), int(x)]))

    def lookup(self, values, default=0):
        """An array, indexed by province index, of values[province id] (for colouring the map)."""
        size = max(self.by_index) + 1
        first = next(iter(values.values()), default)
        shape = (size,) + np.shape(first)
        out = np.zeros(shape, dtype=np.asarray(first).dtype if np.ndim(first) else np.float32)
        out[...] = default
        for pid, v in values.items():
            if pid in self.provinces:
                out[self.provinces[pid].index] = v
        return out
